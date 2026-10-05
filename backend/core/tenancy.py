"""Multi-tenant onboarding and sign-in for farms.

1. A farm registers (farm name, owner, phone, email, district): a pending request.
2. The owner of Poultry 360 approves it on the admin page: a tenant key and
   username are issued to send to the farm (also as a one-click sign-in link).
3. The farm signs in with the tenant key and username.

The tenant key is signed (HMAC-SHA256 over tenant + username), so it is checked
without a database lookup: approved farms can always sign in, even after a
free-tier restart wipes the disk. The session token is signed the same way
(7 days). Daily caps per farm user, per network and for the whole app bound
what the AI key and the CPU can spend.

Required in production (POULTRY_ENV=production, or any Render deploy) and when
POULTRY_AUTH=on; off for local development so the existing flows run unchanged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path

TOKEN_DAYS = 7
DAILY_PER_USER = int(os.environ.get("POULTRY_DAILY_PER_USER", "40"))
DAILY_PER_IP = int(os.environ.get("POULTRY_DAILY_PER_IP", "60"))
DAILY_TOTAL = int(os.environ.get("POULTRY_DAILY_TOTAL", "400"))
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[a-z]{2,}$", re.I)
_USERNAME = re.compile(r"^[a-z0-9][a-z0-9._-]{1,31}$")
_FALLBACK = secrets.token_hex(32)

_attempts: dict[str, deque[float]] = defaultdict(deque)
_usage: dict[str, int] = defaultdict(int)
_usage_day = {"day": ""}


class AuthError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def auth_required() -> bool:
    # Render sets RENDER on every service, so a hosted deploy is locked even before settings sync.
    return (os.environ.get("POULTRY_AUTH", "").lower() == "on"
            or os.environ.get("POULTRY_ENV", "").lower() == "production" or bool(os.environ.get("RENDER")))


def _ai_key() -> str:
    return os.environ.get("DEEPSEEK_API_KEY", "")


def _secret() -> bytes:
    """Stable with no extra setup: derived from the server-only AI key. Read at call time."""
    if os.environ.get("POULTRY_SECRET"):
        return os.environ["POULTRY_SECRET"].encode()
    return (hashlib.sha256(b"poultry-token:" + _ai_key().encode()).hexdigest() if _ai_key() else _FALLBACK).encode()


def derived_admin_key() -> str:
    return hashlib.sha256(b"poultry-admin:" + _ai_key().encode()).hexdigest()[:24] if _ai_key() else ""


def check_admin(given: str | None) -> None:
    given = (given or "").strip()
    if not auth_required() and not os.environ.get("ADMIN_KEY"):
        return                                   # local development: admin open unless ADMIN_KEY is set
    valid = [k for k in (os.environ.get("ADMIN_KEY", ""), derived_admin_key()) if k]
    if not valid or not any(hmac.compare_digest(given, k) for k in valid):
        raise AuthError(401, "Admin key required")


# ------------------------------------------------------------------ signing
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _mac(*parts: str) -> bytes:
    return hmac.new(_secret(), "|".join(parts).encode(), hashlib.sha256).digest()


def tenant_key(slug: str, username: str) -> str:
    return f"{slug}.{base64.b32encode(_mac('tenant-key', slug, username)).decode().rstrip('=')[:16]}"


def check_tenant_key(key: str, username: str) -> str | None:
    slug, _, code = key.strip().rpartition(".")
    if not slug or not code:
        return None
    return slug if hmac.compare_digest(tenant_key(slug, username).rpartition(".")[2], code.upper()) else None


def make_token(name: str, who: str, tenant: str, tenant_name: str, now: float | None = None) -> str:
    issued = time.time() if now is None else now
    payload = _b64(json.dumps({"n": name, "u": who, "t": tenant, "tn": tenant_name, "exp": int(issued + TOKEN_DAYS * 86400)}).encode())
    return f"{payload}.{_b64(_mac('token', payload))}"


def read_token(token: str) -> dict | None:
    try:
        payload, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _b64(_mac("token", payload))):
            return None
        data = json.loads(_unb64(payload))
        return data if data.get("exp", 0) > time.time() and data.get("t") else None
    except Exception:
        return None


# ------------------------------------------------------------------ storage (registrations only)
def _db_path() -> Path:
    d = Path(os.environ.get("POULTRY_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return d / "tenancy.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(_db_path())
    c.row_factory = sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS registrations (
        id TEXT PRIMARY KEY, farm TEXT, owner TEXT, email TEXT, phone TEXT, district TEXT,
        status TEXT DEFAULT 'pending', tenant TEXT, username TEXT, created_at REAL)""")
    return c


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["tenant_key"] = tenant_key(d["tenant"], d["username"]) if d["status"] == "approved" and d["tenant"] and d["username"] else None
    return d


def _limit(key: str, max_hits: int, seconds: int, message: str) -> None:
    window, now = _attempts[key], time.time()
    while window and now - window[0] > seconds:
        window.popleft()
    if len(window) >= max_hits:
        raise AuthError(429, message)
    window.append(now)


def _slugify(text: str) -> str:
    return (re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "farm")[:40].strip("-")


# ------------------------------------------------------------------ flows
def register(farm: str, owner: str, phone: str, email: str, district: str, ip: str) -> dict:
    _limit("reg:" + ip, 5, 3600, "Too many requests from this network. Please try again later.")
    farm, owner, phone, email = farm.strip(), owner.strip(), phone.strip(), email.strip().lower()
    if len(farm) < 2 or not owner:
        raise AuthError(422, "Please enter the farm name and your name.")
    if not phone and not email:
        raise AuthError(422, "Please give a phone number or an email so we can send your key.")
    if email and not _EMAIL.match(email):
        raise AuthError(422, "Please enter a valid email address.")
    with _conn() as c:
        rid = uuid.uuid4().hex
        c.execute("INSERT INTO registrations (id, farm, owner, email, phone, district, created_at) VALUES (?,?,?,?,?,?,?)",
                  (rid, farm[:120], owner[:60], email[:160], phone[:20], district.strip()[:60], time.time()))
    return {"id": rid, "status": "pending"}


def login(key: str, username: str, ip: str) -> dict:
    _limit("login:" + ip, 10, 900, "Too many attempts. Try again in a few minutes.")
    username = username.strip().lower()
    slug = check_tenant_key(key, username)
    if not slug:
        raise AuthError(401, "Tenant key or username is not right.")
    with _conn() as c:
        r = c.execute("SELECT * FROM registrations WHERE tenant=? AND username=?", (slug, username)).fetchone()
    if r and r["status"] == "revoked":
        raise AuthError(403, "This access has been turned off. Please contact Poultry 360.")
    name, farm = (r["owner"], r["farm"]) if r else (username, slug.replace("-", " ").title())
    return {"token": make_token(name, username, slug, farm), "name": name, "tenant": slug, "tenant_name": farm, "days": TOKEN_DAYS}


def list_registrations() -> list[dict]:
    with _conn() as c:
        return [_row(r) for r in c.execute("SELECT * FROM registrations ORDER BY created_at DESC").fetchall()]


def approve(rid: str, username: str = "") -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM registrations WHERE id=?", (rid,)).fetchone()
        if not r:
            raise AuthError(404, "Request not found")
        user = (username or re.sub(r"[^a-z0-9]", "", ((r["email"] or "").split("@")[0] or r["owner"]).lower())[:20] or "farmer").strip().lower()
        if len(user) < 2:
            user += "01"
        if not _USERNAME.match(user):
            raise AuthError(422, "Usernames use 2-32 lowercase letters, digits, dots, dashes or underscores.")
        slug = r["tenant"]
        if not slug:
            taken = {row[0] for row in c.execute("SELECT tenant FROM registrations WHERE tenant IS NOT NULL")}
            base = slug = _slugify(r["farm"])
            n = 2
            while slug in taken:
                slug, n = f"{base}-{n}", n + 1
        c.execute("UPDATE registrations SET status='approved', tenant=?, username=? WHERE id=?", (slug, user, rid))
        return _row(c.execute("SELECT * FROM registrations WHERE id=?", (rid,)).fetchone())


def reject(rid: str) -> dict:
    with _conn() as c:
        r = c.execute("SELECT * FROM registrations WHERE id=?", (rid,)).fetchone()
        if not r:
            raise AuthError(404, "Request not found")
        status = "revoked" if r["status"] == "approved" else "rejected"
        c.execute("UPDATE registrations SET status=? WHERE id=?", (status, rid))
        return {"id": rid, "status": status}


def issue_directly(farm: str, owner: str, username: str = "", phone: str = "", email: str = "") -> dict:
    with _conn() as c:
        rid = uuid.uuid4().hex
        c.execute("INSERT INTO registrations (id, farm, owner, email, phone, district, created_at) VALUES (?,?,?,?,?,?,?)",
                  (rid, farm.strip()[:120], owner.strip()[:60], email.strip().lower()[:160], phone.strip()[:20], "", time.time()))
    return approve(rid, username)


# ------------------------------------------------------------------ guard for the feature endpoints
def authorize(authorization: str | None, ip: str) -> dict | None:
    """The signed-in farm for a protected call (None when sign-in is off), with the daily caps applied."""
    if not auth_required():
        return None
    data = read_token((authorization or "").removeprefix("Bearer ").strip())
    if not data:
        raise AuthError(401, "Please sign in to continue.")
    today = time.strftime("%Y-%m-%d")
    if _usage_day["day"] != today:
        _usage.clear()
        _usage_day["day"] = today
    who = f"{data['t']}:{data['u']}"
    if _usage["__total__"] >= DAILY_TOTAL:
        raise AuthError(429, "Today's free limit for the whole app is used up. Please come back tomorrow.")
    if _usage["u:" + who] >= DAILY_PER_USER:
        raise AuthError(429, f"You have used today's {DAILY_PER_USER} requests. Please come back tomorrow.")
    if _usage["ip:" + ip] >= DAILY_PER_IP:
        raise AuthError(429, "Today's requests from this network are used up. Please come back tomorrow.")
    for k in ("u:" + who, "ip:" + ip, "__total__"):
        _usage[k] += 1
    return data

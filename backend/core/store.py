"""The one place that talks to the database.

Postgres when DATABASE_URL is set (production: survives restarts and redeploys),
otherwise a SQLite file in POULTRY_DATA_DIR (local runs and tests). The same SQL
runs on both, so a test on SQLite exercises the production queries.

Three tables, all small:
- registrations: farms asking to join, and their approval or revocation
- audit_log: who approved, rejected or issued what, and when
- usage_counters: requests per farm user, per network and in total, per day,
  so a restart does not reset the daily caps that bound the AI bill
"""
from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import (Column, Float, Integer, MetaData, String, Table, Text, create_engine,
                        text)
from sqlalchemy.engine import Connection, Engine

metadata = MetaData()

registrations = Table(
    "registrations", metadata,
    Column("id", String(32), primary_key=True),
    Column("farm", String(120)), Column("owner", String(60)),
    Column("email", String(160)), Column("phone", String(20)), Column("district", String(60)),
    Column("status", String(12), server_default="pending"),
    Column("tenant", String(64), index=True), Column("username", String(32)),
    Column("created_at", Float),
)

audit_log = Table(
    "audit_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("at", Float, index=True),
    Column("actor", String(64)), Column("action", String(32)),
    Column("target", String(64)), Column("detail", Text),
    Column("request_id", String(32)),
)

usage_counters = Table(
    "usage_counters", metadata,
    Column("day", String(10), primary_key=True),
    Column("key", String(200), primary_key=True),
    Column("count", Integer, nullable=False, server_default="0"),
)

_engines: dict[str, Engine] = {}


def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Neon, Render and Heroku hand out postgres:// URLs; SQLAlchemy wants the driver named.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url
    d = Path(os.environ.get("POULTRY_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
    d.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{d / 'tenancy.db'}"


def engine() -> Engine:
    """One pooled engine per URL; tables are created on first use."""
    url = database_url()
    if url not in _engines:
        kwargs = {"pool_pre_ping": True} if not url.startswith("sqlite") else {}
        eng = create_engine(url, **kwargs)
        metadata.create_all(eng)
        _engines[url] = eng
    return _engines[url]


def backend() -> str:
    return engine().dialect.name


@contextmanager
def connect() -> Iterator[Connection]:
    """A transaction: committed when the block ends, rolled back on an error."""
    with engine().begin() as c:
        yield c


def ping() -> bool:
    try:
        with engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def audit(actor: str, action: str, target: str, detail: dict | None = None, request_id: str = "") -> None:
    with connect() as c:
        c.execute(audit_log.insert().values(at=time.time(), actor=actor, action=action, target=target,
                                            detail=json.dumps(detail or {}), request_id=request_id))


def recent_audit(limit: int = 50) -> list[dict]:
    with connect() as c:
        rows = c.execute(audit_log.select().order_by(audit_log.c.id.desc()).limit(limit)).mappings()
        return [{**r, "detail": json.loads(r["detail"] or "{}")} for r in rows]


def usage(day: str, keys: list[str]) -> dict[str, int]:
    with connect() as c:
        rows = c.execute(usage_counters.select().where(usage_counters.c.day == day,
                                                       usage_counters.c.key.in_(keys)))
        found = {r.key: r.count for r in rows}
    return {k: found.get(k, 0) for k in keys}


def add_usage(day: str, keys: list[str]) -> None:
    # ON CONFLICT ... DO UPDATE is the same on Postgres and SQLite (3.24+): one atomic upsert per key.
    with connect() as c:
        for k in keys:
            c.execute(text("INSERT INTO usage_counters (day, key, count) VALUES (:d, :k, 1) "
                           "ON CONFLICT (day, key) DO UPDATE SET count = usage_counters.count + 1"),
                      {"d": day, "k": k})

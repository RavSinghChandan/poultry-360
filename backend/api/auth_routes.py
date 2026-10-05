"""Sign-in endpoints: farms register, the owner approves, farms sign in with a tenant key."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from core import tenancy

router = APIRouter(prefix="/api", tags=["auth"])


class RegisterIn(BaseModel):
    farm: str
    owner: str
    phone: str = ""
    email: str = ""
    district: str = ""


class LoginIn(BaseModel):
    tenant_key: str
    username: str


class ApproveIn(BaseModel):
    username: str = ""


class IssueIn(BaseModel):
    farm: str
    owner: str
    username: str = ""
    phone: str = ""
    email: str = ""


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for", "")
    return fwd.split(",")[0].strip() or (request.client.host if request.client else "unknown")


def _call(fn, *args):
    try:
        return fn(*args)
    except tenancy.AuthError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/auth/status")
def status() -> dict:
    return {"required": tenancy.auth_required(), "daily_per_user": tenancy.DAILY_PER_USER}


@router.post("/auth/register")
def register(body: RegisterIn, request: Request) -> dict:
    return _call(tenancy.register, body.farm, body.owner, body.phone, body.email, body.district, client_ip(request))


@router.post("/auth/login")
def login(body: LoginIn, request: Request) -> dict:
    return _call(tenancy.login, body.tenant_key, body.username, client_ip(request))


def _admin(key: str | None) -> None:
    _call(tenancy.check_admin, key)


@router.get("/admin/registrations")
def registrations(x_admin_key: str | None = Header(default=None)) -> list[dict]:
    _admin(x_admin_key)
    return tenancy.list_registrations()


@router.post("/admin/registrations/{rid}/approve")
def approve(rid: str, body: ApproveIn, x_admin_key: str | None = Header(default=None)) -> dict:
    _admin(x_admin_key)
    return _call(tenancy.approve, rid, body.username.strip().lower())


@router.post("/admin/registrations/{rid}/reject")
def reject(rid: str, x_admin_key: str | None = Header(default=None)) -> dict:
    _admin(x_admin_key)
    return _call(tenancy.reject, rid)


@router.post("/admin/issue")
def issue(body: IssueIn, x_admin_key: str | None = Header(default=None)) -> dict:
    _admin(x_admin_key)
    if len(body.farm.strip()) < 2 or not body.owner.strip():
        raise HTTPException(422, "Please enter the farm name and the owner's name.")
    return _call(tenancy.issue_directly, body.farm, body.owner, body.username.strip().lower(), body.phone, body.email)

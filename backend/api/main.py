"""Platform HTTP surface.

This file knows nothing about poultry. It discovers features, mounts them, and
exposes platform-level endpoints. Adding a feature does not change this file.
"""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api.auth_routes import client_ip, router as auth_router
from core import logs, store, tenancy
from core.context import reset_request_id, set_request_id
from core.config import settings
from core.registry import FeatureRegistry
from harness import llm, metrics
from harness.policy import Mode, Policy
from harness.tools import Tool, ToolRegistry
from harness.tracing import Tracer

logs.setup()
log = logging.getLogger("poultry360")

app = FastAPI(title=settings.app_name, version=settings.version)
app.add_middleware(
    CORSMiddleware,
    # "*" by default: sign-in is a bearer token, never a cookie, so another site
    # cannot borrow a farmer's session. POULTRY_CORS narrows it (comma separated).
    allow_origins=settings.cors_origin_list,
    expose_headers=["X-Request-ID"],
    allow_methods=["*"],
    allow_headers=["*"],
)

features = FeatureRegistry()
features.discover()
app.include_router(auth_router)


@app.middleware("http")
async def farms_sign_in(request: Request, call_next):
    """Every feature action (a POST under /api/<feature>/) needs a signed-in farm when sign-in is on.

    Reading tips, schedules and sign lists stays open; the work that spends CPU
    or the AI key is what needs a tenant key, within the daily caps.
    """
    parts = request.url.path.strip("/").split("/")
    if request.method == "POST" and len(parts) >= 3 and parts[0] == "api" and parts[1] in features.loaded:
        try:
            tenancy.authorize(request.headers.get("authorization"), client_ip(request))
        except tenancy.AuthError as e:
            return JSONResponse({"detail": e.message}, status_code=e.status)
    return await call_next(request)

# Registered last, so it is outermost and also times the sign-in refusals.
@app.middleware("http")
async def measure(request: Request, call_next):
    """Latency, status and farm for every API call, for the owner's ops panel."""
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    started = time.perf_counter()
    response = await call_next(request)
    # Group by template, so /admin/registrations/<id>/approve is one row, not one per farm.
    route = request.url.path
    for name, value in (request.scope.get("path_params") or {}).items():
        route = route.replace(f"/{value}", f"/{{{name}}}", 1)
    token = tenancy.read_token((request.headers.get("authorization") or "").removeprefix("Bearer ").strip())
    ms = (time.perf_counter() - started) * 1000
    tenant = token["t"] if token else None
    metrics.record_request(f"{request.method} {route}", response.status_code, ms, tenant)
    log.info("request", extra={"fields": {"method": request.method, "route": route, "status": response.status_code,
                                           "ms": round(ms, 1), "tenant": tenant}})
    return response


_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000",
}


# Registered last of all, so it is outermost: every log line and audit row below it carries the id.
@app.middleware("http")
async def request_context(request: Request, call_next):
    """A request id on every call (kept from X-Request-ID if the caller sent one), echoed back,
    and a JSON 500 that names it instead of a stack trace."""
    rid = (request.headers.get("x-request-id") or "")[:32] or uuid.uuid4().hex[:16]
    token = set_request_id(rid)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("unhandled error", extra={"fields": {"path": request.url.path}})
        response = JSONResponse({"detail": "Something went wrong on our side. Please try again.",
                                 "request_id": rid}, status_code=500)
    finally:
        reset_request_id(token)
    response.headers["X-Request-ID"] = rid
    for k, v in _SECURITY_HEADERS.items():
        response.headers.setdefault(k, v)
    return response


# Every healthy feature's routes, mounted under its own key.
for key, router in features.routers():
    app.include_router(router, prefix=f"/api/{key}", tags=[key])


def build_agent_tools() -> ToolRegistry:
    """The shared registry, assembled from every healthy feature's tools."""
    registry = ToolRegistry(
        policy=Policy(mode=Mode(settings.policy_mode)),
        tracer=Tracer(),
    )
    for spec in features.tools():
        registry.register(Tool(
            name=spec.name, run=spec.run, effect=spec.effect,
            description=spec.description, reads_untrusted=spec.reads_untrusted,
        ))
    return registry


@app.get("/api/health", tags=["platform"])
def health() -> dict[str, Any]:
    """Platform and per-feature health. A sick feature is visible here."""
    unhealthy = [lf.key for lf in features.loaded.values() if not lf.healthy]
    return {
        "status": "degraded" if (unhealthy or features.failed) else "ok",
        "version": settings.version,
        "features_loaded": len(features.loaded),
        "features_unhealthy": unhealthy,
        "features_failed": features.failed,
        "policy_mode": settings.policy_mode,
        "llm_enabled": settings.llm_enabled,
    }


@app.get("/api/ready", tags=["platform"])
def ready() -> JSONResponse:
    """Readiness: can this instance serve real work? Unlike /api/health (is the process up),
    this checks the database, so a load balancer can hold traffic until it answers."""
    db_ok = store.ping()
    body = {"status": "ready" if db_ok else "not_ready", "database": store.backend() if db_ok else "unreachable",
            "durable": not store.database_url().startswith("sqlite")}
    return JSONResponse(body, status_code=200 if db_ok else 503)


@app.get("/api/features", tags=["platform"])
def feature_list(lang: str | None = None) -> dict[str, Any]:
    """What the UI builds its menu from, in the reader's language."""
    return features.manifest(lang)


@app.get("/api/whoami", tags=["platform"])
def whoami(request: Request) -> dict:
    """Who is asking, and over which address.

    Exists for one reason: when someone says "it does not work on my phone",
    this answers whether the phone reached the server at all, and on which
    network. If the phone can load this, the server is fine and the problem
    is elsewhere; if it cannot, the phone never reached the machine.
    """
    client = request.client.host if request.client else "unknown"
    return {
        "you_are": client,
        "you_reached": request.headers.get("host", "?"),
        "same_subnet": client.rsplit(".", 1)[0] == _lan_ip().rsplit(".", 1)[0],
        "server_lan_ip": _lan_ip(),
        "ok": True,
    }


def _lan_ip() -> str:
    """The address a phone on the same Wi-Fi should use."""
    import socket

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))       # no packet sent; just picks a route
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


@app.get("/api/languages", tags=["platform"])
def languages() -> dict:
    """Languages the app speaks, for the picker.

    The client sends its choice as `lang` on each call; nothing is stored
    server-side, so the same deployment serves a Bengali and a Bhojpuri
    farmer at the same time.
    """
    from core.languages import DEFAULT_LANGUAGE, catalogue

    return {"languages": catalogue(), "default": DEFAULT_LANGUAGE}


@app.get("/api/tools", tags=["platform"])
def tool_list() -> dict[str, Any]:
    """Every tool the agent can reach, and the authority each carries."""
    return {"tools": [
        {"name": t.name, "effect": t.effect.value, "description": t.description,
         "reads_untrusted": t.reads_untrusted}
        for t in features.tools()
    ]}


@app.get("/api/model-info", tags=["platform"])
def model_info() -> dict[str, Any]:
    return {
        "llm": llm.status(),
        "routes": {
            "factual": "published table only; no model involved",
            "explanatory": "model only; no published number at stake",
            "diagnostic": "table first, then the model reasons over its figures",
        },
        "constraint": "the model never originates a value a farmer acts on",
    }


# ── Static frontend ────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent.parent
_CANDIDATES = [_ROOT / "frontend" / "dist" / "poultry-360" / "browser",
               _ROOT / "frontend"]
_FRONTEND = next((p for p in _CANDIDATES if (p / "index.html").is_file()), None)

if _FRONTEND is not None:
    @app.get("/{path:path}", include_in_schema=False)
    def serve(path: str):
        candidate = (_FRONTEND / path).resolve()
        if path and _FRONTEND in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND / "index.html")

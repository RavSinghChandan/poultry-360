"""Platform HTTP surface.

This file knows nothing about poultry. It discovers features, mounts them, and
exposes platform-level endpoints. Adding a feature does not change this file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from api.auth_routes import client_ip, router as auth_router
from core import tenancy
from core.config import settings
from core.registry import FeatureRegistry
from harness import llm
from harness.policy import Mode, Policy
from harness.tools import Tool, ToolRegistry
from harness.tracing import Tracer

app = FastAPI(title=settings.app_name, version=settings.version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origins],
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

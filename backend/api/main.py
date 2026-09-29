"""Platform HTTP surface.

This file knows nothing about poultry. It discovers features, mounts them, and
exposes platform-level endpoints. Adding a feature does not change this file.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

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

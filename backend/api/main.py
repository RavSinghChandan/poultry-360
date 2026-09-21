"""HTTP surface. Thin on purpose — all the logic lives in the harness."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from data import rations
from domain.advisor import advise
from domain.hybrid import answer as hybrid_answer
from harness import llm

app = FastAPI(title="Poultry 360", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RationRequest(BaseModel):
    day: int = Field(..., ge=0, le=rations.MAX_DAY, description="Age in days since hatch")
    birds: int = Field(1, ge=1, description="Birds in the batch")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    birds: int = Field(1, ge=1)


class PlanRequest(BaseModel):
    day_from: int = Field(..., ge=0, le=rations.MAX_DAY)
    day_to: int = Field(..., ge=0, le=rations.MAX_DAY)
    birds: int = Field(..., ge=1)


def _respond(result) -> dict[str, Any]:
    """One response shape for every advice call, including failures."""
    body: dict[str, Any] = {
        "ok": result.ok,
        "stop_reason": result.stop_reason.value,
        "turns": result.turns,
        "citations": result.citations,
        "run_id": result.tracer.run_id,
    }
    if result.output.startswith(("ERROR:", "DENIED:")):
        body["ok"] = False
        body["error"] = result.output
        return body
    try:
        body["data"] = json.loads(result.output)
    except json.JSONDecodeError:
        body["ok"] = False
        body["error"] = result.output
    return body


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "dataset_version": rations.DATASET_VERSION,
        "sources": rations.SOURCES,
        "max_day": rations.MAX_DAY,
    }


@app.post("/api/ration")
def ration(req: RationRequest) -> dict[str, Any]:
    """The first feature: enter an age, get the exact ration."""
    return _respond(advise({"intent": "ration", "day": req.day, "birds": req.birds}))


@app.post("/api/plan")
def plan(req: PlanRequest) -> dict[str, Any]:
    """Total feed for a batch across a span of days."""
    return _respond(advise({
        "intent": "plan", "day_from": req.day_from,
        "day_to": req.day_to, "birds": req.birds,
    }))


@app.get("/api/schedule")
def schedule() -> dict[str, Any]:
    """The whole 0-42 day phase chart."""
    return _respond(advise({"intent": "schedule"}))


@app.post("/api/ask")
def ask(req: AskRequest) -> dict[str, Any]:
    """Free-text question, routed to the table, the model, or both."""
    return hybrid_answer(req.question, req.birds)


@app.get("/api/model-info")
def model_info() -> dict[str, Any]:
    """Whether a model is wired up, and what it is allowed to do."""
    return {
        "copy_generation": llm.status(),
        "routes": {
            "factual": "published table only; no model involved",
            "explanatory": "model only; no published number at stake",
            "diagnostic": "table first, then the model reasons over its figures",
        },
        "constraint": "the model never originates a nutrient value",
    }


@app.get("/api/trace/{run_id}")
def trace(run_id: str) -> dict[str, Any]:
    """Placeholder: traces are per-request today, persisted in a later feature."""
    return {"run_id": run_id, "note": "traces are returned inline with each response"}


# ── Static frontend ────────────────────────────────────────────────────────
_FRONTEND = Path(__file__).resolve().parent.parent.parent / "frontend"

if _FRONTEND.is_dir():
    @app.get("/{path:path}", include_in_schema=False)
    def serve(path: str):
        candidate = (_FRONTEND / path).resolve()
        if path and _FRONTEND in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_FRONTEND / "index.html")

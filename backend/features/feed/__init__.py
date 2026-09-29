"""Feature 1 — feed advice by bird age.

Self-contained: its data, logic, routes, tools and self-check all live here.
Nothing outside this package imports it, and it imports no other feature.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.contracts import FeatureInfo, ToolSpec
from harness.policy import Effect

from . import logic, rations
from .hybrid import answer as hybrid_answer

KEY = "feed"


class RationRequest(BaseModel):
    day: int = Field(..., ge=0, le=rations.MAX_DAY)
    birds: int = Field(1, ge=1)


class PlanRequest(BaseModel):
    day_from: int = Field(..., ge=0, le=rations.MAX_DAY)
    day_to: int = Field(..., ge=0, le=rations.MAX_DAY)
    birds: int = Field(..., ge=1)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)
    birds: int = Field(1, ge=1)


class FeedFeature:
    """Implements core.contracts.Feature."""

    def info(self) -> FeatureInfo:
        return FeatureInfo(
            key=KEY,
            names={
                "en": "Feed advice", "bn": "খাবারের পরামর্শ",
                "hi": "आहार सलाह", "bho": "दाना सलाह", "mai": "दाना सलाह",
            },
            summaries={
                "en": "How much to feed, by age and flock size.",
                "bn": "বয়স ও পালের আকার অনুযায়ী কতটা খাওয়াবেন।",
                "hi": "उम्र और झुंड के आकार से कितना दाना दें।",
                "bho": "उमिर आ झुंड के हिसाब से केतना दाना दीं।",
                "mai": "उमेर आ झुंडक हिसाबसँ केतेक दाना दिअ।",
            },
            name_en="Feed advice",
            name_hi="आहार सलाह",
            summary_en="Enter a bird's age, get the exact ration.",
            summary_hi="मुर्गी की उम्र डालें, पूरा आहार पाएँ।",
            version="1.0.0",
            status="live",
            icon="🌾",
            sources=rations.SOURCES,
        )

    def router(self) -> APIRouter:
        api = APIRouter()

        @api.post("/ration")
        def ration(req: RationRequest) -> dict[str, Any]:
            try:
                return {"ok": True, "data": logic.ration_for_day(req.day, req.birds)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @api.post("/plan")
        def plan(req: PlanRequest) -> dict[str, Any]:
            try:
                return {"ok": True, "data": logic.feed_plan(
                    req.day_from, req.day_to, req.birds)}
            except Exception as exc:
                return {"ok": False, "error": str(exc)}

        @api.get("/schedule")
        def schedule() -> dict[str, Any]:
            return {"ok": True, "data": logic.phase_schedule()}

        @api.post("/ask")
        def ask(req: AskRequest) -> dict[str, Any]:
            return hybrid_answer(req.question, req.birds)

        return api

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="feed_lookup_ration",
                run=lambda day, birds=1: json.dumps(logic.ration_for_day(day, birds)),
                effect=Effect.READ,
                description="Nutrient requirements and feed quantity for a bird of a given age.",
            ),
            ToolSpec(
                name="feed_phase_schedule",
                run=lambda: json.dumps(logic.phase_schedule()),
                effect=Effect.READ,
                description="The three feeding phases across the 0-42 day cycle.",
            ),
            ToolSpec(
                name="feed_plan",
                run=lambda day_from, day_to, birds: json.dumps(
                    logic.feed_plan(day_from, day_to, birds)),
                effect=Effect.READ,
                description="Total feed in kilograms for a batch across a span of days.",
            ),
        ]

    def selfcheck(self) -> list[str]:
        """Validate the published data before this feature is served."""
        problems: list[str] = []

        for day in range(0, rations.MAX_DAY + 1):
            hits = [p for p in rations.PHASES if p["days"][0] <= day <= p["days"][1]]
            if len(hits) != 1:
                problems.append(f"day {day} matches {len(hits)} phases, expected 1")
                break

        cp = [p["crude_protein_pct"] for p in rations.PHASES]
        if cp != sorted(cp, reverse=True):
            problems.append("crude protein does not fall with age")

        kcal = [p["energy_kcal_per_kg"] for p in rations.PHASES]
        if kcal != sorted(kcal):
            problems.append("energy does not rise with age")

        missing = [d for d in range(1, rations.MAX_DAY + 1)
                   if d not in rations.DAILY_INTAKE_G]
        if missing:
            problems.append(f"intake table missing days: {missing[:5]}")

        if not rations.SOURCES:
            problems.append("no source cited for the nutrient data")

        return problems


def feature() -> FeedFeature:
    """Factory the registry looks for."""
    return FeedFeature()

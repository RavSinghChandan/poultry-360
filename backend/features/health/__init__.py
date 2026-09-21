"""Feature 2 — flock health from a photo or video.

STATUS: planned. The routes exist and answer honestly that scoring is not
implemented yet; they never guess at a bird's health.

This package is here as the worked example of adding a feature: it was written
without editing a single line of features/feed, core/ or harness/. Copy this
shape for feature 3.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.contracts import FeatureInfo, ToolSpec
from harness.policy import Effect

KEY = "health"

# Signs a farmer can report in words today, before image scoring exists.
OBSERVABLE_SIGNS = {
    "huddling": {
        "en": "Birds huddling together",
        "hi": "मुर्गियाँ एक साथ सिमट रही हैं",
        "suggests_en": "Often too cold. Check brooder temperature first.",
        "suggests_hi": "अक्सर ठंड। पहले ब्रूडर का तापमान देखें।",
    },
    "panting": {
        "en": "Panting, wings held away from the body",
        "hi": "हाँफना, पंख शरीर से दूर",
        "suggests_en": "Heat stress. Check ventilation and water supply.",
        "suggests_hi": "गर्मी का तनाव। हवा और पानी की जाँच करें।",
    },
    "loose_droppings": {
        "en": "Loose or watery droppings",
        "hi": "पतली बीट",
        "suggests_en": "Many causes including feed change and infection. Consult a vet.",
        "suggests_hi": "कई कारण — दाना बदलना या संक्रमण। पशु चिकित्सक से मिलें।",
    },
    "not_eating": {
        "en": "Birds not coming to feed",
        "hi": "मुर्गियाँ दाना नहीं खा रहीं",
        "suggests_en": "Check feeder access and water first, then consult a vet.",
        "suggests_hi": "पहले दाना-पानी की पहुँच देखें, फिर पशु चिकित्सक से मिलें।",
    },
}

_VET_NOTE_EN = "This is not a diagnosis. Consult a veterinarian for sick birds."
_VET_NOTE_HI = "यह निदान नहीं है। बीमार पक्षियों के लिए पशु चिकित्सक से मिलें।"


class SignsRequest(BaseModel):
    signs: list[str] = Field(default_factory=list, max_length=10)
    day: int | None = Field(None, ge=0, le=60)


class HealthFeature:
    """Implements core.contracts.Feature."""

    def info(self) -> FeatureInfo:
        return FeatureInfo(
            key=KEY,
            name_en="Flock health",
            name_hi="झुंड का स्वास्थ्य",
            summary_en="Report what you see; photo scoring coming soon.",
            summary_hi="जो दिख रहा है बताएँ; फ़ोटो जाँच जल्द आएगी।",
            version="0.1.0",
            status="beta",
            icon="🩺",
            sources=["Observable signs only — not a veterinary diagnosis"],
        )

    def router(self) -> APIRouter:
        api = APIRouter()

        @api.get("/signs")
        def signs() -> dict[str, Any]:
            """The signs a farmer can report today."""
            return {"ok": True, "data": [
                {"key": k, **v} for k, v in OBSERVABLE_SIGNS.items()
            ]}

        @api.post("/assess")
        def assess(req: SignsRequest) -> dict[str, Any]:
            """Match reported signs to general guidance. Never a diagnosis."""
            unknown = [s for s in req.signs if s not in OBSERVABLE_SIGNS]
            matched = [
                {"key": s, **OBSERVABLE_SIGNS[s]}
                for s in req.signs if s in OBSERVABLE_SIGNS
            ]
            return {
                "ok": True,
                "matched": matched,
                "unknown_signs": unknown,
                "day": req.day,
                "note_en": _VET_NOTE_EN,
                "note_hi": _VET_NOTE_HI,
            }

        @api.post("/photo")
        def photo() -> dict[str, Any]:
            """Honest placeholder: scoring is not implemented."""
            return {
                "ok": False,
                "status": "not_implemented",
                "error_en": "Photo health scoring is not available yet.",
                "error_hi": "फ़ोटो से जाँच अभी उपलब्ध नहीं है।",
                "note_en": _VET_NOTE_EN,
            }

        return api

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="health_observable_signs",
                run=lambda: json.dumps(
                    [{"key": k, "en": v["en"]} for k, v in OBSERVABLE_SIGNS.items()]),
                effect=Effect.READ,
                description="Signs of poor flock health a farmer can report in words.",
            ),
        ]

    def selfcheck(self) -> list[str]:
        problems: list[str] = []
        for key, sign in OBSERVABLE_SIGNS.items():
            missing = [f for f in ("en", "hi", "suggests_en", "suggests_hi")
                       if not sign.get(f)]
            if missing:
                problems.append(f"sign {key!r} missing: {', '.join(missing)}")
        return problems


def feature() -> HealthFeature:
    return HealthFeature()

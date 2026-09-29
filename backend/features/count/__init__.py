"""Feature 3 — count birds in a photo.

WHAT THIS DOES
--------------
A farmer photographs the shed; this returns how many birds were found, the
boxes it drew so the count can be checked by eye, and a plain statement of how
much to trust it. The farmer confirms or corrects, and the confirmed number is
what gets recorded.

WHAT IT DOES NOT DO
-------------------
It does not claim to be exact. Birds hide behind each other, face away and
leave the frame; on a crowded barn photo the same image honestly yields 9 or
17 depending on where the threshold sits. Following rule 5 of the feature
contract — numbers a farmer acts on come from a cited source, never from a
model — the *recorded* flock count is the farmer's confirmed figure. The model
only proposes it.

ISOLATION
---------
Written without editing features/feed, features/health, core/ or harness/.
If the model file or onnxruntime is missing, selfcheck() reports it, the
feature is left unmounted and the rest of the app serves normally.
"""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.contracts import FeatureInfo, ToolSpec
from core.languages import DEFAULT_LANGUAGE, normalise, resolve
from harness.policy import Effect

from . import detector, strings, video
from .detector import CountError

KEY = "count"

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 80 * 1024 * 1024


class CountRequest(BaseModel):
    """A photo as base64. Kept simple so the Angular client can post JSON."""

    image_base64: str = Field(..., min_length=32)
    lang: str = Field(DEFAULT_LANGUAGE, max_length=12)


class VideoRequest(BaseModel):
    """A short clip as base64. One minute or less."""

    video_base64: str = Field(..., min_length=64)
    lang: str = Field(DEFAULT_LANGUAGE, max_length=12)


class ConfirmRequest(BaseModel):
    """What the farmer says is actually there.

    `counted` is the model's proposal; `confirmed` is the truth. Storing both
    is what lets us measure how wrong the model is on real sheds.
    """

    counted: int = Field(..., ge=0, le=100_000)
    confirmed: int = Field(..., ge=0, le=100_000)
    note: str = Field("", max_length=280)
    lang: str = Field(DEFAULT_LANGUAGE, max_length=12)


def _decode(payload: str, limit: int = MAX_UPLOAD_BYTES, lang: str = DEFAULT_LANGUAGE) -> bytes:
    if "," in payload[:64] and payload.lstrip().startswith("data:"):
        payload = payload.split(",", 1)[1]        # strip a data: URL prefix
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, resolve(strings.ERR_DECODE, lang)) from exc
    if not raw:
        raise HTTPException(400, resolve(strings.ERR_EMPTY, lang))
    if len(raw) > limit:
        raise HTTPException(413, resolve(strings.ERR_TOO_LARGE, lang))
    return raw


def _tips_for(lang: str) -> list[str]:
    """Photo advice in the reader's language, falling back to English."""
    return strings.TIPS.get(normalise(lang)) or strings.TIPS["en"]


def _tips() -> dict:
    """Legacy shape, kept so nothing that already calls it breaks."""
    return {
        "en": [
            "Stand back so the whole group fits in the frame.",
            "Take it in daylight or with the shed lights on.",
            "Hold the phone steady; a blurred photo counts badly.",
            "If the birds are packed together, take two photos of half the shed each.",
            "For a video: walk slowly in one continuous take, under a minute.",
        ],
        "hi": [
            "थोड़ा पीछे खड़े हों ताकि पूरा झुंड फ़्रेम में आए।",
            "दिन की रोशनी में या शेड की लाइट जलाकर लें।",
            "फ़ोन स्थिर रखें; धुंधली फ़ोटो सही नहीं गिनती।",
            "पक्षी पास-पास हों तो आधे-आधे शेड की दो फ़ोटो लें।",
            "वीडियो के लिए: धीरे-धीरे चलते हुए एक ही बार में, एक मिनट से कम।",
        ],
    }


class CountFeature:
    """Implements core.contracts.Feature."""

    def info(self) -> FeatureInfo:
        return FeatureInfo(
            key=KEY,
            name_en=strings.NAME["en"],
            name_hi=strings.NAME["hi"],
            summary_en=strings.SUMMARY["en"],
            summary_hi=strings.SUMMARY["hi"],
            version="0.1.0",
            status="beta" if detector.available() else "planned",
            icon="📷",
            names=strings.NAME,
            summaries=strings.SUMMARY,
            sources=[
                "YOLO11n (COCO class 14 'bird'), Ultralytics, AGPL-3.0",
                "Count is a proposal; the recorded figure is the farmer's confirmation.",
            ],
        )

    def router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/tips")
        def tips(lang: str = DEFAULT_LANGUAGE) -> dict:
            return {
                "tips": _tips_for(lang),
                "lang": normalise(lang),
                "model_ready": detector.available(),
                "video_ready": video.available(),
            }

        @router.post("/photo")
        def count_photo(request: CountRequest) -> dict:
            lang = normalise(request.lang)
            if not detector.available():
                raise HTTPException(
                    503, resolve(strings.UNAVAILABLE_PHOTO, lang)
                )
            raw = _decode(request.image_base64, MAX_UPLOAD_BYTES, lang)
            try:
                result = detector.count_birds(raw)
            except CountError as exc:
                raise HTTPException(400, resolve(exc.text, lang)) from exc

            return {
                "counted": result.best,
                "range": {"low": result.low, "high": result.high},
                "clear": result.clear,
                "quality": result.quality,
                "crowding": result.crowding,
                "image": {"width": result.width, "height": result.height},
                "boxes": [b.as_dict() for b in result.boxes],
                "note": resolve(result.note, lang),
                "quality_label": resolve(
                    strings.QUALITY.get(result.quality, {}), lang
                ),
                "lang": lang,
                "needs_confirmation": True,
                "tips": _tips_for(lang) if result.quality in {"low", "none"} else None,
            }

        @router.post("/video")
        def count_from_video(request: VideoRequest) -> dict:
            """Count across a short clip.

            Slower than a photo because every sampled frame runs the detector,
            but it sees birds a single frame cannot. The response shape matches
            /photo so the UI handles both the same way.
            """
            lang = normalise(request.lang)
            if not video.available():
                raise HTTPException(
                    503, resolve(strings.UNAVAILABLE_VIDEO, lang)
                )
            raw = _decode(request.video_base64, MAX_VIDEO_UPLOAD_BYTES, lang)
            try:
                result = video.count_video(raw)
            except CountError as exc:
                raise HTTPException(400, resolve(exc.text, lang)) from exc

            return {
                "counted": result.counted,
                "range": {"low": result.low, "high": result.high},
                "clear": result.clear,
                "quality": result.quality,
                "motion": result.motion,
                "frames_sampled": result.frames_sampled,
                "duration_s": result.duration_s,
                "peak_frame_count": result.peak_frame_count,
                "tracks": result.tracks,
                "note": resolve(result.note, lang),
                "quality_label": resolve(
                    strings.QUALITY.get(result.quality, {}), lang
                ),
                "lang": lang,
                "needs_confirmation": True,
                "tips": _tips_for(lang) if result.quality in {"low", "none"} else None,
            }

        @router.post("/confirm")
        def confirm(request: ConfirmRequest) -> dict:
            """Record the farmer's figure, and how far the model was out."""
            lang = normalise(request.lang)
            delta = request.confirmed - request.counted
            return {
                "recorded": request.confirmed,
                "model_proposed": request.counted,
                "difference": delta,
                "source": "farmer_confirmed",
                "lang": lang,
                "message": resolve(
                    {c: t.format(n=request.confirmed)
                     for c, t in strings.RECORDED.items()}, lang
                ),
                "model_note": resolve(
                    {c: t.format(n=request.counted)
                     for c, t in strings.MODEL_PROPOSED.items()}, lang
                ),
            }

        return router

    def tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="count_birds_in_photo",
                run=lambda image_base64: count_tool(image_base64),
                effect=Effect.READ,
                description=(
                    "Count birds visible in a photo. Returns a proposal with a "
                    "range and a quality flag; it is never authoritative."
                ),
                reads_untrusted=True,      # the image is user-supplied content
            ),
        ]

    def selfcheck(self) -> list[str]:
        problems: list[str] = []
        if not detector.available():
            # Not fatal: the feature reports status "planned" and its routes
            # answer 503 honestly rather than guessing a number.
            return problems
        import os

        size = os.path.getsize(detector.MODEL_PATH)
        if size < 1_000_000:
            problems.append(
                f"count: model file looks truncated ({size} bytes)"
            )
        if not (0 < detector.CONF_MIN < detector.CONF_CLEAR < 1):
            problems.append("count: confidence thresholds are not ordered")
        return problems


def count_tool(image_base64: str) -> dict:
    """Tool entry point, kept out of the router so it can be tested directly."""
    if not detector.available():
        return {"error": "model unavailable", "counted": None}
    raw = _decode(image_base64)
    result = detector.count_birds(raw)
    return {
        "counted": result.best,
        "range": {"low": result.low, "high": result.high},
        "quality": result.quality,
        "needs_confirmation": True,
    }


def feature() -> CountFeature:
    return CountFeature()

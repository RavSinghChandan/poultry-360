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
from harness.policy import Effect

from . import detector, video

KEY = "count"

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 80 * 1024 * 1024


class CountRequest(BaseModel):
    """A photo as base64. Kept simple so the Angular client can post JSON."""

    image_base64: str = Field(..., min_length=32)


class VideoRequest(BaseModel):
    """A short clip as base64. One minute or less."""

    video_base64: str = Field(..., min_length=64)


class ConfirmRequest(BaseModel):
    """What the farmer says is actually there.

    `counted` is the model's proposal; `confirmed` is the truth. Storing both
    is what lets us measure how wrong the model is on real sheds.
    """

    counted: int = Field(..., ge=0, le=100_000)
    confirmed: int = Field(..., ge=0, le=100_000)
    note: str = Field("", max_length=280)


def _decode(payload: str, limit: int = MAX_UPLOAD_BYTES, what: str = "image") -> bytes:
    if "," in payload[:64] and payload.lstrip().startswith("data:"):
        payload = payload.split(",", 1)[1]        # strip a data: URL prefix
    try:
        raw = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(400, f"The {what} could not be decoded.") from exc
    if not raw:
        raise HTTPException(400, f"The {what} was empty.")
    if len(raw) > limit:
        raise HTTPException(413, f"That {what} is too large. Please send a smaller one.")
    return raw


def _tips() -> dict:
    """How to take a photo that counts well. Farmer-facing, not technical."""
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
            name_en="Count the flock",
            name_hi="झुंड गिनें",
            summary_en="Photo or short video of the shed; check the count by eye.",
            summary_hi="शेड की फ़ोटो या छोटा वीडियो; गिनती आँख से जाँचें।",
            version="0.1.0",
            status="beta" if detector.available() else "planned",
            icon="📷",
            sources=[
                "YOLO11n (COCO class 14 'bird'), Ultralytics, AGPL-3.0",
                "Count is a proposal; the recorded figure is the farmer's confirmation.",
            ],
        )

    def router(self) -> APIRouter:
        router = APIRouter()

        @router.get("/tips")
        def tips() -> dict:
            return {
                "tips": _tips(),
                "model_ready": detector.available(),
                "video_ready": video.available(),
            }

        @router.post("/photo")
        def count_photo(request: CountRequest) -> dict:
            if not detector.available():
                raise HTTPException(
                    503,
                    "Photo counting is not available on this server. "
                    "Enter the number by hand.",
                )
            raw = _decode(request.image_base64)
            try:
                result = detector.count_birds(raw)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

            return {
                "counted": result.best,
                "range": {"low": result.low, "high": result.high},
                "clear": result.clear,
                "quality": result.quality,
                "crowding": result.crowding,
                "image": {"width": result.width, "height": result.height},
                "boxes": [b.as_dict() for b in result.boxes],
                "note": {"en": result.note_en, "hi": result.note_hi},
                "needs_confirmation": True,
                "tips": _tips() if result.quality in {"low", "none"} else None,
            }

        @router.post("/video")
        def count_from_video(request: VideoRequest) -> dict:
            """Count across a short clip.

            Slower than a photo because every sampled frame runs the detector,
            but it sees birds a single frame cannot. The response shape matches
            /photo so the UI handles both the same way.
            """
            if not video.available():
                raise HTTPException(
                    503,
                    "Video counting is not available on this server. "
                    "Send a photo instead, or enter the number by hand.",
                )
            raw = _decode(
                request.video_base64, MAX_VIDEO_UPLOAD_BYTES, "video"
            )
            try:
                result = video.count_video(raw)
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

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
                "note": {"en": result.note_en, "hi": result.note_hi},
                "needs_confirmation": True,
                "tips": _tips() if result.quality in {"low", "none"} else None,
            }

        @router.post("/confirm")
        def confirm(request: ConfirmRequest) -> dict:
            """Record the farmer's figure, and how far the model was out."""
            delta = request.confirmed - request.counted
            return {
                "recorded": request.confirmed,
                "model_proposed": request.counted,
                "difference": delta,
                "source": "farmer_confirmed",
                "message": {
                    "en": f"Recorded {request.confirmed} birds.",
                    "hi": f"{request.confirmed} पक्षी दर्ज किए गए।",
                },
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

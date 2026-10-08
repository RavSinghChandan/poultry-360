"""Tests for feature 3 — counting birds in a photo.

The detector is a model, so these never assert an exact count on a real photo:
that test would fail on any model update and get deleted. They assert the
things that must hold whatever the model says — the contract, the error paths,
the confidence arithmetic, and above all that the feature never presents a
count as certain.
"""
import base64
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app, features
from features.count import detector
from features.count.detector import Box, CountResult

client = TestClient(app)

pytestmark = pytest.mark.skipif(
    not detector.available(), reason="detector dependencies not installed"
)


def _png(width=320, height=240, colour=(200, 200, 200)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buf, format="PNG")
    return buf.getvalue()


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def _has_devanagari(text: str) -> bool:
    return any("\u0900" <= ch <= "\u097F" for ch in text)


def _has_bengali(text: str) -> bool:
    return any("\u0980" <= ch <= "\u09FF" for ch in text)


def result(clear, total, crowding=0.0, boxes=None):
    return CountResult(
        clear=clear, total=total, boxes=boxes or [], width=640, height=480,
        crowding=crowding, note={},
    )


# --- the feature is registered and isolated -----------------------------

def test_count_feature_loaded():
    assert "count" in features.loaded


def test_count_feature_is_healthy():
    assert features.loaded["count"].healthy


def test_count_does_not_break_other_features():
    for key in ("feed", "health"):
        assert key in features.loaded, f"{key} must still load"
        assert features.loaded[key].healthy


def test_count_appears_in_the_feature_list():
    keys = {f["key"] for f in client.get("/api/features").json()["features"]}
    assert "count" in keys


def test_info_is_bilingual():
    info = features.loaded["count"].info
    assert info.name_hi and info.summary_hi


def test_sources_are_cited():
    assert features.loaded["count"].info.sources


# --- quality never overstates -------------------------------------------

def test_no_detections_is_reported_as_none():
    assert result(0, 0).quality == "none"


def test_all_clear_and_uncrowded_is_high():
    assert result(10, 10, crowding=0.0).quality == "high"


def test_many_uncertain_detections_lowers_quality():
    assert result(2, 10, crowding=0.0).quality == "low"


def test_crowded_large_flock_is_low_quality():
    """Packed birds hide each other, so the count is probably an undercount."""
    assert result(8, 8, crowding=0.9).quality == "low"


def test_crowded_small_group_is_not_treated_as_occluded():
    """Three hens filling the frame overlap, and the count is still right.

    This was a real bug: any overlap marked every photo untrustworthy.
    """
    assert result(3, 3, crowding=1.0).quality != "low"


def test_range_brackets_the_estimate():
    r = result(4, 9)
    assert r.low <= r.best <= r.high
    assert (r.low, r.high) == (4, 9)


# --- the API contract ---------------------------------------------------

def test_photo_endpoint_always_asks_for_confirmation():
    body = client.post("/api/count/photo", json={"image_base64": _b64(_png())}).json()
    assert body["needs_confirmation"] is True, "a count must never be presented as final"


def test_photo_endpoint_returns_boxes_for_visual_checking():
    body = client.post("/api/count/photo", json={"image_base64": _b64(_png())}).json()
    assert "boxes" in body and isinstance(body["boxes"], list)


def test_photo_endpoint_returns_a_range_not_just_a_number():
    body = client.post("/api/count/photo", json={"image_base64": _b64(_png())}).json()
    assert set(body["range"]) == {"low", "high"}


def test_note_comes_back_in_the_requested_language():
    """The server resolves the language; the client gets one plain string."""
    bn = client.post("/api/count/photo",
                     json={"image_base64": _b64(_png()), "lang": "bn"}).json()
    en = client.post("/api/count/photo",
                     json={"image_base64": _b64(_png()), "lang": "en"}).json()
    assert isinstance(bn["note"], str) and bn["note"]
    assert bn["note"] != en["note"], "bn and en must differ"
    assert _has_bengali(bn["note"])


def test_language_defaults_to_english():
    body = client.post("/api/count/photo", json={"image_base64": _b64(_png())}).json()
    assert body["lang"] == "en"


def test_unknown_language_falls_back_rather_than_failing():
    body = client.post("/api/count/photo",
                       json={"image_base64": _b64(_png()), "lang": "zz"}).json()
    assert body["lang"] == "en"


def test_bhojpuri_falls_back_to_hindi_when_untranslated():
    from core.languages import resolve

    assert resolve({"en": "x", "hi": "हिन्दी"}, "bho") == "हिन्दी"


def test_blank_image_finds_nothing_and_says_so():
    body = client.post("/api/count/photo", json={"image_base64": _b64(_png())}).json()
    assert body["counted"] == 0
    assert body["quality"] == "none"


def test_tips_endpoint_returns_the_requested_language():
    bn = client.get("/api/count/tips?lang=bn").json()
    en = client.get("/api/count/tips?lang=en").json()
    assert bn["tips"] and en["tips"]
    assert bn["tips"] != en["tips"]
    assert bn["lang"] == "bn"


# --- bad input ----------------------------------------------------------

def test_rejects_unreadable_base64():
    assert client.post("/api/count/photo", json={"image_base64": "!" * 40}).status_code == 400


def test_rejects_a_file_that_is_not_an_image():
    payload = _b64(b"this is not an image" * 5)
    assert client.post("/api/count/photo", json={"image_base64": payload}).status_code == 400


def test_rejects_a_tiny_image():
    assert client.post("/api/count/photo", json={"image_base64": _b64(_png(16, 16))}).status_code == 400


def test_accepts_a_data_url_prefix():
    payload = "data:image/png;base64," + _b64(_png())
    assert client.post("/api/count/photo", json={"image_base64": payload}).status_code == 200


# --- confirmation is what gets recorded ---------------------------------

def test_confirmed_number_is_what_is_recorded():
    body = client.post("/api/count/confirm", json={"counted": 12, "confirmed": 15}).json()
    assert body["recorded"] == 15
    assert body["source"] == "farmer_confirmed"


def test_confirmation_records_how_far_the_model_was_out():
    body = client.post("/api/count/confirm", json={"counted": 12, "confirmed": 15}).json()
    assert body["difference"] == 3


def test_confirmation_handles_an_overcount():
    body = client.post("/api/count/confirm", json={"counted": 20, "confirmed": 18}).json()
    assert body["difference"] == -2


def test_confirmation_rejects_a_negative_count():
    assert client.post("/api/count/confirm", json={"counted": 1, "confirmed": -5}).status_code == 422


# --- the tool declares itself honestly ----------------------------------

def test_tool_reads_untrusted_content():
    """An uploaded photo is user-supplied, so the harness must know."""
    tool = next(t for t in features.loaded["count"].feature.tools()
                if t.name == "count_birds_in_photo")
    assert tool.reads_untrusted is True


def test_tool_is_read_only():
    from harness.policy import Effect

    tool = next(t for t in features.loaded["count"].feature.tools()
                if t.name == "count_birds_in_photo")
    assert tool.effect is Effect.READ


# --- errors must be readable by a farmer who reads no English -----------

def _has_devanagari(text: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in text)


def test_errors_are_in_the_readers_language():
    """A farmer who reads only Bengali must understand a failure."""
    payload = _b64(b"not an image at all" * 5)
    detail = client.post(
        "/api/count/photo", json={"image_base64": payload, "lang": "bn"}
    ).json()["detail"]
    assert _has_bengali(detail), f"not Bengali: {detail!r}"


def test_errors_translate_to_hindi_too():
    payload = _b64(b"not an image at all" * 5)
    detail = client.post(
        "/api/count/photo", json={"image_base64": payload, "lang": "hi"}
    ).json()["detail"]
    assert _has_devanagari(detail), f"not Devanagari: {detail!r}"


def test_tiny_image_error_is_translated():
    detail = client.post(
        "/api/count/photo", json={"image_base64": _b64(_png(16, 16)), "lang": "bn"}
    ).json()["detail"]
    assert _has_bengali(detail), f"not Bengali: {detail!r}"


def test_undecodable_payload_error_is_translated():
    detail = client.post(
        "/api/count/photo", json={"image_base64": "!" * 40, "lang": "bn"}
    ).json()["detail"]
    assert _has_bengali(detail), f"not Bengali: {detail!r}"

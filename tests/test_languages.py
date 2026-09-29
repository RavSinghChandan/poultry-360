"""The language layer.

A farmer should never see an empty screen because a translation is missing,
and should never see a language they cannot read when one they can is
available. These pin both.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from api.main import app, features
from core.languages import (DEFAULT_LANGUAGE, LANGUAGES, catalogue,
                            missing_languages, normalise, resolve)

client = TestClient(app)


# --- the catalogue ------------------------------------------------------

def test_bengali_is_the_default():
    assert DEFAULT_LANGUAGE == "bn"


def test_the_promised_languages_are_present():
    for code in ("bn", "hi", "bho", "mai", "en"):
        assert code in LANGUAGES


def test_every_language_declares_a_native_name():
    for lang in LANGUAGES.values():
        assert lang.name_native.strip()


def test_every_fallback_chain_terminates_at_english():
    """A cycle here would hang resolve(), so this is a real safety check."""
    for code in LANGUAGES:
        seen, at = set(), code
        while at:
            assert at not in seen, f"fallback cycle at {code}"
            seen.add(at)
            at = LANGUAGES[at].fallback
        assert "en" in seen


def test_catalogue_marks_exactly_one_default():
    assert sum(1 for entry in catalogue() if entry["default"]) == 1


# --- normalising what a client sends ------------------------------------

@pytest.mark.parametrize("given,expected", [
    ("bn", "bn"), ("BN", "bn"), ("bn-IN", "bn"), ("bn_IN", "bn"),
    ("hi", "hi"), ("en-GB", "en"),
])
def test_normalise_accepts_real_world_codes(given, expected):
    assert normalise(given) == expected


@pytest.mark.parametrize("given", ["", None, "zz", "klingon", "  "])
def test_unknown_codes_fall_back_to_the_default(given):
    assert normalise(given) == DEFAULT_LANGUAGE


# --- resolving a Text ---------------------------------------------------

def test_exact_language_wins():
    assert resolve({"bn": "বাংলা", "en": "English"}, "bn") == "বাংলা"


def test_bhojpuri_falls_back_to_hindi_not_english():
    """A Bhojpuri speaker reads Hindi far more easily than English."""
    assert resolve({"hi": "हिन्दी", "en": "English"}, "bho") == "हिन्दी"


def test_maithili_falls_back_to_hindi_not_english():
    assert resolve({"hi": "हिन्दी", "en": "English"}, "mai") == "हिन्दी"


def test_bengali_falls_back_to_english_when_missing():
    assert resolve({"en": "English"}, "bn") == "English"


def test_empty_text_resolves_to_empty_rather_than_raising():
    assert resolve({}, "bn") == ""


def test_a_text_with_no_english_still_returns_something():
    """Better a language the reader may not know than a blank screen."""
    assert resolve({"bn": "বাংলা"}, "hi") == "বাংলা"


def test_missing_languages_reports_gaps():
    assert missing_languages({"bn": "x"}, ("en", "bn")) == ["en"]


# --- the endpoint -------------------------------------------------------

def test_languages_endpoint_lists_them_all():
    body = client.get("/api/languages").json()
    assert {entry["code"] for entry in body["languages"]} >= {"bn", "hi", "bho", "mai", "en"}
    assert body["default"] == "bn"


def test_feature_menu_is_translated():
    bn = client.get("/api/features?lang=bn").json()["features"]
    en = client.get("/api/features?lang=en").json()["features"]
    by_key_bn = {f["key"]: f["name"] for f in bn}
    by_key_en = {f["key"]: f["name"] for f in en}
    for key in by_key_bn:
        assert by_key_bn[key] != by_key_en[key], f"{key} not translated"


def test_feature_menu_defaults_to_bengali():
    assert client.get("/api/features").json()["lang"] == "bn"


def test_every_feature_has_a_name_in_every_language():
    """A missing name would render an unlabelled tab."""
    for code in LANGUAGES:
        for feature in client.get(f"/api/features?lang={code}").json()["features"]:
            assert feature["name"].strip(), f"{feature['key']} has no name in {code}"


def test_legacy_fields_still_present_for_unmigrated_clients():
    feature = client.get("/api/features").json()["features"][0]
    assert "name_en" in feature and "name_hi" in feature

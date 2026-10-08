"""The app's words: one file per language, English complete, nothing missing.

A key the code uses but English lacks shows up on screen as a raw key; a
placeholder dropped in translation shows a farmer a sentence with no number.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
I18N = ROOT / "frontend/src/assets/i18n"
APP = ROOT / "frontend/src/app"

pytestmark = pytest.mark.skipif(not I18N.exists(), reason="frontend sources not present")


def load(code: str) -> dict:
    return json.loads((I18N / f"{code}.json").read_text())


def config() -> dict:
    return json.loads((I18N / "languages.json").read_text())


def test_english_is_the_default_and_listed_first():
    cfg = config()
    assert cfg["default"] == "en"
    assert cfg["languages"][0]["code"] == "en"


def test_every_enabled_language_has_a_file():
    for code in config()["enabled"]:
        assert (I18N / f"{code}.json").exists(), code


def test_every_fallback_chain_ends_at_english():
    by_code = {lang["code"]: lang for lang in config()["languages"]}
    for code in by_code:
        seen, at = set(), code
        while at:
            assert at not in seen, f"fallback cycle at {code}"
            seen.add(at)
            at = by_code[at]["fallback"]
        assert "en" in seen


def test_no_language_has_keys_english_lacks():
    en = set(load("en"))
    for code in config()["enabled"]:
        assert set(load(code)) <= en, f"{code}: {set(load(code)) - en}"


def test_full_languages_cover_every_english_key():
    en = set(load("en"))
    for code in ("hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "or"):
        assert set(load(code)) == en, f"{code} missing {en - set(load(code))}"


def test_placeholders_survive_translation():
    en = load("en")
    for code in config()["enabled"]:
        for key, text in load(code).items():
            for ph in re.findall(r"\{\w+\}", en[key]):
                assert ph in text, f"{code}:{key} lost {ph}"


def test_every_literal_key_in_the_code_exists_in_english():
    en = set(load("en"))
    used = set()
    for path in APP.rglob("*.ts"):
        used |= set(re.findall(r"t\(\)\('([a-zA-Z0-9_.]+)'\)", path.read_text()))
    assert used, "no keys found; the pattern no longer matches the code"
    assert used <= en, f"missing in en.json: {sorted(used - en)}"


def test_dynamic_key_families_are_complete():
    en = set(load("en"))
    families = {
        "phase.": ["starter", "grower", "finisher", "starter.note", "grower.note", "finisher.note"],
        "count.q.": ["high", "medium", "low", "none"],
        "count.tip.": ["1", "2", "3", "4", "5"],
        "nav.": ["today", "count", "feed", "health", "diary"],
    }
    for prefix, rest in families.items():
        for r in rest:
            assert prefix + r in en, prefix + r

"""Tests for the hybrid path.

The question these must answer: can the model ever change a number a farmer
acts on? The answer must be no, on every route and every failure mode.
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from domain.hybrid import answer
from domain.router import Route, classify, extract_day
from harness import llm


# ── routing ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text,route", [
    ("day 17 ration for 4000 birds", Route.FACTUAL),
    ("17 din", Route.FACTUAL),
    ("what should a day 30 bird eat", Route.FACTUAL),
    ("why does protein drop after day 14?", Route.EXPLANATORY),
    ("प्रोटीन क्यों कम होता है", Route.EXPLANATORY),
    ("my birds look weak at day 20", Route.DIAGNOSTIC),
    ("birds not gaining weight at day 30", Route.DIAGNOSTIC),
    ("20 दिन की मुर्गी कमज़ोर है", Route.DIAGNOSTIC),
])
def test_questions_route_correctly(text, route):
    assert classify(text) is route


@pytest.mark.parametrize("text,day", [
    ("day 17 ration", 17), ("17 din", 17), ("दिन 5 का आहार", 5),
    ("no age here", None), ("30 days old", 30),
])
def test_day_is_extracted_from_free_text(text, day):
    assert extract_day(text) == day


# ── the guarantee: the model cannot change a number ────────────────────────

def test_factual_route_never_calls_the_model():
    """A question with one correct answer must not reach an LLM at all."""
    with patch.object(llm, "ask", side_effect=AssertionError("model was called")):
        r = answer("day 17 ration", birds=100)
    assert r["route"] == "factual"
    assert r["model_used"] is False
    assert r["ration"]["crude_protein_pct"] == 20.0


def test_diagnostic_gives_the_model_the_table_figures_as_facts():
    """The model must receive the numbers, not be asked to supply them."""
    seen = {}

    def fake_ask(system, user, temperature=0.3):
        seen["system"] = system
        seen["user"] = user
        return "Feed looks low. Raise it to 20% protein."

    with patch.object(llm, "is_enabled", return_value=True), \
         patch.object(llm, "ask", fake_ask):
        r = answer("my birds look weak at day 20", birds=500)

    assert r["route"] == "diagnostic"
    assert r["model_used"] is True
    assert "FACTS" in seen["user"]
    assert "20.0%" in seen["user"]          # the table's figure was supplied
    assert "NEVER state" in seen["system"]  # and the constraint was stated


def test_an_invented_number_is_flagged_not_hidden():
    """If the model states a figure we did not supply, the farmer is told."""
    with patch.object(llm, "is_enabled", return_value=True), \
         patch.object(llm, "ask", return_value="Give them 26% protein now."):
        r = answer("my birds look weak at day 20", birds=10)

    assert r["model_used"] is True
    assert r["unverified_numbers"] == ["26"]
    assert "not from the published table" in r["warning"]


def test_a_reply_quoting_only_table_figures_is_not_flagged():
    with patch.object(llm, "is_enabled", return_value=True), \
         patch.object(llm, "ask", return_value="Target is 20.0% protein, 3100 kcal/kg."):
        r = answer("my birds look weak at day 20", birds=10)
    assert "unverified_numbers" not in r


def test_the_ration_is_returned_even_when_the_model_answers():
    """The authoritative numbers travel with every diagnostic reply."""
    with patch.object(llm, "is_enabled", return_value=True), \
         patch.object(llm, "ask", return_value="Check your feed supplier."):
        r = answer("birds not gaining weight at day 30", birds=10)
    assert r["ration"]["crude_protein_pct"] == 18.0
    assert r["source"]


# ── degradation ────────────────────────────────────────────────────────────

def test_without_a_key_the_app_still_answers_from_the_table():
    with patch.object(llm, "is_enabled", return_value=False):
        r = answer("my birds look weak at day 20", birds=10)
    assert r["ok"] is True
    assert r["model_available"] is False
    assert "20.0%" in r["answer"]


def test_a_model_failure_does_not_fail_the_request():
    with patch.object(llm, "is_enabled", return_value=True), \
         patch.object(llm, "ask", return_value=None):
        r = answer("why does protein drop after day 14", birds=10)
    assert r["ok"] is True
    assert r["model_available"] is False


def test_out_of_range_day_is_refused_before_any_model_call():
    with patch.object(llm, "ask", side_effect=AssertionError("model was called")):
        r = answer("my birds look weak at day 99", birds=10)
    assert r["ok"] is False
    assert "0-42" in r["error"]


def test_factual_question_without_an_age_asks_for_one():
    r = answer("what should I feed them", birds=10)
    assert r["ok"] is False
    assert "age" in r["error"].lower() or "उम्र" in r["error"]


# ── the verifier itself ────────────────────────────────────────────────────

@pytest.mark.parametrize("reply,allowed,flagged", [
    ("20% protein", {"20.0"}, []),
    ("20.0% protein", {"20"}, []),
    ("22% protein", {"20.0"}, ["22"]),
    ("3100 kcal and 20%", {"20.0", "3100"}, []),
    ("no numbers here", {"20.0"}, []),
    ("प्रोटीन 25 प्रतिशत", {"20.0"}, ["25"]),
])
def test_number_verifier(reply, allowed, flagged):
    _, invented = llm.verify_no_invented_numbers(reply, allowed)
    assert invented == flagged

"""Tests for the poultry harness.

Grouped the way the failure taxonomy is: data correctness, domain arithmetic,
authority, budgets, and the seams between them.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from features.feed import rations
from features.feed import logic as feed
from features.feed.advisor_compat import advise, build_registry
from harness.agent import Agent, StopReason
from harness.policy import Effect, Mode, Policy
from harness.tools import Tool, ToolError, ToolRegistry
from harness.tracing import EventType, Tracer


# ── the published data ─────────────────────────────────────────────────────

def test_phases_cover_every_day_with_no_gap_or_overlap():
    """Every day 0-42 belongs to exactly one phase."""
    for day in range(0, rations.MAX_DAY + 1):
        matches = [p for p in rations.PHASES
                   if p["days"][0] <= day <= p["days"][1]]
        assert len(matches) == 1, f"day {day} matched {len(matches)} phases"


def test_protein_falls_as_the_bird_ages():
    """Starter > grower > finisher. If this inverts, the table is wrong."""
    cp = [p["crude_protein_pct"] for p in rations.PHASES]
    assert cp == sorted(cp, reverse=True)


def test_energy_rises_as_the_bird_ages():
    kcal = [p["energy_kcal_per_kg"] for p in rations.PHASES]
    assert kcal == sorted(kcal)


@pytest.mark.parametrize("bad", [-1, 43, 100, "x", 3.5, None, True])
def test_day_outside_the_tables_is_refused(bad):
    """No guessing past the published range, and a bool is not a day."""
    with pytest.raises(rations.DayOutOfRange):
        rations.phase_for_day(bad)


def test_intake_never_decreases_with_age():
    prev = -1
    for day in range(1, rations.MAX_DAY + 1):
        g = rations.intake_g_for_day(day)
        assert g >= prev, f"intake dropped at day {day}"
        prev = g


# ── the domain arithmetic ──────────────────────────────────────────────────

def test_ration_scales_linearly_with_flock_size():
    one = feed.ration_for_day(20, birds=1)
    many = feed.ration_for_day(20, birds=1000)
    assert many["feed_total_kg"] == pytest.approx(one["feed_per_bird_g"] * 1000 / 1000.0)
    assert many["crude_protein_pct"] == one["crude_protein_pct"]   # a % does not scale


def test_ration_carries_its_source():
    r = feed.ration_for_day(10)
    assert r["source"] and all(isinstance(s, str) for s in r["source"])
    assert r["dataset_version"] == rations.DATASET_VERSION


@pytest.mark.parametrize("birds", [0, -5, True, 2.5, "ten"])
def test_bad_bird_count_is_refused(birds):
    with pytest.raises(ToolError):
        feed.ration_for_day(10, birds=birds)


def test_feed_plan_sums_to_the_daily_figures():
    """The plan total must equal the sum of its days — no rounding drift."""
    plan = feed.feed_plan(1, 42, 100)
    by_hand = sum(rations.intake_g_for_day(d) * 100 for d in range(1, 43)) / 1000.0
    assert plan["total_feed_kg"] == pytest.approx(by_hand, abs=0.01)


def test_feed_plan_phases_sum_to_the_total():
    plan = feed.feed_plan(0, 42, 500)
    assert sum(plan["by_phase_kg"].values()) == pytest.approx(
        plan["total_feed_kg"], abs=0.05
    )


def test_reversed_span_is_refused():
    with pytest.raises(ToolError):
        feed.feed_plan(30, 10, 100)


# ── authority ──────────────────────────────────────────────────────────────

def test_read_is_allowed_even_in_the_strictest_mode():
    v = Policy(mode=Mode.READ_ONLY).check("lookup_ration", Effect.READ, {})
    assert v.allowed


def test_write_is_denied_in_an_advice_only_session():
    v = Policy(mode=Mode.READ_ONLY).check("save_batch", Effect.WRITE, {})
    assert not v.allowed and "advice-only" in v.reason


def test_destructive_needs_a_human_even_when_autonomous():
    v = Policy(mode=Mode.AUTONOMOUS).check("order_feed", Effect.DESTRUCTIVE, {})
    assert not v.allowed and v.asked


def test_destructive_proceeds_once_confirmed():
    p = Policy(mode=Mode.AUTONOMOUS, confirm=lambda n, a: True)
    assert p.check("order_feed", Effect.DESTRUCTIVE, {}).allowed


def test_denied_tool_returns_text_not_an_exception():
    """A denial is information for the model, not a crash."""
    reg = ToolRegistry(policy=Policy(mode=Mode.READ_ONLY), tracer=Tracer())
    reg.register(Tool(name="save", run=lambda: "saved", effect=Effect.WRITE))
    out = reg.execute("save", {})
    assert out.startswith("DENIED:")


def test_untrusted_content_withdraws_destructive_tools():
    """After reading outside content, destruction is off the table."""
    reg = ToolRegistry(policy=Policy(mode=Mode.AUTONOMOUS))
    reg.register(Tool(name="read_photo", run=lambda: "a caption",
                      effect=Effect.READ, reads_untrusted=True))
    reg.register(Tool(name="order_feed", run=lambda: "ordered",
                      effect=Effect.DESTRUCTIVE))
    assert any(t.name == "order_feed" for t in reg.available())
    reg.execute("read_photo", {})
    assert all(t.name != "order_feed" for t in reg.available())


# ── the loop ───────────────────────────────────────────────────────────────

def test_unknown_tool_is_reported_not_raised():
    reg = ToolRegistry(policy=Policy(), tracer=Tracer())
    out = reg.execute("does_not_exist", {})
    assert out.startswith("ERROR:") and "does_not_exist" in out


def test_turn_budget_stops_a_model_that_never_finishes():
    """A model that only ever calls tools must still terminate."""
    reg = build_registry()
    calls = {"n": 0}

    def never_done(messages):
        calls["n"] += 1
        return {"type": "tool", "name": "phase_schedule", "args": {}}

    agent = Agent(model=never_done, tools=reg, max_turns=3, repeat_limit=99)
    result = agent.run("{}")
    assert result.stop_reason is StopReason.TURN_BUDGET
    assert not result.ok                      # a budget stop is never success
    assert calls["n"] <= 3


def test_repeated_identical_call_trips_the_no_progress_guard():
    reg = build_registry()
    agent = Agent(
        model=lambda m: {"type": "tool", "name": "phase_schedule", "args": {}},
        tools=reg, max_turns=50, repeat_limit=2,
    )
    result = agent.run("{}")
    assert result.stop_reason is StopReason.NO_PROGRESS


def test_a_raising_model_does_not_take_the_process_down():
    def broken(messages):
        raise RuntimeError("model unavailable")

    agent = Agent(model=broken, tools=build_registry())
    result = agent.run("{}")
    assert result.stop_reason is StopReason.MODEL_ERROR
    assert not result.ok


# ── end to end ─────────────────────────────────────────────────────────────

def test_advice_run_completes_and_cites_its_tool():
    r = advise({"intent": "ration", "day": 17, "birds": 4000})
    assert r.ok
    assert r.citations == ["lookup_ration"]
    data = json.loads(r.output)
    assert data["crude_protein_pct"] == 20.0
    assert data["phase"] == "grower"


def test_same_question_gives_the_same_answer_every_time():
    """No randomness anywhere: a farmer asking twice must not get two answers."""
    outs = {advise({"intent": "ration", "day": 23, "birds": 800}).output
            for _ in range(5)}
    assert len(outs) == 1


def test_every_run_leaves_a_trace():
    r = advise({"intent": "ration", "day": 5})
    kinds = {e.type for e in r.tracer.events}
    assert EventType.RUN_START in kinds
    assert EventType.TOOL_CALL in kinds
    assert EventType.RUN_END in kinds


def test_out_of_range_day_reaches_the_farmer_as_a_readable_error():
    r = advise({"intent": "ration", "day": 60})
    assert r.output.startswith("ERROR:")
    assert "0-42" in r.output

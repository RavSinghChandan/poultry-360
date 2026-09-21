"""Wires the poultry tools into a harness and runs the advice loop.

The model here is a deterministic planner, not an LLM. That is deliberate for
feature 1: the question "what should a 17-day bird eat?" has one correct answer
in the published tables, so a model choosing freely could only make it worse.

The harness is still the real thing — budgets, policy, tracing, tool dispatch —
so when feature 2 (photo/video health scoring) arrives and genuinely needs a
model's judgement, it plugs into the same loop with nothing else to change.
"""
from __future__ import annotations

import json
from typing import Any

from data import rations
from domain import feed
from harness.agent import Agent, RunResult
from harness.policy import Effect, Mode, Policy
from harness.tools import Tool, ToolRegistry
from harness.tracing import Tracer


def build_registry(policy: Policy | None = None, tracer: Tracer | None = None) -> ToolRegistry:
    """Every tool the advisor can reach, each carrying its own effect."""
    registry = ToolRegistry(policy=policy or Policy(mode=Mode.READ_ONLY), tracer=tracer)

    registry.register(Tool(
        name="lookup_ration",
        run=lambda day, birds=1: json.dumps(feed.ration_for_day(day, birds)),
        effect=Effect.READ,
        description="Nutrient requirements and feed quantity for a bird of a given age.",
    ))
    registry.register(Tool(
        name="phase_schedule",
        run=lambda: json.dumps(feed.phase_schedule()),
        effect=Effect.READ,
        description="The three feeding phases across the 0-42 day cycle.",
    ))
    registry.register(Tool(
        name="feed_plan",
        run=lambda day_from, day_to, birds: json.dumps(
            feed.feed_plan(day_from, day_to, birds)
        ),
        effect=Effect.READ,
        description="Total feed in kilograms for a batch across a span of days.",
    ))
    return registry


def _planner(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """A deterministic 'model': read the task, call one tool, then report.

    Returns the same shape an LLM adapter would, so swapping in a real model
    later changes this function and nothing else.
    """
    # Has a tool already answered? Then finish.
    for m in reversed(messages):
        if m["role"] == "user" and m["content"].startswith("[result]"):
            payload = m["content"][len("[result] "):]
            if payload.startswith(("ERROR:", "DENIED:")):
                return {"type": "final", "content": payload}
            return {"type": "final", "content": payload}

    task = json.loads(messages[1]["content"])
    intent = task.get("intent", "ration")

    if intent == "plan":
        return {"type": "tool", "name": "feed_plan", "args": {
            "day_from": task["day_from"], "day_to": task["day_to"],
            "birds": task["birds"],
        }}
    if intent == "schedule":
        return {"type": "tool", "name": "phase_schedule", "args": {}}
    return {"type": "tool", "name": "lookup_ration", "args": {
        "day": task["day"], "birds": task.get("birds", 1),
    }}


def advise(task: dict[str, Any], policy: Policy | None = None) -> RunResult:
    """Run one advice request through the full harness."""
    tracer = Tracer()
    registry = build_registry(policy=policy, tracer=tracer)
    agent = Agent(
        model=_planner,
        tools=registry,
        system_prompt=(
            "You give broiler feeding advice from published standards. "
            "Never invent a nutrient value."
        ),
    )
    return agent.run(json.dumps(task))

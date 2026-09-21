"""Agent-loop entry point for the feed feature.

Kept as a thin module so the harness loop can be exercised against this
feature's tools without the API layer. The platform's own registry is the
production path; this is the unit-test seam.
"""
from __future__ import annotations

import json
from typing import Any

from harness.agent import Agent, RunResult
from harness.policy import Mode, Policy
from harness.tools import Tool, ToolRegistry
from harness.tracing import Tracer

from . import logic


def build_registry(policy: Policy | None = None, tracer: Tracer | None = None) -> ToolRegistry:
    registry = ToolRegistry(policy=policy or Policy(mode=Mode.READ_ONLY), tracer=tracer)
    registry.register(Tool(
        name="lookup_ration",
        run=lambda day, birds=1: json.dumps(logic.ration_for_day(day, birds)),
        description="Ration for a bird of a given age."))
    registry.register(Tool(
        name="phase_schedule",
        run=lambda: json.dumps(logic.phase_schedule()),
        description="The three feeding phases."))
    registry.register(Tool(
        name="feed_plan",
        run=lambda day_from, day_to, birds: json.dumps(
            logic.feed_plan(day_from, day_to, birds)),
        description="Total feed across a span of days."))
    return registry


def _planner(messages: list[dict[str, Any]]) -> dict[str, Any]:
    for m in reversed(messages):
        if m["role"] == "user" and m["content"].startswith("[result]"):
            return {"type": "final", "content": m["content"][len("[result] "):]}
    task = json.loads(messages[1]["content"])
    intent = task.get("intent", "ration")
    if intent == "plan":
        return {"type": "tool", "name": "feed_plan", "args": {
            "day_from": task["day_from"], "day_to": task["day_to"], "birds": task["birds"]}}
    if intent == "schedule":
        return {"type": "tool", "name": "phase_schedule", "args": {}}
    return {"type": "tool", "name": "lookup_ration", "args": {
        "day": task["day"], "birds": task.get("birds", 1)}}


def advise(task: dict[str, Any], policy: Policy | None = None) -> RunResult:
    tracer = Tracer()
    agent = Agent(model=_planner, tools=build_registry(policy=policy, tracer=tracer),
                  system_prompt="You give broiler feeding advice from published standards.")
    return agent.run(json.dumps(task))

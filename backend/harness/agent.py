"""The agent loop — nine steps per turn, eight of them ours.

    assemble -> budget -> call -> DECIDE -> validate -> authorise
             -> execute -> observe -> loop

Only DECIDE belongs to the model. Everything else is ordinary control flow, and
that is the point: the reliability of this app lives here, not in the prompt.

TERMINATION
-----------
The loop stops on a turn budget, a wall-clock budget, or repeated identical
tool calls. A farmer waiting on a phone must never hit an unbounded loop, and
an advice endpoint must never hang.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from .tools import ToolRegistry
from .tracing import EventType, Tracer


class StopReason(str, Enum):
    COMPLETED = "completed"
    TURN_BUDGET = "turn_budget"
    TIME_BUDGET = "time_budget"
    NO_PROGRESS = "no_progress"
    MODEL_ERROR = "model_error"


@dataclass
class RunResult:
    output: str
    stop_reason: StopReason
    turns: int
    tracer: Tracer
    citations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Only completion is success. A budget stop is never 'it worked'."""
        return self.stop_reason is StopReason.COMPLETED


# A model takes the message list and returns either
#   {"type": "tool", "name": str, "args": dict}
#   {"type": "final", "content": str}
Model = Callable[[list[dict[str, Any]]], dict[str, Any]]


@dataclass
class Agent:
    model: Model
    tools: ToolRegistry
    system_prompt: str = "You are a careful poultry advisor."

    max_turns: int = 6
    max_seconds: float = 20.0
    repeat_limit: int = 2

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])

    def run(self, task: str) -> RunResult:
        tracer = self.tools.tracer or Tracer(run_id=self.run_id)
        self.tools.tracer = tracer
        tracer.record(EventType.RUN_START, "agent", task=task)

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.system_prompt},   # cacheable prefix
            {"role": "user", "content": task},
        ]
        started = time.monotonic()
        seen: dict[str, int] = {}
        turns = 0

        while True:
            # 2. BUDGET — checked before spending anything, not after.
            if turns >= self.max_turns:
                return self._finish(StopReason.TURN_BUDGET, messages, turns, tracer)
            if time.monotonic() - started > self.max_seconds:
                return self._finish(StopReason.TIME_BUDGET, messages, turns, tracer)

            turns += 1

            # 3. CALL + 4. DECIDE — the only step that is the model's.
            tracer.record(EventType.MODEL_CALL, f"turn-{turns}")
            try:
                decision = self.model(messages)
            except Exception as exc:
                tracer.record(EventType.TOOL_ERROR, "model", error=repr(exc))
                return self._finish(StopReason.MODEL_ERROR, messages, turns, tracer)

            if decision.get("type") == "final":
                out = str(decision.get("content", ""))
                messages.append({"role": "assistant", "content": out})
                tracer.record(EventType.RUN_END, "agent", stop="completed")
                return RunResult(
                    output=out,
                    stop_reason=StopReason.COMPLETED,
                    turns=turns,
                    tracer=tracer,
                    citations=self._citations(tracer),
                )

            name = str(decision.get("name", ""))
            args = decision.get("args") or {}

            # No-progress guard: the same call repeated is a stuck model.
            key = f"{name}:{sorted(args.items())}"
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > self.repeat_limit:
                return self._finish(StopReason.NO_PROGRESS, messages, turns, tracer)

            # 5/6/7. VALIDATE, AUTHORISE, EXECUTE — all inside the registry.
            observation = self.tools.execute(name, args)

            # 8. OBSERVE — the result goes back as context for the next turn.
            messages.append({"role": "assistant", "content": f"[tool] {name}({args})"})
            messages.append({"role": "user", "content": f"[result] {observation}"})

    def _finish(
        self,
        reason: StopReason,
        messages: list[dict[str, Any]],
        turns: int,
        tracer: Tracer,
    ) -> RunResult:
        """Stop honestly: say which budget fired rather than inventing an answer."""
        tracer.record(EventType.RUN_END, "agent", stop=reason.value)
        return RunResult(
            output=f"Stopped without completing: {reason.value}.",
            stop_reason=reason,
            turns=turns,
            tracer=tracer,
            citations=self._citations(tracer),
        )

    @staticmethod
    def _citations(tracer: Tracer) -> list[str]:
        """Which tools actually supplied data for this answer."""
        return sorted({e.name for e in tracer.tool_calls()})

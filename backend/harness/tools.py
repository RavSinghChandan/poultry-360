"""Tools carry their own effect, so policy never guesses from a name.

One gate, on one hot path. Scattered permission checks always grow a hole.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable

from .policy import Effect, Policy
from .tracing import EventType, Tracer


class ToolError(Exception):
    """A failure the model can read and act on."""


@dataclass(frozen=True)
class Tool:
    name: str
    run: Callable[..., Any]
    effect: Effect = Effect.READ
    description: str = ""
    reads_untrusted: bool = False   # pulls in content we did not author


@dataclass
class ToolRegistry:
    policy: Policy
    tracer: Tracer | None = None
    _tools: dict[str, Tool] = field(default_factory=dict)
    saw_untrusted: bool = False

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def available(self) -> list[Tool]:
        """Tools the model may be told about right now.

        Once untrusted content (a farmer's uploaded photo caption, a supplier
        page) is in context, destructive capability is withdrawn for the rest
        of the run. An injection can then ask for anything and reach nothing.
        """
        tools = list(self._tools.values())
        if self.saw_untrusted:
            return [t for t in tools if t.effect is not Effect.DESTRUCTIVE]
        return tools

    def execute(self, name: str, args: dict[str, Any] | None = None) -> str:
        """Validate, authorise, run. Always returns text the model can read."""
        args = args or {}
        started = time.monotonic()

        tool = self._tools.get(name)
        if tool is None:                                    # validation
            known = ", ".join(sorted(self._tools)) or "none"
            msg = f"No tool named {name!r}. Available: {known}"
            if self.tracer:
                self.tracer.record(EventType.TOOL_ERROR, name, error=msg)
            return f"ERROR: {msg}"

        verdict = self.policy.check(name, tool.effect, args)  # authorisation
        if not verdict.allowed:
            if self.tracer:
                self.tracer.record(EventType.TOOL_DENIED, name, reason=verdict.reason)
            return f"DENIED: {verdict.reason}"

        if self.tracer:
            self.tracer.record(EventType.TOOL_CALL, name, args=args)

        try:
            result = tool.run(**args)
        except ToolError as exc:                            # expected failure
            if self.tracer:
                self.tracer.record(EventType.TOOL_ERROR, name, error=str(exc))
            return f"ERROR: {exc}"
        except TypeError as exc:                            # wrong arguments
            if self.tracer:
                self.tracer.record(EventType.TOOL_ERROR, name, error=str(exc))
            return f"ERROR: {name} called with wrong arguments: {exc}"
        except Exception as exc:                            # unexpected
            if self.tracer:
                self.tracer.record(EventType.TOOL_ERROR, name, error=repr(exc))
            return f"ERROR: {name} failed unexpectedly: {exc}"

        if tool.reads_untrusted:
            self.saw_untrusted = True

        if self.tracer:
            ev = self.tracer.record(EventType.TOOL_RESULT, name)
            ev.duration_ms = (time.monotonic() - started) * 1000

        return str(result)

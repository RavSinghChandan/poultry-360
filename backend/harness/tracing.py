"""Every step recorded, so a wrong answer can be explained after the fact.

A farmer acting on bad feed advice needs to know where the number came from.
"Nobody can explain what happened" is a harness failure, not a model failure.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EventType(str, Enum):
    RUN_START = "run_start"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    TOOL_DENIED = "tool_denied"
    TOOL_ERROR = "tool_error"
    MODEL_CALL = "model_call"
    RUN_END = "run_end"


@dataclass
class Event:
    type: EventType
    name: str
    detail: dict[str, Any] = field(default_factory=dict)
    at: float = field(default_factory=time.time)
    duration_ms: float = 0.0


@dataclass
class Tracer:
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    events: list[Event] = field(default_factory=list)

    def record(self, type: EventType, name: str, **detail: Any) -> Event:
        ev = Event(type=type, name=name, detail=detail)
        self.events.append(ev)
        return ev

    def tool_calls(self) -> list[Event]:
        return [e for e in self.events if e.type is EventType.TOOL_CALL]

    def to_dict(self) -> dict[str, Any]:
        """Serialisable trace, safe to return over the API."""
        return {
            "run_id": self.run_id,
            "events": [
                {
                    "type": e.type.value,
                    "name": e.name,
                    "detail": e.detail,
                    "duration_ms": round(e.duration_ms, 2),
                }
                for e in self.events
            ],
        }

    def render(self) -> str:
        """Human-readable tree, for logs and for the /trace endpoint."""
        lines = [f"run {self.run_id}"]
        for e in self.events:
            mark = {
                EventType.TOOL_DENIED: "denied",
                EventType.TOOL_ERROR: "error",
            }.get(e.type, "")
            extra = f"  [{mark}]" if mark else ""
            lines.append(f"  {e.type.value:13s} {e.name}{extra}")
        return "\n".join(lines)

"""Authority control — adapted from harness-engineering P04.

Validation asks "is this well-formed?". Authorisation asks "is this allowed?".
They stay apart because a validation error should be retried and a denial
should be explained.

WHY THIS MATTERS ON A FARM
--------------------------
Reading a published ration table is safe. Recording a mortality figure against
a batch changes a record a farmer relies on. Sending an order to a feed
supplier spends money. Those are three different levels of authority and the
harness must not treat them alike.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class Effect(str, Enum):
    """What a tool does to the world. Policy keys off this, never off a name."""

    READ = "read"              # look something up; no side effect
    WRITE = "write"            # change a record we can correct later
    DESTRUCTIVE = "destroy"    # irreversible or spends money


class Mode(str, Enum):
    """How much authority this session carries."""

    READ_ONLY = "read_only"     # advice only — the default for a public demo
    ASK_FIRST = "ask_first"     # confirm every change
    AUTONOMOUS = "autonomous"   # writes flow; destruction still confirms


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str = ""
    asked: bool = False


Confirmer = Callable[[str, dict], bool]


def _deny_everything(name: str, args: dict) -> bool:
    """Safe default: with no confirmer wired up, nothing is confirmed."""
    return False


@dataclass
class Policy:
    mode: Mode = Mode.READ_ONLY
    confirm: Confirmer = _deny_everything

    def check(self, tool_name: str, effect: Effect, args: dict) -> Verdict:
        """Decide whether this call may proceed."""
        if effect is Effect.READ:
            return Verdict(True, "read is always allowed")

        if self.mode is Mode.READ_ONLY:
            return Verdict(
                False,
                f"{tool_name} changes data and this session is advice-only",
            )

        if effect is Effect.DESTRUCTIVE:
            ok = self.confirm(tool_name, args)
            return Verdict(
                ok,
                "confirmed by operator" if ok else f"{tool_name} was not confirmed",
                asked=True,
            )

        # WRITE
        if self.mode is Mode.AUTONOMOUS:
            return Verdict(True, "writes flow in autonomous mode")

        ok = self.confirm(tool_name, args)
        return Verdict(
            ok,
            "confirmed by operator" if ok else f"{tool_name} was not confirmed",
            asked=True,
        )

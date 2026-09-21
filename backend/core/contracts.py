"""The contract every feature implements.

WHY THIS FILE EXISTS
--------------------
Feature 1 was written directly into domain/. Adding feature 2 that way means
editing shared files, and every edit to a shared file is a chance to break a
feature that was already working.

So a feature is now a self-contained module that implements `Feature`. The
platform discovers it, mounts its routes, registers its tools and runs its
self-check. Adding one touches no existing feature's code.

THE RULES A FEATURE MUST FOLLOW
-------------------------------
1. It owns its own data, domain logic, tools and tests.
2. It never imports another feature. Shared needs go in core/ or harness/.
3. Its tools declare an Effect; the platform enforces policy, not the feature.
4. `selfcheck()` must pass before the feature is served. A feature whose data
   is wrong fails loudly at startup rather than quietly at a farmer's screen.
5. Numbers a farmer acts on come from a cited source, never from a model.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable

from fastapi import APIRouter

from harness.policy import Effect


@dataclass(frozen=True)
class ToolSpec:
    """A tool a feature contributes to the shared registry."""

    name: str
    run: Callable[..., Any]
    effect: Effect = Effect.READ
    description: str = ""
    reads_untrusted: bool = False


@dataclass(frozen=True)
class FeatureInfo:
    """What the platform shows about a feature, and what the UI needs to render it."""

    key: str                      # stable id, used in URLs and the registry
    name_en: str
    name_hi: str
    summary_en: str
    summary_hi: str
    version: str = "0.1.0"
    status: str = "live"          # live | beta | planned
    icon: str = "🐔"
    sources: list[str] = field(default_factory=list)


@runtime_checkable
class Feature(Protocol):
    """Implement this and the platform will mount you.

    Nothing here knows about poultry. A feature is a unit of capability with
    an identity, some routes, some tools, and a way to prove it is healthy.
    """

    def info(self) -> FeatureInfo:
        """Identity and description. Must be stable across releases."""

    def router(self) -> APIRouter:
        """Routes, which the platform mounts under /api/<key>."""

    def tools(self) -> list[ToolSpec]:
        """Tools contributed to the shared agent registry."""

    def selfcheck(self) -> list[str]:
        """Return a list of problems. Empty means healthy.

        Run at startup and exposed at /api/health. A feature that cannot
        validate its own data must say so here rather than serve bad advice.
        """

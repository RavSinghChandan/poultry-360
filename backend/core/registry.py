"""Discovers features, mounts them, and refuses to serve a broken one.

ISOLATION IS THE POINT
----------------------
A feature that fails to import, fails its selfcheck, or collides with another
feature's key or tool names is recorded as failed and left unmounted. The rest
of the platform keeps serving. One broken feature must never take down the app
a farmer is standing in a shed using.
"""
from __future__ import annotations

import importlib
import pkgutil
from dataclasses import dataclass, field
from typing import Any

from fastapi import APIRouter

from core.contracts import Feature, FeatureInfo, ToolSpec


@dataclass
class LoadedFeature:
    key: str
    info: FeatureInfo
    feature: Feature
    problems: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not self.problems


@dataclass
class FeatureRegistry:
    loaded: dict[str, LoadedFeature] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)

    def discover(self, package: str = "features") -> None:
        """Import every feature package and register the ones that work."""
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError:
            return

        for mod in pkgutil.iter_modules(pkg.__path__):
            if not mod.ispkg or mod.name.startswith("_"):
                continue
            name = f"{package}.{mod.name}"
            try:
                module = importlib.import_module(name)
                factory = getattr(module, "feature", None)
                if factory is None:
                    self.failed[mod.name] = "module has no `feature()` factory"
                    continue
                self.register(factory())
            except Exception as exc:                  # a broken feature is contained
                self.failed[mod.name] = f"{type(exc).__name__}: {exc}"

    def register(self, feature: Feature) -> None:
        """Add one feature, rejecting collisions and unhealthy state."""
        info = feature.info()

        if info.key in self.loaded:
            self.failed[info.key] = f"duplicate feature key {info.key!r}"
            return

        existing = {t.name for lf in self.loaded.values() for t in lf.feature.tools()}
        clashes = sorted({t.name for t in feature.tools()} & existing)
        if clashes:
            self.failed[info.key] = f"tool name(s) already taken: {', '.join(clashes)}"
            return

        problems = list(feature.selfcheck())
        self.loaded[info.key] = LoadedFeature(
            key=info.key, info=info, feature=feature, problems=problems
        )

    # ── what the platform asks the registry for ────────────────────────────

    def healthy(self) -> list[LoadedFeature]:
        return [lf for lf in self.loaded.values() if lf.healthy]

    def routers(self) -> list[tuple[str, APIRouter]]:
        """Only healthy features are served."""
        return [(lf.key, lf.feature.router()) for lf in self.healthy()]

    def tools(self) -> list[ToolSpec]:
        return [t for lf in self.healthy() for t in lf.feature.tools()]

    def manifest(self) -> dict[str, Any]:
        """What /api/features returns, and what the UI renders its menu from."""
        return {
            "features": [
                {
                    "key": lf.key,
                    "name_en": lf.info.name_en,
                    "name_hi": lf.info.name_hi,
                    "summary_en": lf.info.summary_en,
                    "summary_hi": lf.info.summary_hi,
                    "version": lf.info.version,
                    "status": lf.info.status,
                    "icon": lf.info.icon,
                    "sources": lf.info.sources,
                    "healthy": lf.healthy,
                    "problems": lf.problems,
                    "base_path": f"/api/{lf.key}",
                }
                for lf in self.loaded.values()
            ],
            "failed_to_load": self.failed,
        }

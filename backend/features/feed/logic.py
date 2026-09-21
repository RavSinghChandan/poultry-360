"""Feed advice — the domain logic behind the first feature.

Every number returned here comes from data/rations.py, which is a transcription
of published standards. This module does arithmetic on those numbers (scaling
per-bird intake to a flock, converting grams to kilograms) and never originates
a nutrient value of its own.
"""
from __future__ import annotations

from typing import Any

from features.feed import rations
from harness.tools import ToolError


def ration_for_day(day: int, birds: int = 1) -> dict[str, Any]:
    """The full ration card for a bird of this age, scaled to the flock.

    Args:
        day: age in days since hatch, 0-42.
        birds: how many birds in the batch.

    Raises:
        ToolError: for an age the published tables do not cover, or a bird
            count that is not a positive whole number. The message is written
            for the model to read and relay.
    """
    try:
        phase = rations.phase_for_day(day)
    except rations.DayOutOfRange as exc:
        raise ToolError(
            f"{exc}. Commercial broiler tables run from day 0 to day "
            f"{rations.MAX_DAY}; after that the bird is normally sold."
        ) from exc

    if not isinstance(birds, int) or isinstance(birds, bool) or birds < 1:
        raise ToolError(f"birds must be a whole number of at least 1, got {birds!r}")

    per_bird_g = rations.intake_g_for_day(day)
    total_kg = round(per_bird_g * birds / 1000.0, 2)

    return {
        "day": day,
        "birds": birds,
        "phase": phase["key"],
        "phase_name_en": phase["name_en"],
        "phase_name_hi": phase["name_hi"],
        "crude_protein_pct": phase["crude_protein_pct"],
        "energy_kcal_per_kg": phase["energy_kcal_per_kg"],
        "lysine_pct": phase["lysine_pct"],
        "methionine_pct": phase["methionine_pct"],
        "calcium_pct": phase["calcium_pct"],
        "available_phosphorus_pct": phase["available_phosphorus_pct"],
        "feed_per_bird_g": per_bird_g,
        "feed_total_kg": total_kg,
        "target_weight_g": rations.target_weight_g(day),
        "note_en": phase["note_en"],
        "note_hi": phase["note_hi"],
        "source": rations.SOURCES,
        "dataset_version": rations.DATASET_VERSION,
    }


def phase_schedule() -> list[dict[str, Any]]:
    """The whole 0-42 day plan, for the farmer who wants the full chart."""
    out = []
    for phase in rations.PHASES:
        low, high = phase["days"]
        out.append({
            "phase": phase["key"],
            "name_en": phase["name_en"],
            "name_hi": phase["name_hi"],
            "day_from": low,
            "day_to": high,
            "crude_protein_pct": phase["crude_protein_pct"],
            "energy_kcal_per_kg": phase["energy_kcal_per_kg"],
        })
    return out


def feed_plan(day_from: int, day_to: int, birds: int) -> dict[str, Any]:
    """Total feed a batch needs across a span of days.

    Useful for ordering: a farmer asks "how much feed to day 42?" and needs
    kilograms, not percentages.
    """
    if day_to < day_from:
        raise ToolError(f"day_to ({day_to}) is before day_from ({day_from})")
    for d in (day_from, day_to):
        try:
            rations.phase_for_day(d)
        except rations.DayOutOfRange as exc:
            raise ToolError(str(exc)) from exc
    if not isinstance(birds, int) or isinstance(birds, bool) or birds < 1:
        raise ToolError(f"birds must be a whole number of at least 1, got {birds!r}")

    by_phase: dict[str, float] = {}
    total_g = 0
    for d in range(day_from, day_to + 1):
        g = rations.intake_g_for_day(d) * birds
        total_g += g
        key = rations.phase_for_day(d)["key"]
        by_phase[key] = by_phase.get(key, 0.0) + g / 1000.0

    return {
        "day_from": day_from,
        "day_to": day_to,
        "birds": birds,
        "total_feed_kg": round(total_g / 1000.0, 2),
        "by_phase_kg": {k: round(v, 2) for k, v in by_phase.items()},
        "dataset_version": rations.DATASET_VERSION,
    }

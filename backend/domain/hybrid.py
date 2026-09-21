"""The hybrid path: table for numbers, model for judgement.

Three routes, decided before the model is reached (see router.py):

    FACTUAL      table only      — deterministic, no model, no key needed
    EXPLANATORY  model only      — no published number is at stake
    DIAGNOSTIC   table -> model  — numbers fixed first, model reasons on them

Every answer says which route it took and whether a model was involved, so a
farmer (or an auditor) can always tell where a sentence came from.
"""
from __future__ import annotations

from typing import Any

from data import rations
from domain import feed
from domain.router import Route, classify, extract_day
from harness import llm
from harness.tools import ToolError

_SYSTEM = (
    "You advise Indian poultry farmers about broiler feeding. "
    "Write in simple English and Hindi, 6th-grade level, at most 5 short "
    "sentences. "
    "NEVER state a protein percentage, energy figure or any nutrient number "
    "unless it appears in the FACTS given to you. If you need a number that is "
    "not in the FACTS, say the farmer should check the ration chart instead. "
    "Do not diagnose disease; suggest they consult a veterinarian for illness."
)


def _allowed_numbers(ration: dict[str, Any]) -> set[str]:
    """Figures the model is permitted to repeat, taken from the table."""
    keys = ("crude_protein_pct", "energy_kcal_per_kg", "lysine_pct",
            "methionine_pct", "calcium_pct", "available_phosphorus_pct",
            "feed_per_bird_g", "feed_total_kg", "target_weight_g", "day")
    return {str(ration[k]) for k in keys if ration.get(k) is not None}


def answer(question: str, birds: int = 1) -> dict[str, Any]:
    """Route one free-text question and answer it."""
    route = classify(question)
    day = extract_day(question)

    result: dict[str, Any] = {
        "route": route.value,
        "question": question,
        "model_used": False,
        "dataset_version": rations.DATASET_VERSION,
    }

    # ---- the table, whenever a day was mentioned -------------------------
    ration = None
    if day is not None:
        try:
            ration = feed.ration_for_day(day, birds)
            result["ration"] = ration
            result["source"] = ration["source"]
        except ToolError as exc:
            result["ok"] = False
            result["error"] = str(exc)
            return result

    # ---- FACTUAL: the table is the whole answer --------------------------
    if route is Route.FACTUAL:
        if ration is None:
            result["ok"] = False
            result["error"] = (
                "Tell me the bird's age in days, for example 'day 17'. "
                "मुर्गी की उम्र दिनों में बताएँ, जैसे 'दिन 17'।"
            )
            return result
        result["ok"] = True
        result["answer"] = (
            f"{ration['phase_name_hi']} · {ration['phase_name_en']} "
            f"(दिन {ration['day']}): प्रोटीन {ration['crude_protein_pct']}%, "
            f"ऊर्जा {ration['energy_kcal_per_kg']} kcal/kg, "
            f"फ़ीड {ration['feed_per_bird_g']} g प्रति मुर्गी."
        )
        return result

    # ---- the model paths -------------------------------------------------
    if not llm.is_enabled():
        result["ok"] = True
        result["model_available"] = False
        if ration is not None:
            result["answer"] = (
                f"यह रहा दिन {ration['day']} का आहार: प्रोटीन "
                f"{ration['crude_protein_pct']}%, ऊर्जा "
                f"{ration['energy_kcal_per_kg']} kcal/kg. "
                "(विस्तृत सलाह के लिए AI सहायक अभी उपलब्ध नहीं है।)"
            )
        else:
            result["answer"] = (
                "AI सहायक अभी उपलब्ध नहीं है। मुर्गी की उम्र बताएँ तो "
                "आहार चार्ट दिखा सकते हैं. "
                "(AI assistant unavailable; give the age for the ration chart.)"
            )
        return result

    if route is Route.DIAGNOSTIC and ration is not None:
        facts = (
            f"FACTS from the published table for a day-{ration['day']} broiler:\n"
            f"- crude protein should be {ration['crude_protein_pct']}%\n"
            f"- energy should be {ration['energy_kcal_per_kg']} kcal/kg\n"
            f"- feed per bird today {ration['feed_per_bird_g']} g\n"
            f"- target liveweight {ration['target_weight_g']} g\n"
            f"Source: {ration['source'][0]}"
        )
        prompt = f"{facts}\n\nFARMER SAYS: {question}\n\nCompare what they report against the FACTS and advise."
    else:
        prompt = (
            "FACTS: none supplied — do not state any nutrient number.\n\n"
            f"FARMER ASKS: {question}"
        )

    reply = llm.ask(_SYSTEM, prompt)
    if reply is None:
        result["ok"] = True
        result["model_available"] = False
        result["answer"] = (
            "AI सहायक अभी जवाब नहीं दे पाया। "
            "(The assistant could not answer; the ration chart above still applies.)"
        )
        return result

    allowed = _allowed_numbers(ration) if ration else set()
    reply, invented = llm.verify_no_invented_numbers(reply, allowed)

    result["ok"] = True
    result["model_used"] = True
    result["answer"] = reply
    if invented:
        # Never hide this. The farmer and any auditor must see that a figure
        # in the text did not come from the published table.
        result["unverified_numbers"] = invented
        result["warning"] = (
            "Some figures in this reply are not from the published table. "
            "Follow the ration chart, not the text."
        )
    return result

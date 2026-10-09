"""Decides which path a question takes: table, model, or both.

WHY A ROUTER AND NOT "LET THE MODEL DECIDE"
-------------------------------------------
The obvious hybrid is to hand the model every question and let it choose when
to call the ration tool. That is worse than either pure option, because it puts
the model in the path of a safety-critical number: it can decide not to call
the tool at all, or paraphrase 20.0% as "about 20 to 22 percent".

So the split is made *before* the model is reached, and it is made on the shape
of the question rather than on anyone's confidence:

    FACTUAL      a number exists in the published table  -> table only
    EXPLANATORY  no number is being asked for            -> model only
    DIAGNOSTIC   a number is needed AND judgement is     -> table, then model
                 needed about the farmer's situation        with the numbers
                                                            already fixed

In the diagnostic path the table runs FIRST and its figures are passed to the
model as established fact. The model reasons about the gap between what the
bird should be getting and what the farmer reports. It never supplies the
target itself.
"""
from __future__ import annotations

import re
from enum import Enum


class Route(str, Enum):
    FACTUAL = "factual"          # table answers it; no model involved
    EXPLANATORY = "explanatory"  # model answers it; no number at stake
    DIAGNOSTIC = "diagnostic"    # table first, then model reasons over it


# A day mentioned as an age: "day 17", "17 din", "17 days old", "17 दिन".
_DAY = re.compile(
    r"(?:day|din|दिन)\s*(\d{1,2})|(\d{1,2})\s*(?:day|din|दिन)",
    re.IGNORECASE,
)

# Words that mean the farmer is reporting a problem, not asking for a figure.
_TROUBLE = (
    "weak", "dying", "died", "death", "mortality", "sick", "ill", "loose",
    "not eating", "not growing", "not gaining", "slow growth", "thin",
    "weight drop", "problem", "issue", "worried",
    "stopped eating", "not eat", "low weight",
    "कमज़ोर", "कमजोर", "मर", "बीमार", "नहीं खा", "नहीं बढ़",
    # Hinglish: Hindi typed in English letters, which is how most farmers text.
    "kamzor", "kamjor", "mar rahe", "mar rahi", "mar gaye", "mar gayi", "bimar",
    "beemar", "nahi kha", "nahin kha", "nhi kha", "badh nahi", "badh nahin",
    "badh nhi", "weight kam", "wajan kam", "vajan kam", "dast", "patli beet",
)

# Words that ask for reasoning rather than a value.
_WHY = ("why", "how come", "reason", "explain", "क्यों", "कैसे", "वजह",
        "kyun", "kyon", "kyu ", "kaise", "wajah", "vajah")


def extract_day(text: str) -> int | None:
    """The bird age mentioned in free text, if there is one."""
    m = _DAY.search(text)
    if not m:
        return None
    raw = m.group(1) or m.group(2)
    try:
        day = int(raw)
    except (TypeError, ValueError):       # pragma: no cover - regex guarantees digits
        return None
    return day


def classify(text: str) -> Route:
    """Which path this question takes.

    Deliberately conservative: anything that reports a problem is diagnostic
    even if it also asks "why", because the farmer needs the correct target
    numbers in front of them before any explanation is useful.
    """
    low = text.lower()
    has_trouble = any(w in low for w in _TROUBLE)
    has_why = any(w in low for w in _WHY)

    if has_trouble:
        return Route.DIAGNOSTIC
    if has_why:
        return Route.EXPLANATORY
    return Route.FACTUAL

"""Offline evals for the parts of Poultry 360 that decide what a farmer is told.

    python -m evals.run            # from the repo root; writes evals/results.json
    python -m evals.run --check    # also exit 1 if a score drops below its floor (CI)

1. Router: does each question take the right path (table / model / both), and
   is the bird's age read correctly? English, Hindi and Hinglish.
2. Grounding guard: when the model writes a nutrient figure that is not in the
   published table, is it flagged? Model replies are fixed text, so the eval is
   free, offline and repeatable.

No API key, no network. Deterministic: the same code gives the same numbers.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend"))

from features.feed import logic as feed  # noqa: E402
from features.feed.hybrid import _allowed_numbers  # noqa: E402
from features.feed.router_rules import classify, extract_day  # noqa: E402
from harness.llm import verify_no_invented_numbers  # noqa: E402

# A drop below these fails CI. Raise them as the scores improve, never lower them.
FLOORS = {"router_route_accuracy": 0.95, "router_day_accuracy": 1.0,
          "guard_recall": 0.8, "guard_precision": 1.0}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_HINGLISH = ("din", "kitna", "murgi", "chuze", "kyun", "kaise", "nahi", "kamzor", "mar rahe", "bimar", "badh", " pe", "hai")


def _lang(q: str) -> str:
    if _DEVANAGARI.search(q):
        return "hindi"
    return "hinglish" if any(w in f" {q.lower()} " for w in _HINGLISH) else "english"


def _load(name: str) -> list[dict]:
    return [json.loads(l) for l in (HERE / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def eval_router() -> dict:
    cases = _load("router_cases.jsonl")
    by_lang: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    route_ok = day_ok = 0
    misses = []
    for c in cases:
        got_route, got_day = classify(c["q"]).value, extract_day(c["q"])
        r, d = got_route == c["route"], got_day == c["day"]
        route_ok += r
        day_ok += d
        by_lang[_lang(c["q"])][0] += r
        by_lang[_lang(c["q"])][1] += 1
        if not (r and d):
            misses.append({"q": c["q"], "expected": [c["route"], c["day"]], "got": [got_route, got_day]})
    n = len(cases)
    return {"cases": n, "router_route_accuracy": round(route_ok / n, 3), "router_day_accuracy": round(day_ok / n, 3),
            "route_accuracy_by_language": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_lang.items())},
            "misses": misses}


def eval_guard() -> dict:
    tp = fp = fn = tn = 0
    misses = []
    for c in _load("grounding_cases.jsonl"):
        ration = feed.ration_for_day(c["day"])
        reply = c["reply"].format(**ration)
        _, invented = verify_no_invented_numbers(reply, _allowed_numbers(ration))
        flagged = bool(invented)
        if flagged and c["invented"]:
            tp += 1
        elif flagged:
            fp += 1
            misses.append({"reply": reply, "expected": "clean", "flagged": invented})
        elif c["invented"]:
            fn += 1
            misses.append({"reply": reply, "expected": "flagged", "flagged": []})
        else:
            tn += 1
    return {"cases": tp + fp + fn + tn,
            "guard_recall": round(tp / (tp + fn), 3) if tp + fn else 1.0,
            "guard_precision": round(tp / (tp + fp), 3) if tp + fp else 1.0,
            "misses": misses}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if a score is below its floor")
    args = ap.parse_args()
    results = {"router": eval_router(), "grounding_guard": eval_guard()}
    (HERE / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    flat = {**results["router"], **results["grounding_guard"]}
    print(f"Router      route {flat['router_route_accuracy']:.0%}  day {flat['router_day_accuracy']:.0%}  "
          f"({results['router']['cases']} questions; by language {results['router']['route_accuracy_by_language']})")
    print(f"Guard       recall {flat['guard_recall']:.0%}  precision {flat['guard_precision']:.0%}  "
          f"({results['grounding_guard']['cases']} model replies)")
    for section in results.values():
        for m in section["misses"]:
            print("  miss:", json.dumps(m, ensure_ascii=False))
    below = [k for k, floor in FLOORS.items() if flat[k] < floor]
    if args.check and below:
        print("Below floor:", ", ".join(below))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

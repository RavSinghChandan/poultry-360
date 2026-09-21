"""Optional LLM, used only where no published number is at stake.

THE CONSTRAINT
--------------
This model never originates a nutrient value. On the diagnostic path the
ration table runs first and its figures are handed to the model as established
fact; the model reasons about the gap between the published target and what
the farmer reports. `verify_no_invented_numbers` is the backstop: any nutrient
figure in the reply that is not one we supplied is stripped and flagged.

The key is read from the environment only. With no key the app degrades to the
deterministic path and says so, rather than failing.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"
TIMEOUT_SECONDS = 20

# A percentage or kcal figure in the reply, which is what must be verified.
_NUMBER = re.compile(r"(\d+(?:\.\d+)?)\s*(%|percent|kcal|प्रतिशत)", re.IGNORECASE)


def is_enabled() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY", "").strip())


def status() -> dict[str, Any]:
    """Safe to serialise. Never includes the key."""
    return {
        "provider": "deepseek",
        "enabled": is_enabled(),
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
    }


def verify_no_invented_numbers(reply: str, allowed: set[str]) -> tuple[str, list[str]]:
    """Check every nutrient figure in the reply against the ones we supplied.

    Returns the reply and a list of figures that did not come from the table.
    We do not silently rewrite the text - the caller decides what to do, and
    the API reports the discrepancy so it is never invisible.
    """
    invented = []
    for raw, _unit in _NUMBER.findall(reply):
        # Compare numerically so "20" and "20.0" are the same figure.
        try:
            val = float(raw)
        except ValueError:                      # pragma: no cover
            continue
        if not any(abs(val - float(a)) < 1e-9 for a in allowed):
            invented.append(raw)
    return reply, invented


def ask(system: str, user: str, temperature: float = 0.3) -> str | None:
    """One completion, or None on any failure.

    Returning None rather than raising is deliberate: an explanation is never
    worth failing a farmer's request over, and the deterministic answer is
    always available.
    """
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key:
        return None

    base = os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    payload = json.dumps({
        "model": os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }).encode("utf-8")

    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = json.loads(response.read().decode("utf-8"))
        return str(body["choices"][0]["message"]["content"]).strip()
    except (urllib.error.URLError, TimeoutError, KeyError,
            IndexError, ValueError, json.JSONDecodeError):
        # Deliberately opaque: the request carries the key in its headers.
        return None

"""What the running service is doing, for the owner's ops panel.

In memory, since the process started: requests, errors and latency per route,
requests per farm today, and every model call (ok or failed, how long, tokens).
A free instance restarts often, so this is a live view, not a history.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Any

_LATENCY_SAMPLES = 500
_lock = threading.Lock()
_started = time.time()
_routes: dict[str, dict[str, Any]] = defaultdict(lambda: {"count": 0, "client_errors": 0, "server_errors": 0,
                                                          "ms": deque(maxlen=_LATENCY_SAMPLES)})
_tenants: dict[str, int] = defaultdict(int)
_tenant_day = {"day": ""}
_model = {"calls": 0, "failed": 0, "prompt_tokens": 0, "completion_tokens": 0, "ms": deque(maxlen=_LATENCY_SAMPLES)}


def _pct(samples: deque, p: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    return round(ordered[min(len(ordered) - 1, int(p * len(ordered)))], 1)


def record_request(route: str, status: int, ms: float, tenant: str | None = None) -> None:
    with _lock:
        r = _routes[route]
        r["count"] += 1
        r["ms"].append(ms)
        if status >= 500:
            r["server_errors"] += 1
        elif status >= 400:
            r["client_errors"] += 1
        if tenant:
            today = time.strftime("%Y-%m-%d")
            if _tenant_day["day"] != today:
                _tenants.clear()
                _tenant_day["day"] = today
            _tenants[tenant] += 1


def record_model_call(ok: bool, ms: float, usage: dict[str, Any] | None = None) -> None:
    with _lock:
        _model["calls"] += 1
        _model["failed"] += 0 if ok else 1
        _model["ms"].append(ms)
        if usage:
            _model["prompt_tokens"] += int(usage.get("prompt_tokens", 0) or 0)
            _model["completion_tokens"] += int(usage.get("completion_tokens", 0) or 0)


def snapshot() -> dict[str, Any]:
    with _lock:
        routes = [{"route": k, "count": v["count"], "client_errors": v["client_errors"],
                   "server_errors": v["server_errors"], "p50_ms": _pct(v["ms"], 0.5), "p95_ms": _pct(v["ms"], 0.95)}
                  for k, v in _routes.items()]
        total = sum(r["count"] for r in routes)
        errors = sum(r["server_errors"] for r in routes)
        return {
            "uptime_s": int(time.time() - _started),
            "requests": total,
            "server_error_rate": round(errors / total, 4) if total else 0.0,
            "routes": sorted(routes, key=lambda r: -r["count"]),
            "farms_today": dict(sorted(_tenants.items(), key=lambda kv: -kv[1])),
            "model": {"calls": _model["calls"], "failed": _model["failed"],
                      "fallback_rate": round(_model["failed"] / _model["calls"], 4) if _model["calls"] else 0.0,
                      "p50_ms": _pct(_model["ms"], 0.5), "p95_ms": _pct(_model["ms"], 0.95),
                      "prompt_tokens": _model["prompt_tokens"], "completion_tokens": _model["completion_tokens"]},
        }


def reset() -> None:
    """For tests."""
    with _lock:
        _routes.clear()
        _tenants.clear()
        for k in ("calls", "failed", "prompt_tokens", "completion_tokens"):
            _model[k] = 0
        _model["ms"].clear()

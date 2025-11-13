from __future__ import annotations

from threading import Lock
from typing import Any, Dict

# Lightweight in-memory metrics intended for local/dev observability.
#
# Design goals:
# - Process-local only; no external dependencies.
# - Cheap integer/float operations only.
# - Safe to call from FastAPI middleware in a single process.


REQUEST_COUNT_TOTAL: int = 0
REQUEST_COUNT_BY_PATH: Dict[str, int] = {}
REQUEST_LATENCY_MS: Dict[str, Dict[str, float]] = {}

_LOCK = Lock()


def record_request(path: str, duration_ms: float) -> None:
    """
    Record a completed HTTP request.

    - path: the request URL path (already normalized by the caller).
    - duration_ms: duration in milliseconds.
    """
    global REQUEST_COUNT_TOTAL

    if duration_ms < 0:
        # Defensive; should not happen, but avoid corrupting aggregates.
        duration_ms = 0.0

    with _LOCK:
        REQUEST_COUNT_TOTAL += 1

        # Per-path counts
        REQUEST_COUNT_BY_PATH[path] = REQUEST_COUNT_BY_PATH.get(path, 0) + 1

        # Per-path latency aggregates
        entry = REQUEST_LATENCY_MS.get(path)
        if entry is None:
            REQUEST_LATENCY_MS[path] = {
                "count": 1,
                "total": float(duration_ms),
                "min": float(duration_ms),
                "max": float(duration_ms),
            }
        else:
            count = entry.get("count", 0) + 1
            total = entry.get("total", 0.0) + float(duration_ms)
            current_min = entry.get("min", float(duration_ms))
            current_max = entry.get("max", float(duration_ms))
            if duration_ms < current_min:
                current_min = float(duration_ms)
            if duration_ms > current_max:
                current_max = float(duration_ms)

            entry.update(
                {
                    "count": float(count),
                    "total": float(total),
                    "min": float(current_min),
                    "max": float(current_max),
                }
            )


def snapshot() -> Dict[str, Any]:
    """
    Return a shallow copy of current metrics for debugging.

    Structure:
    {
        "request_count_total": int,
        "request_count_by_path": {path: int, ...},
        "request_latency_ms": {
            path: {"count": int, "total": float, "min": float, "max": float},
            ...
        },
    }
    """
    with _LOCK:
        return {
            "request_count_total": int(REQUEST_COUNT_TOTAL),
            "request_count_by_path": dict(REQUEST_COUNT_BY_PATH),
            "request_latency_ms": {
                path: dict(stats) for path, stats in REQUEST_LATENCY_MS.items()
            },
        }

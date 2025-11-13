"""
Simple performance benchmark runner for the local API.

Usage (non-interactive):

    python -m scripts.run_benchmarks

Configuration (via environment variables):

- API_BASE_URL:
    Base URL of the running API.
    Default: "http://localhost:8000"

- BENCH_N:
    Number of requests per endpoint (int).
    Default: 5

This script:
- Sends N requests to key endpoints.
- Measures latency in milliseconds.
- Prints a JSON blob to stdout with:
    {
      "endpoints": [
        {
          "name": "...",
          "method": "GET/POST",
          "url": "...",
          "n": N,
          "avg_ms": ...,
          "p95_ms": ...,
          "max_ms": ...,
          "ok": true/false,
          "status_codes": [...unique codes seen...]
        },
        ...
      ]
    }

Constraints:
- Uses only standard library + urllib to avoid new dependencies.
- Non-fatal on individual endpoint failures; marks them in output.
"""

from __future__ import annotations

import json
import os
import statistics
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _time_request(
    method: str,
    url: str,
    data: Dict[str, Any] | None = None,
    timeout: float = 10.0,
) -> Tuple[float, int]:
    body: bytes | None = None
    headers = {
        "Accept": "application/json",
    }
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method, data=body, headers=headers)
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
    except urllib.error.HTTPError as exc:
        status = exc.code
    except urllib.error.URLError:
        # Treat as 0 to distinguish from HTTP codes.
        status = 0
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    return elapsed_ms, status


def _stats(latencies: List[float]) -> Dict[str, float]:
    if not latencies:
        return {"avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0}
    lat_sorted = sorted(latencies)
    avg = float(statistics.fmean(lat_sorted))
    p95_index = max(int(round(0.95 * (len(lat_sorted) - 1))), 0)
    p95 = float(lat_sorted[p95_index])
    max_v = float(lat_sorted[-1])
    return {
        "avg_ms": round(avg, 2),
        "p95_ms": round(p95, 2),
        "max_ms": round(max_v, 2),
    }


def run_benchmarks() -> Dict[str, Any]:
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    n = _env_int("BENCH_N", 5)

    endpoints: List[Dict[str, Any]] = [
        {
            "name": "players_list",
            "method": "GET",
            "path": "/api/v1/players?page=1&page_size=10",
            "payload": None,
        },
        {
            "name": "tools_player_season_finder",
            "method": "POST",
            "path": "/api/v1/tools/player-season-finder",
            "payload": {"page": 1, "page_size": 10},
        },
        {
            "name": "tools_player_game_finder",
            "method": "POST",
            "path": "/api/v1/tools/player-game-finder",
            "payload": {"page": 1, "page_size": 10},
        },
        {
            "name": "tools_team_season_finder",
            "method": "POST",
            "path": "/api/v1/tools/team-season-finder",
            "payload": {"page": 1, "page_size": 10},
        },
        {
            "name": "tools_leaderboards",
            "method": "POST",
            "path": "/api/v1/tools/leaderboards",
            # Minimal, intentionally broad payload; API side should validate.
            "payload": {
                "scope": "player_season",
                "stat": "pts",
                "page": 1,
                "page_size": 10,
            },
        },
    ]

    results: List[Dict[str, Any]] = []

    for ep in endpoints:
        url = base_url + ep["path"]
        latencies: List[float] = []
        codes: List[int] = []
        for _ in range(n):
            elapsed_ms, status = _time_request(
                ep["method"],
                url,
                data=ep["payload"],
            )
            latencies.append(elapsed_ms)
            codes.append(status)

        stats = _stats(latencies)
        ok = any(code == 200 for code in codes)

        results.append(
            {
                "name": ep["name"],
                "method": ep["method"],
                "url": url,
                "n": n,
                "avg_ms": stats["avg_ms"],
                "p95_ms": stats["p95_ms"],
                "max_ms": stats["max_ms"],
                "ok": ok,
                "status_codes": sorted(set(codes)),
            },
        )

    return {"endpoints": results}


def main() -> None:
    report = run_benchmarks()
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

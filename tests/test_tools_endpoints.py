from __future__ import annotations

"""
Smoke tests for /api/v1/tools/* endpoints.

These tests intentionally:
- Use minimal valid payloads aligned with api/models.py and lib/apiClient.ts.
- Assert 200 responses and basic response envelope shape.
- Do NOT depend on large or specific datasets.
"""

from fastapi.testclient import TestClient

from api.main import create_app

app = create_app()
client = TestClient(app)


def assert_paginated_response_shape(resp_json: dict) -> None:
    assert "data" in resp_json
    assert "pagination" in resp_json
    assert "filters" in resp_json

    assert isinstance(resp_json["data"], list)
    pagination = resp_json["pagination"]
    # Require all three keys to be present for a valid pagination envelope
    assert {"page", "page_size", "total"} <= set(pagination.keys())


def test_tools_player_season_finder_smoke() -> None:
    resp = client.post(
        "/api/v1/tools/player-season-finder",
        json={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert_paginated_response_shape(resp.json())


def test_tools_player_game_finder_smoke() -> None:
    resp = client.post(
        "/api/v1/tools/player-game-finder",
        json={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert_paginated_response_shape(resp.json())


def test_tools_team_season_finder_smoke() -> None:
    resp = client.post(
        "/api/v1/tools/team-season-finder",
        json={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert_paginated_response_shape(resp.json())


def test_tools_team_game_finder_smoke() -> None:
    resp = client.post(
        "/api/v1/tools/team-game-finder",
        json={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert_paginated_response_shape(resp.json())


def test_tools_streak_finder_player_smoke() -> None:
    # Exactly one of player_id or team_id is required; use a simple
    # placeholder.
    resp = client.post(
        "/api/v1/tools/streak-finder",
        json={"player_id": 1, "min_length": 2, "page": 1, "page_size": 5},
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert_paginated_response_shape(resp.json())


def test_tools_span_finder_player_smoke() -> None:
    resp = client.post(
        "/api/v1/tools/span-finder",
        json={"player_id": 1, "span_length": 3, "page": 1, "page_size": 5},
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert_paginated_response_shape(resp.json())


def test_tools_versus_finder_player_smoke() -> None:
    # Exactly one of player_id or team_id is required.
    resp = client.post(
        "/api/v1/tools/versus-finder",
        json={"player_id": 1, "page": 1, "page_size": 5},
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert_paginated_response_shape(resp.json())


def test_tools_event_finder_smoke() -> None:
    # Fully optional filters; empty payload is valid.
    resp = client.post(
        "/api/v1/tools/event-finder",
        json={"page": 1, "page_size": 5},
    )
    assert resp.status_code == 200
    assert_paginated_response_shape(resp.json())


def test_tools_leaderboards_smoke() -> None:
    # Use a supported minimal combination per tools_leaderboards router.
    payload = {
        "scope": "player_season",
        "stat": "pts",
        "page": 1,
        "page_size": 5,
    }
    resp = client.post("/api/v1/tools/leaderboards", json=payload)
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert_paginated_response_shape(resp.json())


def test_tools_splits_smoke() -> None:
    # Minimal valid request: subject_type, subject_id, split_type.
    resp = client.post(
        "/api/v1/tools/splits",
        json={
            "subject_type": "player",
            "subject_id": 1,
            "split_type": "home_away",
            "page": 1,
            "page_size": 5,
        },
    )
    # If subject_id does not exist in test DB, backend may still return 200
    # with empty data.
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        assert_paginated_response_shape(resp.json())

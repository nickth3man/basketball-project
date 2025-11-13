from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from api.main import create_app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # Ensure we point at whatever DB the user configured for ETL; tests are
    # schema/shape-only and must not mutate data.
    os.environ.setdefault(
        "API_PG_DSN",
        (
            "postgresql+asyncpg://postgres:postgres"
            "@localhost:5432/basketball"
        ),
    )
    app = create_app()
    return TestClient(app)


@pytest.mark.skipif(
    os.getenv("API_SMOKE_SKIP_DB", "").lower() == "true",
    reason="DB not available; skipping integration-style smoke tests",
)
def test_get_players_schema(client: TestClient) -> None:
    resp = client.get("/api/v1/players")
    assert resp.status_code == 200
    body = resp.json()
    # Envelope keys
    assert set(body.keys()) == {"data", "pagination", "filters"}
    assert isinstance(body["data"], list)
    # Pagination meta
    pag = body["pagination"]
    assert {"page", "page_size", "total"} <= set(pag.keys())
    # Filters echo present
    assert "raw" in body["filters"]


@pytest.mark.skipif(
    os.getenv("API_SMOKE_SKIP_DB", "").lower() == "true",
    reason="DB not available; skipping integration-style smoke tests",
)
def test_get_games_schema(client: TestClient) -> None:
    resp = client.get("/api/v1/games")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "pagination", "filters"}
    assert isinstance(body["data"], list)
    pag = body["pagination"]
    assert {"page", "page_size", "total"} <= set(pag.keys())
    assert "raw" in body["filters"]


@pytest.mark.skipif(
    os.getenv("API_SMOKE_SKIP_DB", "").lower() == "true",
    reason="DB not available; skipping integration-style smoke tests",
)
def test_player_season_finder_schema(client: TestClient) -> None:
    # Minimal POST per spec; endpoint should exist and return envelope.
    payload = {
        "page": 1,
        "page_size": 5,
    }
    resp = client.post("/api/v1/tools/player-season-finder", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"data", "pagination", "filters"}
    assert isinstance(body["data"], list)
    pag = body["pagination"]
    assert {"page", "page_size", "total"} <= set(pag.keys())
    assert "raw" in body["filters"]
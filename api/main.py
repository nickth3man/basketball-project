from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .models import ErrorResponse
from .routers import (  # type: ignore  # populated by submodules
    core_players,
    core_teams,
    core_seasons,
    core_games,
    core_pbp,
    stats_player_seasons,
    stats_team_seasons,
    tools_player_finder,
    tools_team_finder,
    tools_streaks,
    tools_versus,
    tools_pbp_search,
    tools_leaderboards,
    tools_splits,
)

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application factory for the Phase 3 API.

    - Loads settings (for side effects / validation).
    - Registers global exception handlers.
    - Includes all routers under `/api/v1`.
    """
    get_settings()  # ensure settings are initialized

    app = FastAPI(title="Local Basketball Stats API", version="0.1.0")

    # Exception handlers -----------------------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.debug("Validation error: %s", exc)
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail="Invalid request").dict(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="Internal server error").dict(),
        )

    # Routers ---------------------------------------------------------------

    # Core entity routers
    app.include_router(core_players.router, prefix="/api/v1")
    app.include_router(core_teams.router, prefix="/api/v1")
    app.include_router(core_seasons.router, prefix="/api/v1")
    app.include_router(core_games.router, prefix="/api/v1")
    app.include_router(core_pbp.router, prefix="/api/v1")

    # Stats hubs
    app.include_router(stats_player_seasons.router, prefix="/api/v1")
    app.include_router(stats_team_seasons.router, prefix="/api/v1")

    # Tool endpoints
    app.include_router(tools_player_finder.router, prefix="/api/v1")
    app.include_router(tools_team_finder.router, prefix="/api/v1")
    app.include_router(tools_streaks.router, prefix="/api/v1")
    app.include_router(tools_versus.router, prefix="/api/v1")
    app.include_router(tools_pbp_search.router, prefix="/api/v1")
    app.include_router(tools_leaderboards.router, prefix="/api/v1")
    app.include_router(tools_splits.router, prefix="/api/v1")

    # Simple health endpoint (not versioned to keep local tooling easy)
    @app.get("/health", tags=["meta"])
    async def health() -> Dict[str, Any]:
        return {"status": "ok"}

    return app


if __name__ == "__main__":
    # Lightweight dev-only runner:
    # python -m api.main
    import uvicorn

    uvicorn.run(
        "api.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=False,
    )
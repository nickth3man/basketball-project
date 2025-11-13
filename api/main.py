from __future__ import annotations

import logging
import time
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import get_settings
from .logging_utils import get_logger, log_api_event
from .metrics_local import record_request
from .models import ErrorResponse
from .routers import (  # type: ignore  # populated by submodules
    core_players,
    core_teams,
    core_seasons,
    core_games,
    core_pbp,
    tools_player_finder,
    tools_team_finder,
    tools_streaks,
    tools_span,
    tools_versus,
    tools_pbp_search,
    tools_leaderboards,
    tools_splits,
    stats_player_seasons,
    stats_team_seasons,
    v2_tools_streaks,
    v2_tools_spans,
    v2_tools_leaderboards,
    v2_tools_splits,
    v2_tools_versus,
    v2_metrics,
    v2_saved_queries,
    health,
)

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Application factory for the Phase 3 API.

    - Loads settings (for side effects / validation).
    - Registers global exception handlers.
    - Includes all routers under `/api/v1`.
    """
    get_settings()  # ensure settings are initialized

    # Ensure root logging is configured once for the API process.
    get_logger("api.bootstrap")

    app = FastAPI(title="Local Basketball Stats API", version="0.1.0")

    # Exception handlers -----------------------------------------------------

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        log_api_event(
            logger,
            "request_validation_error",
            level=logging.WARNING,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(detail="Invalid request").dict(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        log_api_event(
            logger,
            "unhandled_exception",
            level=logging.ERROR,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="Internal server error").dict(),
        )

    # Request/response logging middleware -----------------------------------

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """
        Lightweight structured logging middleware.

        - Generates request_id per request.
        - Logs request start and response completion.
        - Records local in-memory metrics.
        """
        start = time.monotonic()
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        path = request.url.path
        method = request.method

        request_id = request.headers.get("x-request-id") or str(id(request))

        log_api_event(
            logger,
            "request",
            method=method,
            path=path,
            client_ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
        )

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Ensure we still log a response event on unexpected errors.
            status_code = 500
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000.0
            log_api_event(
                logger,
                "response",
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=round(duration_ms, 3),
                request_id=request_id,
            )
            # Update local in-memory metrics (cheap counters).
            try:
                record_request(path, duration_ms)
            except Exception:
                # Metrics must never break requests.
                pass

        return response

    # Routers ---------------------------------------------------------------

    # Core entity routers
    app.include_router(core_players.router, prefix="/api/v1")
    app.include_router(core_teams.router, prefix="/api/v1")
    app.include_router(core_seasons.router, prefix="/api/v1")
    app.include_router(core_games.router, prefix="/api/v1")
    app.include_router(core_pbp.router, prefix="/api/v1")

    # Tool endpoints
    app.include_router(tools_player_finder.router, prefix="/api/v1")
    app.include_router(tools_team_finder.router, prefix="/api/v1")
    app.include_router(tools_streaks.router, prefix="/api/v1")
    app.include_router(tools_span.router, prefix="/api/v1")
    app.include_router(tools_versus.router, prefix="/api/v1")
    # tools_pbp_search is provided as alias from tools_event_finder
    app.include_router(tools_pbp_search.router, prefix="/api/v1")
    app.include_router(tools_leaderboards.router, prefix="/api/v1")
    app.include_router(tools_splits.router, prefix="/api/v1")

    # Stats endpoints
    app.include_router(stats_player_seasons.router, prefix="/api/v1")
    app.include_router(stats_team_seasons.router, prefix="/api/v1")

    # v2 generalized tool endpoints (additive; do not change v1 behavior)
    app.include_router(v2_tools_streaks.router, prefix="/api/v2")
    app.include_router(v2_tools_spans.router, prefix="/api/v2")
    app.include_router(v2_tools_leaderboards.router, prefix="/api/v2")
    app.include_router(v2_tools_splits.router, prefix="/api/v2")
    app.include_router(v2_tools_versus.router, prefix="/api/v2")
    app.include_router(v2_metrics.router, prefix="/api/v2")
    app.include_router(v2_saved_queries.router, prefix="/api/v2")

    # Health endpoints (v1 router exposes /api/v1/health/*)
    app.include_router(health.router)

    # Legacy simple health endpoint (backwards compatible, trivial check).
    @app.get("/health", tags=["meta"])
    async def legacy_health() -> Dict[str, Any]:
        # Intentionally shallow: no DB, no FS, matches historical behavior.
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

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response

from .config import get_settings
from .logging_utils import get_logger, log_api_event
from .metrics_local import record_request
from .middleware.auth import auth_middleware
from .middleware.rate_limit import rate_limit_middleware
from .models import ErrorResponse
from .routers import (
    core_games,
    core_pbp,
    core_players,
    core_seasons,
    core_teams,
    health,
    stats_player_seasons,
    stats_team_seasons,
    tools_event_finder,
    tools_leaderboards,
    tools_player_finder,
    tools_span,
    tools_splits,
    tools_streaks,
    tools_team_finder,
    tools_versus,
    v2_metrics,
    v2_saved_queries,
    v2_tools_leaderboards,
    v2_tools_spans,
    v2_tools_splits,
    v2_tools_streaks,
    v2_tools_versus,
)

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """
    Application factory for the Phase 3 API.

    - Loads settings (for side effects / validation).
    - Registers global exception handlers.
    - Includes all routers under `/api/v1`.

    Threading model: Single-threaded async (FastAPI + uvicorn workers).
    No shared mutable state beyond DB connection pool.
    """
    # [NOTE][SECURITY] Authentication implemented via middleware.
    # Set API_KEY env var to enable; unset for local dev mode.

    # [NOTE][SECURITY] Rate limiting: 100 requests/min per IP.
    # For production, consider Redis-backed solution (slowapi).

    get_settings()  # ensure settings are initialized

    # Ensure root logging is configured once for the API process.
    get_logger("api.bootstrap")

    app = FastAPI(title="Local Basketball Stats API", version="0.1.0")

    # Middleware ------------------------------------------------------------

    @app.middleware("http")
    async def auth_check(request: Request, call_next: Callable) -> Response:
        """Auth middleware: API key validation (optional)."""
        return await auth_middleware(request, call_next)

    @app.middleware("http")
    async def rate_limit_check(request: Request, call_next: Callable) -> Response:
        """Rate limit: 100 req/min per IP (in-memory)."""
        return await rate_limit_middleware(request, call_next)

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
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Log exception details without exposing to client
        logger.exception(
            "Unhandled exception",
            extra={
                "path": request.url.path,
                "method": request.method,
                "exc_type": type(exc).__name__,
            },
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(detail="Internal server error").dict(),
        )

    # Request/response logging middleware -----------------------------------

    @app.middleware("http")
    async def log_requests(request: Request, call_next: Callable) -> Any:
        """Structured logging with request_id and metrics."""
        start = time.monotonic()
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        path = request.url.path
        method = request.method
        # Use x-request-id header or generate from object id
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

    # Routers -------------------------------------------------------

    API_V1 = "/api/v1"
    API_V2 = "/api/v2"

    # Core entity routers
    app.include_router(core_players.router, prefix=API_V1)
    app.include_router(core_teams.router, prefix=API_V1)
    app.include_router(core_seasons.router, prefix=API_V1)
    app.include_router(core_games.router, prefix=API_V1)
    app.include_router(core_pbp.router, prefix=API_V1)

    # Tool endpoints
    app.include_router(tools_player_finder.router, prefix=API_V1)
    app.include_router(tools_team_finder.router, prefix=API_V1)
    app.include_router(tools_streaks.router, prefix=API_V1)
    app.include_router(tools_span.router, prefix=API_V1)
    app.include_router(tools_versus.router, prefix=API_V1)
    app.include_router(tools_event_finder.router, prefix=API_V1)
    app.include_router(tools_leaderboards.router, prefix=API_V1)
    app.include_router(tools_splits.router, prefix=API_V1)

    # Stats endpoints
    app.include_router(stats_player_seasons.router, prefix=API_V1)
    app.include_router(stats_team_seasons.router, prefix=API_V1)

    # v2 endpoints
    app.include_router(v2_tools_streaks.router, prefix=API_V2)
    app.include_router(v2_tools_spans.router, prefix=API_V2)
    app.include_router(v2_tools_leaderboards.router, prefix=API_V2)
    app.include_router(v2_tools_splits.router, prefix=API_V2)
    app.include_router(v2_tools_versus.router, prefix=API_V2)
    app.include_router(v2_metrics.router, prefix=API_V2)
    app.include_router(v2_saved_queries.router, prefix=API_V2)

    # Health (already includes /api/v1/health/* in routes)
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

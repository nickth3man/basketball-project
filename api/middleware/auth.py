"""
Authentication middleware for the Basketball Stats API.

Implements API key authentication for production deployments.
Local development can bypass auth by not setting API_KEY env var.
"""

from __future__ import annotations

import os
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import Response


def get_api_key() -> str | None:
    """Get API key from environment. Returns None if not configured."""
    return os.getenv("API_KEY")


async def auth_middleware(request: Request, call_next: Callable) -> Response:
    """
    Validate API key for all requests except health endpoints.

    Preconditions: API_KEY env var set (or None for local dev).
    Postconditions: Request proceeds if auth valid or bypassed.
    Side effects: Raises HTTPException 401 on auth failure.
    """
    api_key = get_api_key()

    # Bypass auth if API_KEY not configured (local dev mode)
    if api_key is None:
        return await call_next(request)

    # Skip auth for health endpoints
    if request.url.path in {"/health", "/api/v1/health"}:
        return await call_next(request)

    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Validate API key format: "Bearer <key>"
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    provided_key = parts[1]
    if provided_key != api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await call_next(request)


__all__ = ["auth_middleware", "get_api_key"]

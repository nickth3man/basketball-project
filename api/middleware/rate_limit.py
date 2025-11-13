"""
Simple in-memory rate limiting middleware.

For production use, consider Redis-backed rate limiting (slowapi).
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable

from fastapi import HTTPException, Request, status
from fastapi.responses import Response

# In-memory rate limit tracking
# Key: client IP, Value: list of request timestamps
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# Configuration
RATE_LIMIT_REQUESTS = 100  # requests
RATE_LIMIT_WINDOW = 60  # seconds (1 minute)


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """
    Simple in-memory rate limiting.

    Limits: 100 requests per minute per IP.

    Preconditions: None (runs for all requests).
    Postconditions: Request proceeds if within rate limit.
    Side effects: Updates in-memory rate limit store.
    """
    # Skip rate limiting for health endpoints
    if request.url.path in {"/health", "/api/v1/health"}:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Clean old entries
    timestamps = _rate_limit_store[client_ip]
    cutoff = now - RATE_LIMIT_WINDOW
    _rate_limit_store[client_ip] = [ts for ts in timestamps if ts > cutoff]

    # Check rate limit
    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s",
            headers={"Retry-After": str(RATE_LIMIT_WINDOW)},
        )

    # Record request
    _rate_limit_store[client_ip].append(now)

    return await call_next(request)


__all__ = ["rate_limit_middleware"]

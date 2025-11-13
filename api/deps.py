from __future__ import annotations

from typing import Iterable, List, Tuple

from fastapi import HTTPException, Query, status

from .config import get_settings
from .db import AsyncSession
from .db import get_db as _get_db

settings = get_settings()


async def get_db() -> AsyncSession:
    """
    FastAPI dependency wrapper around [`api.db.get_db()`](api/db.py:1).

    Kept here so routers import from a single deps module.
    """
    async for session in _get_db():
        return session
    # Defensive: should never reach here
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Database session acquisition failed",
    )


def get_pagination(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int | None = Query(
        None,
        description="Page size; defaults to configured page_size_default",
    ),
) -> Tuple[int, int]:
    """
    Validate and normalize pagination parameters.

    - Enforces `page >= 1`.
    - Applies global page_size_default / page_size_max from settings.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page must be >= 1",
        )

    if page_size is None:
        page_size = settings.page_size_default

    if page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page_size must be >= 1",
        )

    if page_size > settings.page_size_max:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size must be <= {settings.page_size_max}",
        )

    return page, page_size


def parse_comma_ints(value: str | None) -> List[int]:
    """
    Parse a comma-separated string of ints into a list.

    Returns [] for None/empty.
    Raises 400 on invalid integers.
    """
    if not value:
        return []
    try:
        return [int(v) for v in value.split(",") if v.strip()]
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid integer list",
        ) from exc


def parse_bool(value: str | None) -> bool | None:
    """
    Parse a boolean-ish query string value.

    Accepts: "true"/"1"/"yes"/"y" and "false"/"0"/"no"/"n" (case-insensitive).
    Returns None if value is None or empty.
    Raises 400 on unknown values.
    """
    if value is None or value == "":
        return None

    normalized = value.strip().lower()
    truthy = {"true", "1", "yes", "y", "on"}
    falsy = {"false", "0", "no", "n", "off"}

    if normalized in truthy:
        return True
    if normalized in falsy:
        return False

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid boolean value",
    )


def parse_comma_strings(value: str | None) -> List[str]:
    """
    Parse a comma-separated string into a list of non-empty trimmed strings.
    """
    if not value:
        return []
    items: Iterable[str] = (v.strip() for v in value.split(","))
    return [v for v in items if v]


__all__ = [
    "get_db",
    "get_pagination",
    "parse_comma_ints",
    "parse_bool",
    "parse_comma_strings",
]

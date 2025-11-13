from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from api.models_v2 import (
    PaginationMetaV2,
    PaginatedResponseV2,
    QueryFiltersEchoV2,
    SpansQueryV2,
    SpansQueryResponseV2,
    SpansResultRowV2,
)


router = APIRouter(tags=["tools-v2-spans"])


MAX_PAGE_SIZE = 500
MAX_METRICS = 25
MAX_SUBJECT_IDS = 200


def _normalize_filters(query: SpansQueryV2) -> Dict[str, Any]:
    """Minimal normalized filter echo for introspection/debugging."""

    return {
        "season_filter": (query.season_filter.dict() if query.season_filter else None),
        "date_range": (query.date_range.dict() if query.date_range else None),
        "game_type": (query.game_type.dict() if query.game_type else None),
        "team_filter": (query.team_filter.dict() if query.team_filter else None),
        "player_filter": (query.player_filter.dict() if query.player_filter else None),
        "opponent_filter": (
            query.opponent_filter.dict() if query.opponent_filter else None
        ),
        "location_filter": (
            query.location_filter.dict() if query.location_filter else None
        ),
        "result_filter": (query.result_filter.dict() if query.result_filter else None),
        "subject_type": query.subject_type.value,
        "subject_ids": query.subject_ids,
        "span_mode": query.span_mode.value,
    }


def _validate_query(query: SpansQueryV2) -> None:
    if query.page and query.page.page_size > MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size cannot exceed {MAX_PAGE_SIZE}",
        )

    if len(query.metrics) > MAX_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many metrics requested (max {MAX_METRICS})",
        )

    if len(query.subject_ids) > MAX_SUBJECT_IDS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"subject_ids cannot exceed {MAX_SUBJECT_IDS} items",
        )


@router.post(
    "/tools/spans",
    response_model=SpansQueryResponseV2,
    status_code=status.HTTP_200_OK,
)
async def spans_v2(query: SpansQueryV2) -> SpansQueryResponseV2:
    """Generalized v2 spans tool.

    Current implementation:
    - Validates structural constraints only.
    - Returns an empty paginated result with normalized filter echo.
    - Does NOT access the database yet.

    TODO:
    - Integrate with metrics registry (Epic C).
    - Implement span computation over games dataset.
    - Respect ETL metadata for filter normalization (Epic A).
    """
    _validate_query(query)

    page_spec = query.page or query.page.__class__(  # type: ignore[union-attr]
        page=1,
        page_size=50,
    )

    pagination = PaginationMetaV2(
        page=page_spec.page,
        page_size=min(page_spec.page_size, MAX_PAGE_SIZE),
        total=0,
    )
    filters = QueryFiltersEchoV2(normalized=_normalize_filters(query))

    return PaginatedResponseV2[SpansResultRowV2](
        data=[],
        pagination=pagination,
        filters=filters,
    )

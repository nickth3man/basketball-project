from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status

from api.models_v2 import (
    MAX_METRICS,
    MAX_PAGE_SIZE,
    MAX_SPLIT_DIMENSIONS,
    PaginatedResponseV2,
    PaginationMetaV2,
    QueryFiltersEchoV2,
    SplitsQueryResponseV2,
    SplitsQueryV2,
    SplitsResultRowV2,
)

router = APIRouter(tags=["tools-v2-splits"])


def _normalize_filters(query: SplitsQueryV2) -> Dict[str, Any]:
    """Minimal normalized filter echo for introspection/debugging."""

    return {
        "subject_type": query.subject_type.value,
        "subject_id": query.subject_id,
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
        "split_dimensions": [dim.id for dim in query.split_dimensions],
    }


def _validate_query(query: SplitsQueryV2) -> None:
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

    if len(query.split_dimensions) > MAX_SPLIT_DIMENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Too many split dimensions requested (max {MAX_SPLIT_DIMENSIONS})"
            ),
        )


@router.post(
    "/tools/splits",
    response_model=SplitsQueryResponseV2,
    status_code=status.HTTP_200_OK,
)
async def splits_v2(query: SplitsQueryV2) -> SplitsQueryResponseV2:
    """Generalized v2 splits tool.

    Current implementation:
    - Validates structural constraints only.
    - Returns an empty paginated result with normalized filter echo.
    - Does NOT access the database yet.

    TODO:
    - Integrate with metrics registry (Epic C).
    - Implement split aggregations over games dataset.
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

    return PaginatedResponseV2[SplitsResultRowV2](
        data=[],
        pagination=pagination,
        filters=filters,
    )

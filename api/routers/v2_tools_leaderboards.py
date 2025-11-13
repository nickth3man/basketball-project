from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from api.models_v2 import (
    LeaderboardsQueryResponseV2,
    LeaderboardsQueryV2,
    LeaderboardsResultRowV2,
    PaginatedResponseV2,
    PaginationMetaV2,
    QueryFiltersEchoV2,
)

router = APIRouter(tags=["tools-v2-leaderboards"])


MAX_PAGE_SIZE = 500
MAX_METRICS = 25


def _normalize_filters(query: LeaderboardsQueryV2) -> Dict[str, Any]:
    """Minimal normalized filter echo for introspection/debugging."""

    return {
        "entity_type": query.entity_type.value,
        "season_filter": query.season_filter.dict(),
        "game_type": (query.game_type.dict() if query.game_type else None),
        "team_filter": (query.team_filter.dict() if query.team_filter else None),
        "player_filter": (query.player_filter.dict() if query.player_filter else None),
        "location_filter": (
            query.location_filter.dict() if query.location_filter else None
        ),
        "result_filter": (query.result_filter.dict() if query.result_filter else None),
        "min_games": query.min_games,
        "min_minutes": query.min_minutes,
        "min_attempts_by_metric": query.min_attempts_by_metric,
        "primary_metric_id": query.primary_metric_id,
    }


def _validate_query(query: LeaderboardsQueryV2) -> None:
    if query.page.page_size > MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size cannot exceed {MAX_PAGE_SIZE}",
        )

    if len(query.metrics) > MAX_METRICS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Too many metrics requested (max {MAX_METRICS})",
        )


@router.post(
    "/tools/leaderboards",
    response_model=LeaderboardsQueryResponseV2,
    status_code=status.HTTP_200_OK,
)
async def leaderboards_v2(
    query: LeaderboardsQueryV2,
) -> LeaderboardsQueryResponseV2:
    """Generalized v2 leaderboards tool.

    Current implementation:
    - Validates structural constraints only.
    - Returns an empty paginated result with normalized filter echo.
    - Does NOT access the database yet.

    TODO:
    - Integrate with metrics registry (Epic C).
    - Implement leaderboard computation based on configured metrics.
    - Respect ETL metadata for filter normalization (Epic A).
    """
    _validate_query(query)

    page_size = min(query.page.page_size, MAX_PAGE_SIZE)
    pagination = PaginationMetaV2(
        page=query.page.page,
        page_size=page_size,
        total=0,
    )
    filters = QueryFiltersEchoV2(normalized=_normalize_filters(query))

    return PaginatedResponseV2[LeaderboardsResultRowV2](
        data=[],
        pagination=pagination,
        filters=filters,
    )


# -------------------------
# CSV export
# -------------------------


def _leaderboards_csv_headers() -> list[str]:
    # Stable header order; matches LeaderboardsResultRowV2 structure
    return [
        "entity_type",
        "entity_id",
        "label",
        "season_end_year",
        "metrics_json",
        "rank",
    ]


def _leaderboards_row_to_csv(row: LeaderboardsResultRowV2) -> list[str]:
    from json import dumps

    return [
        row.entity_type.value,
        str(row.entity_id),
        row.label,
        "" if row.season_end_year is None else str(row.season_end_year),
        dumps(row.metrics, sort_keys=True),
        str(row.rank),
    ]


@router.post(
    "/tools/leaderboards/export",
    status_code=status.HTTP_200_OK,
    response_class=PlainTextResponse,
)
async def export_leaderboards_v2(
    query: LeaderboardsQueryV2,
) -> PlainTextResponse:
    """CSV export for v2 leaderboards.

    Uses the same request model as the JSON endpoint.
    Current implementation mirrors the placeholder JSON behavior:
    it validates input and emits only CSV headers (no data rows yet).
    """
    _validate_query(query)

    # Placeholder: no computed rows yet; emit only header.
    headers = _leaderboards_csv_headers()
    csv_content = ",".join(headers) + "\n"

    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="leaderboards_v2_export.csv"'
            ),
        },
    )

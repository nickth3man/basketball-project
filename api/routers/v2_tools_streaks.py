from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import PlainTextResponse

from api.models_v2 import (
    QueryFiltersEchoV2,
    PaginationMetaV2,
    PageSpecV2,
    StreaksQueryV2,
    StreaksQueryResponseV2,
)


router = APIRouter(tags=["tools-v2-streaks"])


MAX_PAGE_SIZE = 500
MAX_METRICS = 25
MAX_SUBJECT_IDS = 200


def _normalize_filters(query: StreaksQueryV2) -> Dict[str, Any]:
    """Minimal normalized filter echo for introspection/debugging.

    This should remain JSON-serializable and stable as a contract.
    """
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
        "stat_metric": query.stat_metric.dict(),
    }


def _validate_query(query: StreaksQueryV2) -> None:
    page = query.page
    if page and page.page_size > MAX_PAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"page_size cannot exceed {MAX_PAGE_SIZE}",
        )

    metrics = [query.stat_metric] + list(query.metrics or [])
    if len(metrics) > MAX_METRICS:
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
    "/tools/streaks",
    response_model=StreaksQueryResponseV2,
    status_code=status.HTTP_200_OK,
)
async def streaks_v2(query: StreaksQueryV2) -> StreaksQueryResponseV2:
    """Generalized v2 streaks tool.

    Current implementation:
    - Validates structural constraints only.
    - Returns an empty paginated result with normalized filter echo.
    - Does NOT access the database yet.

    TODO:
    - Integrate with metrics registry (Epic C).
    - Implement streak computation over games dataset.
    - Respect ETL metadata for filter normalization (Epic A).
    """
    _validate_query(query)

    # Default pagination if not provided
    page_spec = query.page or PageSpecV2()
    page_size = min(page_spec.page_size, MAX_PAGE_SIZE)

    pagination = PaginationMetaV2(
        page=page_spec.page,
        page_size=page_size,
        total=0,
    )
    filters = QueryFiltersEchoV2(normalized=_normalize_filters(query))

    return StreaksQueryResponseV2(
        data=[],
        pagination=pagination,
        filters=filters,
    )


# -------------------------
# CSV export
# -------------------------


def _streaks_csv_headers() -> List[str]:
    return [
        "subject_type",
        "subject_id",
        "streak_id",
        "start_game_id",
        "end_game_id",
        "start_date",
        "end_date",
        "length",
        "metric_id",
        "metric_value",
        "games_count",
        "is_active",
    ]


@router.post(
    "/tools/streaks/export",
    status_code=status.HTTP_200_OK,
    response_class=PlainTextResponse,
)
async def export_streaks_v2(
    query: StreaksQueryV2,
) -> PlainTextResponse:
    """CSV export for v2 streaks.

    Uses same request model as JSON endpoint. Placeholder implementation:
    validates input and returns only CSV headers (no data rows yet).
    """
    _validate_query(query)

    headers = _streaks_csv_headers()
    csv_content = ",".join(headers) + "\n"

    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": ('attachment; filename="streaks_v2_export.csv"'),
        },
    )

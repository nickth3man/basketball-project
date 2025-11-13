from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    TeamSeasonSummary,
)

router = APIRouter(tags=["stats-team-seasons"])


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be >= 1",
        )


@router.get(
    "/stats/team-seasons",
    response_model=PaginatedResponse[TeamSeasonSummary],
    responses={400: {"model": ErrorResponse}},
)
async def get_team_seasons_stats(
    db: AsyncSession = Depends(get_db),
    team_id: int | None = Query(None),
    season_end_year: int | None = Query(None),
    is_playoffs: bool | None = Query(None),
    min_g: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
) -> PaginatedResponse[TeamSeasonSummary]:
    """
    Paginated team-season stats backed by vw_team_season_advanced.

    Filters are optional and only applied when provided.
    Ordering is deterministic:
    - season_end_year DESC, team_id ASC, team_season_id ASC
    """
    _validate_pagination(page, page_size)

    where_clauses: List[str] = []
    params: Dict[str, Any] = {}
    echo: Dict[str, Any] = {}

    if team_id is not None:
        where_clauses.append("team_id = :team_id")
        params["team_id"] = team_id
        echo["team_id"] = team_id

    if season_end_year is not None:
        where_clauses.append("season_end_year = :season_end_year")
        params["season_end_year"] = season_end_year
        echo["season_end_year"] = season_end_year

    if is_playoffs is not None:
        where_clauses.append("is_playoffs = :is_playoffs")
        params["is_playoffs"] = is_playoffs
        echo["is_playoffs"] = is_playoffs

    if min_g is not None:
        where_clauses.append("g >= :min_g")
        params["min_g"] = min_g
        echo["min_g"] = min_g

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    count_sql = text(
        f"""
        SELECT COUNT(*) AS total
        FROM vw_team_season_advanced
        {where_sql}
        """
    )
    result = await db.execute(count_sql, params)
    total = int(result.scalar_one())

    offset = (page - 1) * page_size

    data_sql = text(
        f"""
        SELECT
            team_season_id,
            team_id,
            season_end_year,
            is_playoffs,
            g,
            pts,
            opp_pts
        FROM vw_team_season_advanced
        {where_sql}
        ORDER BY season_end_year DESC, team_id ASC, team_season_id ASC
        LIMIT :limit OFFSET :offset
        """
    )
    data_params = dict(params)
    data_params["limit"] = page_size
    data_params["offset"] = offset

    rows = (await db.execute(data_sql, data_params)).mappings().all()
    data = [TeamSeasonSummary(**dict(row)) for row in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
        ),
        filters=FiltersEcho(raw=echo),
    )

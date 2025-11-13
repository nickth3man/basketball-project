from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    PlayerSeasonSummary,
)

router = APIRouter(tags=["stats-player-seasons"])


def _validate_pagination(page: int, page_size: int) -> None:
    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be >= 1",
        )


@router.get(
    "/stats/player-seasons",
    response_model=PaginatedResponse[PlayerSeasonSummary],
    responses={400: {"model": ErrorResponse}},
)
async def get_player_seasons_stats(
    db: AsyncSession = Depends(get_db),
    player_id: int | None = Query(None),
    season_end_year: int | None = Query(None),
    team_id: int | None = Query(None),
    is_playoffs: bool | None = Query(None),
    min_g: int | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
) -> PaginatedResponse[PlayerSeasonSummary]:
    """
    Paginated player-season advanced stats backed by vw_player_season_advanced.

    Filters are optional and only applied when provided.
    Ordering is deterministic for stable pagination:
    - season_end_year DESC, player_id ASC, seas_id ASC
    """
    # Explicit validation to ensure we return ErrorResponse shape
    _validate_pagination(page, page_size)

    where_clauses: List[str] = []
    params: Dict[str, Any] = {}
    echo: Dict[str, Any] = {}

    if player_id is not None:
        where_clauses.append("player_id = :player_id")
        params["player_id"] = player_id
        echo["player_id"] = player_id

    if season_end_year is not None:
        where_clauses.append("season_end_year = :season_end_year")
        params["season_end_year"] = season_end_year
        echo["season_end_year"] = season_end_year

    if team_id is not None:
        where_clauses.append("team_id = :team_id")
        params["team_id"] = team_id
        echo["team_id"] = team_id

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
        FROM vw_player_season_advanced
        {where_sql}
        """
    )

    result = await db.execute(count_sql, params)
    total = int(result.scalar_one())

    offset = (page - 1) * page_size

    data_sql = text(
        f"""
        SELECT
            seas_id,
            player_id,
            season_end_year,
            team_id,
            team_abbrev,
            is_total,
            is_playoffs,
            g,
            pts_per_g,
            trb_per_g,
            ast_per_g
        FROM vw_player_season_advanced
        {where_sql}
        ORDER BY season_end_year DESC, player_id ASC, seas_id ASC
        LIMIT :limit OFFSET :offset
        """
    )

    data_params = dict(params)
    data_params["limit"] = page_size
    data_params["offset"] = offset

    rows = (await db.execute(data_sql, data_params)).mappings().all()

    data = [PlayerSeasonSummary(**dict(row)) for row in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
        ),
        filters=FiltersEcho(raw=echo),
    )

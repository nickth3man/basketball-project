from __future__ import annotations

from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import (
    build_pagination_query,
    build_players_query,
    parse_bool,
    player_season_pg_table,
    player_season_table,
    players_table,
)
from api.deps import (
    get_db,
    get_pagination,
)
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    Player,
    PlayerSeasonSummary,
)

router = APIRouter(tags=["players"])


@router.get("/players", response_model=PaginatedResponse)
async def list_players(
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
    player_ids: str | None = Query(
        None,
        description="Comma-separated list of player_id values.",
    ),
    q: str | None = Query(
        None,
        description="Free-text search over name fields.",
    ),
    is_active: str | None = Query(
        None,
        description="Boolean flag for active players.",
    ),
    hof: str | None = Query(
        None,
        description="Boolean flag for Hall-of-Fame inductees.",
    ),
    from_season: int | None = Query(
        None,
        description="Filter players with seasons on/after this year.",
    ),
    to_season: int | None = Query(
        None,
        description="Filter players with seasons on/before this year.",
    ),
) -> PaginatedResponse:
    page, page_size = page_data

    # Parse boolean query parameters
    is_active_val = parse_bool(is_active)
    hof_val = parse_bool(hof)

    # Build base query with filters
    query = build_players_query(
        filters=[],
        season_filter=(from_season, to_season) if from_season or to_season else None,
        search_term=q,
        active_only=is_active_val,
        hof_only=hof_val,
    )

    # Get total count
    # [NOTE][PERF] Counting via subquery is correct but may be slow on large tables.
    # Consider approximate counts (pg_class.reltuples) for very large datasets.
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Add pagination
    paginated_query = build_pagination_query(query, page, page_size)

    # Execute query
    rows = (await db.execute(paginated_query)).mappings()
    data = [Player(**dict(row)) for row in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(
            raw={
                "player_ids": player_ids,
                "q": q,
                "is_active": is_active,
                "hof": hof,
                "from_season": from_season,
                "to_season": to_season,
            }
        ),
    )


@router.get(
    "/players/{player_id}",
    response_model=Player,
    responses={404: {"model": ErrorResponse}},
)
async def get_player(
    player_id: int,
    db: AsyncSession = Depends(get_db),
) -> Player:
    # Build query for single player
    query = select(players_table).where(players_table.c.player_id == player_id).limit(1)
    row = (await db.execute(query)).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    return Player(**dict(row))


@router.get(
    "/players/{player_id}/seasons",
    response_model=PaginatedResponse,
)
async def get_player_seasons(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
) -> PaginatedResponse:
    page, page_size = page_data

    # Build query for player seasons
    query = (
        select(
            player_season_table.c.seas_id,
            player_season_table.c.player_id,
            player_season_table.c.season_end_year,
            player_season_table.c.team_id,
            player_season_table.c.team_abbrev,
            player_season_table.c.is_total,
            player_season_table.c.is_playoffs,
            player_season_pg_table.c.g,
            player_season_pg_table.c.pts_per_g,
            player_season_pg_table.c.trb_per_g,
            player_season_pg_table.c.ast_per_g,
        )
        .join(
            player_season_pg_table,
            player_season_pg_table.c.seas_id == player_season_table.c.seas_id,
            isouter=True,
        )
        .where(player_season_table.c.player_id == player_id)
        .order_by(player_season_table.c.season_end_year, player_season_table.c.seas_id)
    )

    # Get total count
    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Add pagination and execute
    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [PlayerSeasonSummary(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw={"player_id": player_id}),
    )

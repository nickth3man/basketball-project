from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, table, column
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_pagination, parse_bool, parse_comma_ints
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    Player,
    PlayerSeasonSummary,
)

router = APIRouter(tags=["players"])


def _players_table():
    return table(
        "players",
        column("player_id"),
        column("slug"),
        column("full_name"),
        column("first_name"),
        column("last_name"),
        column("is_active"),
        column("hof_inducted"),
        column("rookie_year"),
        column("final_year"),
    )


def _player_season_table():
    return table(
        "player_season",
        column("seas_id"),
        column("player_id"),
        column("season_end_year"),
        column("team_id"),
        column("team_abbrev"),
        column("is_total"),
        column("is_playoffs"),
    )


def _player_season_pg_table():
    return table(
        "player_season_per_game",
        column("seas_id"),
        column("g"),
        column("pts_per_g"),
        column("trb_per_g"),
        column("ast_per_g"),
    )


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

    filters: List[Any] = []
    echo: Dict[str, Any] = {}

    ids = parse_comma_ints(player_ids)
    if ids:
        filters.append(("player_id", "in", ids))
        echo["player_ids"] = ids

    if q:
        echo["q"] = q

    is_active_val = parse_bool(is_active)
    if is_active_val is not None:
        echo["is_active"] = is_active_val

    hof_val = parse_bool(hof)
    if hof_val is not None:
        echo["hof"] = hof_val

    if from_season is not None:
        echo["from_season"] = from_season
    if to_season is not None:
        echo["to_season"] = to_season

    players = _players_table()
    query = select(
        players.c.player_id,
        players.c.slug,
        players.c.full_name,
        players.c.first_name,
        players.c.last_name,
        players.c.is_active,
        players.c.hof_inducted,
        players.c.rookie_year,
        players.c.final_year,
    )

    # Optional join to player_season when season filters present
    if from_season is not None or to_season is not None:
        ps = _player_season_table()
        query = query.join(ps, ps.c.player_id == players.c.player_id)
        season_clauses = []
        if from_season is not None:
            season_clauses.append(ps.c.season_end_year >= from_season)
        if to_season is not None:
            season_clauses.append(ps.c.season_end_year <= to_season)
        if season_clauses:
            query = query.where(and_(*season_clauses))

    # Apply dynamic filters
    where_clauses = []
    for key, op, value in filters:
        col = getattr(players.c, key)
        if op == "in":
            where_clauses.append(col.in_(value))

    if is_active_val is not None:
        where_clauses.append(players.c.is_active.is_(is_active_val))
    if hof_val is not None:
        where_clauses.append(players.c.hof_inducted.is_(hof_val))

    if q:
        pattern = f"%{q.lower()}%"
        where_clauses.append(
            or_(
                func.lower(players.c.full_name).like(pattern),
                func.lower(players.c.first_name).like(pattern),
                func.lower(players.c.last_name).like(pattern),
                func.lower(players.c.slug).like(pattern),
            )
        )

    if where_clauses:
        query = query.where(and_(*where_clauses))

    # Deterministic ordering
    query = query.order_by(
        players.c.full_name.nulls_last(),
        players.c.player_id,
    )

    # Total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar_one()

    # Page slice
    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [Player(**dict(row)) for row in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
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
    players = _players_table()

    stmt = (
        select(
            players.c.player_id,
            players.c.slug,
            players.c.full_name,
            players.c.first_name,
            players.c.last_name,
            players.c.is_active,
            players.c.hof_inducted,
            players.c.rookie_year,
            players.c.final_year,
        )
        .where(players.c.player_id == player_id)
        .limit(1)
    )

    row = (await db.execute(stmt)).mappings().first()
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

    ps = _player_season_table()
    pspg = _player_season_pg_table()

    base = (
        select(
            ps.c.seas_id,
            ps.c.player_id,
            ps.c.season_end_year,
            ps.c.team_id,
            ps.c.team_abbrev,
            ps.c.is_total,
            ps.c.is_playoffs,
            pspg.c.g,
            pspg.c.pts_per_g,
            pspg.c.trb_per_g,
            pspg.c.ast_per_g,
        )
        .join(pspg, pspg.c.seas_id == ps.c.seas_id, isouter=True)
        .where(ps.c.player_id == player_id)
        .order_by(ps.c.season_end_year, ps.c.seas_id)
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(base.limit(page_size).offset(offset))
    ).mappings()

    data = [PlayerSeasonSummary(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw={"player_id": player_id}),
    )
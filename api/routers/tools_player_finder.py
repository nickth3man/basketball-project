from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    PlayerGameFinderRequest,
    PlayerGameFinderResponseRow,
    PlayerSeasonFinderRequest,
    PlayerSeasonFinderResponseRow,
)

router = APIRouter(tags=["tools", "player-finder"])


def _players_table():
    return table(
        "players",
        column("player_id"),
        column("full_name"),
    )


def _player_season_table():
    return table(
        "player_season",
        column("seas_id"),
        column("player_id"),
        column("season_end_year"),
        column("team_id"),
        column("is_total"),
        column("is_playoffs"),
    )


def _player_season_pg_table():
    return table(
        "player_season_per_game",
        column("seas_id"),
        column("g"),
        column("pts_per_g"),
    )


def _boxscore_player_table():
    return table(
        "boxscore_player",
        column("game_id"),
        column("player_id"),
        column("season_end_year"),
        column("pts"),
        column("trb"),
        column("ast"),
        column("is_playoffs"),
    )


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


@router.post(
    "/tools/player-season-finder",
    response_model=PaginatedResponse[PlayerSeasonFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def player_season_finder(
    req: PlayerSeasonFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PlayerSeasonFinderResponseRow]:
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    ps = _player_season_table()
    pspg = _player_season_pg_table()

    where_clauses: List[Any] = [ps.c.is_total.is_(True)]
    echo: Dict[str, Any] = {}

    if req.player_ids:
        where_clauses.append(ps.c.player_id.in_(req.player_ids))
        echo["player_ids"] = req.player_ids

    if req.from_season is not None:
        where_clauses.append(ps.c.season_end_year >= req.from_season)
        echo["from_season"] = req.from_season

    if req.to_season is not None:
        where_clauses.append(ps.c.season_end_year <= req.to_season)
        echo["to_season"] = req.to_season

    if req.is_playoffs is not None:
        where_clauses.append(ps.c.is_playoffs.is_(req.is_playoffs))
        echo["is_playoffs"] = req.is_playoffs

    query = (
        select(
            ps.c.seas_id,
            ps.c.player_id,
            ps.c.season_end_year,
            ps.c.team_id,
            pspg.c.g,
            pspg.c.pts_per_g,
        )
        .select_from(ps.join(pspg, pspg.c.seas_id == ps.c.seas_id, isouter=True))
        .where(and_(*where_clauses))
        .order_by(ps.c.season_end_year, ps.c.player_id, ps.c.seas_id)
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [
        PlayerSeasonFinderResponseRow(
            seas_id=row["seas_id"],
            player_id=row["player_id"],
            season_end_year=row["season_end_year"],
            team_id=row.get("team_id"),
            g=row.get("g"),
            pts_per_g=row.get("pts_per_g"),
        )
        for row in rows
    ]

    return PaginatedResponse[PlayerSeasonFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


@router.post(
    "/tools/player-game-finder",
    response_model=PaginatedResponse[PlayerGameFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def player_game_finder(
    req: PlayerGameFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[PlayerGameFinderResponseRow]:
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    bs = _boxscore_player_table()
    games = _games_table()

    where_clauses: List[Any] = []
    echo: Dict[str, Any] = {}

    if req.player_ids:
        where_clauses.append(bs.c.player_id.in_(req.player_ids))
        echo["player_ids"] = req.player_ids

    if req.from_season is not None:
        where_clauses.append(bs.c.season_end_year >= req.from_season)
        echo["from_season"] = req.from_season

    if req.to_season is not None:
        where_clauses.append(bs.c.season_end_year <= req.to_season)
        echo["to_season"] = req.to_season

    if req.is_playoffs is not None:
        # ensure alignment with games.is_playoffs via join
        where_clauses.append(games.c.is_playoffs.is_(req.is_playoffs))
        echo["is_playoffs"] = req.is_playoffs

    query = select(
        bs.c.game_id,
        bs.c.player_id,
        bs.c.season_end_year,
        bs.c.pts,
        bs.c.trb,
        bs.c.ast,
    ).select_from(bs.join(games, games.c.game_id == bs.c.game_id))

    if where_clauses:
        query = query.where(and_(*where_clauses))

    # Deterministic: newest games first, then game_id, player_id
    query = query.order_by(
        bs.c.season_end_year.desc().nullslast(),
        bs.c.game_id,
        bs.c.player_id,
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [
        PlayerGameFinderResponseRow(
            game_id=row["game_id"],
            player_id=row["player_id"],
            season_end_year=row.get("season_end_year"),
            pts=row.get("pts"),
            trb=row.get("trb"),
            ast=row.get("ast"),
        )
        for row in rows
    ]

    return PaginatedResponse[PlayerGameFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

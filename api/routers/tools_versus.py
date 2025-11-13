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
    VersusFinderRequest,
    VersusFinderResponseRow,
)

router = APIRouter(tags=["tools", "versus-finder"])


def _boxscore_player_table():
    return table(
        "boxscore_player",
        column("game_id"),
        column("player_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("pts"),
    )


def _boxscore_team_table():
    return table(
        "boxscore_team",
        column("game_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("pts"),
    )


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


@router.post(
    "/tools/versus-finder",
    response_model=PaginatedResponse[VersusFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def versus_finder(
    req: VersusFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[VersusFinderResponseRow]:
    """
    Aggregate subject vs opponent stats.

    Minimal implementation per specs:
    - subject is either a player or team (exactly one).
    - Aggregates:
        - games played (g)
        - points per game (pts_per_g)
    """
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    if bool(req.player_id) == bool(req.team_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of player_id or team_id is required",
        )

    echo: Dict[str, Any] = {}
    if req.player_id is not None:
        echo["player_id"] = req.player_id
    if req.team_id is not None:
        echo["team_id"] = req.team_id
    if req.opponent_ids is not None:
        echo["opponent_ids"] = req.opponent_ids

    games = _games_table()

    if req.player_id is not None:
        bs = _boxscore_player_table()

        where_clauses: List[Any] = [bs.c.player_id == req.player_id]
        if req.opponent_ids:
            where_clauses.append(bs.c.opponent_team_id.in_(req.opponent_ids))

        base = (
            select(
                bs.c.player_id.label("subject_id"),
                bs.c.opponent_team_id.label("opponent_id"),
                bs.c.pts,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(and_(*where_clauses))
        )
    else:
        bs = _boxscore_team_table()

        where_clauses = [bs.c.team_id == req.team_id]
        if req.opponent_ids:
            where_clauses.append(bs.c.opponent_team_id.in_(req.opponent_ids))

        base = (
            select(
                bs.c.team_id.label("subject_id"),
                bs.c.opponent_team_id.label("opponent_id"),
                bs.c.pts,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(and_(*where_clauses))
        )

    base_sq = base.subquery()

    agg = (
        select(
            base_sq.c.subject_id,
            base_sq.c.opponent_id,
            func.count().label("g"),
            func.avg(base_sq.c.pts).label("pts_per_g"),
        )
        .group_by(base_sq.c.subject_id, base_sq.c.opponent_id)
        .order_by(
            func.count().desc(),
            base_sq.c.opponent_id,
        )
    )

    count_stmt = select(func.count()).select_from(agg.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(agg.limit(page_size).offset(offset))).mappings()

    data: List[VersusFinderResponseRow] = []
    for row in rows:
        data.append(
            VersusFinderResponseRow(
                subject_id=row["subject_id"],
                opponent_id=row["opponent_id"],
                g=row["g"],
                pts_per_g=float(row["pts_per_g"])
                if row["pts_per_g"] is not None
                else None,
            )
        )

    return PaginatedResponse[VersusFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

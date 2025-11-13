from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    SplitsRequest,
    SplitsResponseRow,
)

router = APIRouter(tags=["tools", "splits"])


def _boxscore_player_table():
    return table(
        "boxscore_player",
        column("game_id"),
        column("player_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("pts"),
        column("is_home"),
    )


def _boxscore_team_table():
    return table(
        "boxscore_team",
        column("game_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("pts"),
        column("is_home"),
    )


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


@router.post(
    "/tools/splits",
    response_model=PaginatedResponse[SplitsResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def splits(
    req: SplitsRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SplitsResponseRow]:
    """
    Minimal splits implementation.

    - subject_type: 'player' or 'team'
    - split_type:
        - 'home_away': split by home vs away
        - 'versus_opponent': split by opponent_id
    - Aggregates:
        - g (games)
        - pts_per_g
    """
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    if req.subject_type not in {"player", "team"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported subject_type",
        )

    if req.split_type not in {"home_away", "versus_opponent"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported split_type",
        )

    echo: Dict[str, Any] = {
        "subject_type": req.subject_type,
        "subject_id": req.subject_id,
        "split_type": req.split_type,
    }

    games = _games_table()

    if req.subject_type == "player":
        bs = _boxscore_player_table()
        where_clause = bs.c.player_id == req.subject_id
        subject_col = bs.c.player_id
        home_flag = bs.c.is_home
        opp_col = bs.c.opponent_team_id
    else:
        bs = _boxscore_team_table()
        where_clause = bs.c.team_id == req.subject_id
        subject_col = bs.c.team_id
        home_flag = bs.c.is_home
        opp_col = bs.c.opponent_team_id

    where_clauses: List[Any] = [where_clause]

    # Base join with games in case filters are extended later; currently unused but
    # keeps pattern consistent.
    base = (
        select(
            subject_col.label("subject_id"),
            bs.c.game_id,
            bs.c.pts,
            home_flag,
            opp_col,
        )
        .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
        .where(and_(*where_clauses))
    )

    base_sq = base.subquery()

    if req.split_type == "home_away":
        split_key_expr = case(
            (base_sq.c.is_home.is_(True), "home"),
            (base_sq.c.is_home.is_(False), "away"),
            else_="unknown",
        ).label("split_key")
    else:  # versus_opponent
        split_key_expr = func.coalesce(
            func.cast(base_sq.c.opponent_team_id, func.String()),
            "unknown",
        ).label("split_key")

    grouped = (
        select(
            base_sq.c.subject_id,
            split_key_expr,
            func.count().label("g"),
            func.avg(base_sq.c.pts).label("pts_per_g"),
        )
        .group_by(base_sq.c.subject_id, split_key_expr)
        .order_by(
            func.count().desc(),
            split_key_expr,
        )
    )

    count_stmt = select(func.count()).select_from(grouped.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(grouped.limit(page_size).offset(offset))).mappings()

    data: List[SplitsResponseRow] = []
    for row in rows:
        data.append(
            SplitsResponseRow(
                subject_id=row["subject_id"],
                split_key=str(row["split_key"]),
                g=row["g"],
                pts_per_g=float(row["pts_per_g"])
                if row["pts_per_g"] is not None
                else None,
            )
        )

    return PaginatedResponse[SplitsResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

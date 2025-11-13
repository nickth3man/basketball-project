from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    StreakFinderRequest,
    StreakFinderResponseRow,
)

router = APIRouter(tags=["tools", "streak-finder"])


def _boxscore_player_table():
    return table(
        "boxscore_player",
        column("game_id"),
        column("player_id"),
        column("pts"),
    )


def _boxscore_team_table():
    return table(
        "boxscore_team",
        column("game_id"),
        column("team_id"),
        column("pts"),
        column("opponent_team_id"),
        column("opponent_pts"),
    )


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("game_date_est"),
    )


@router.post(
    "/tools/streak-finder",
    response_model=PaginatedResponse[StreakFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def streak_finder(
    req: StreakFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[StreakFinderResponseRow]:
    """
    Canonical simple streak finder.

    Implements a single metric per Architect's minimal spec:
    - If player_id provided: consecutive games with pts >= 20.
    - If team_id provided: consecutive wins.
    Exactly one of player_id or team_id must be set.
    """
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    if bool(req.player_id) == bool(req.team_id):
        # Either none or both set -> invalid
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of player_id or team_id is required",
        )

    if req.player_id:
        # Player scoring streak: pts >= 20
        bs = _boxscore_player_table()
        games = _games_table()

        metric_label = "pts_ge_20"
        metric_expr = case((bs.c.pts >= 20, 1), else_=0).label("metric_hit")

        base = (
            select(
                bs.c.player_id.label("subject_id"),
                bs.c.game_id,
                games.c.game_date_est,
                metric_expr,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(bs.c.player_id == req.player_id)
        )

        # Order games deterministically by date then game_id
        base = base.order_by(games.c.game_date_est, bs.c.game_id)
    else:
        # Team win streaks
        bs = _boxscore_team_table()
        games = _games_table()

        metric_label = "wins"
        win_expr = case(
            (bs.c.pts > bs.c.opponent_pts, 1),
            else_=0,
        ).label("metric_hit")

        base = (
            select(
                bs.c.team_id.label("subject_id"),
                bs.c.game_id,
                games.c.game_date_est,
                win_expr,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(bs.c.team_id == req.team_id)
        )

        base = base.order_by(games.c.game_date_est, bs.c.game_id)

    # Use window functions to segment consecutive metric_hit = 1 runs.
    # streak_group increments when a non-hit (0) appears.
    streak_group = (
        func.sum(case((base.c.metric_hit == 0, 1), else_=0))
        .over(order_by=(base.c.game_date_est, base.c.game_id))
        .label("streak_group")
    )

    streaked = (
        select(
            base.c.subject_id,
            base.c.game_id,
            base.c.game_date_est,
            base.c.metric_hit,
            streak_group,
        )
        .select_from(base.subquery())
        .subquery()
    )

    # Aggregate only groups where metric_hit == 1 (streak games)
    agg = (
        select(
            streaked.c.subject_id,
            func.min(streaked.c.game_id).label("start_game_id"),
            func.max(streaked.c.game_id).label("end_game_id"),
            func.count().label("length"),
        )
        .where(streaked.c.metric_hit == 1)
        .group_by(streaked.c.subject_id, streaked.c.streak_group)
    )

    # Apply minimum length
    agg = agg.having(func.count() >= req.min_length)

    # Deterministic ordering: longest first, then start_game_id
    agg = agg.order_by(
        func.count().desc(),
        func.min(streaked.c.game_id),
    )

    count_stmt = select(func.count()).select_from(agg.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(agg.limit(page_size).offset(offset))).mappings()

    echo: Dict[str, Any] = {
        "min_length": req.min_length,
    }
    if req.player_id:
        echo["player_id"] = req.player_id
    if req.team_id:
        echo["team_id"] = req.team_id

    data: List[StreakFinderResponseRow] = []
    for row in rows:
        data.append(
            StreakFinderResponseRow(
                subject_id=row["subject_id"],
                start_game_id=row["start_game_id"],
                end_game_id=row["end_game_id"],
                length=row["length"],
                stat=metric_label,
                value=float(row["length"]),
            )
        )

    return PaginatedResponse[StreakFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

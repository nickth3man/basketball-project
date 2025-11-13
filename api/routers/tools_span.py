from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    SpanFinderRequest,
    SpanFinderResponseRow,
)

router = APIRouter(tags=["tools", "span-finder"])


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
    )


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("game_date_est"),
        column("season_end_year"),
    )


@router.post(
    "/tools/span-finder",
    response_model=PaginatedResponse[SpanFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def span_finder(
    req: SpanFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[SpanFinderResponseRow]:
    """
    Canonical rolling span finder using SQL window functions.

    Minimal implementation:
    - Requires exactly one of player_id or team_id.
    - Uses fixed stat: sum of pts over a rolling window of length span_length.
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

    if req.span_length < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="span_length must be >= 1",
        )

    games = _games_table()
    echo: Dict[str, Any] = {
        "span_length": req.span_length,
    }

    if req.player_id:
        bs = _boxscore_player_table()
        echo["player_id"] = req.player_id

        base = (
            select(
                bs.c.player_id.label("subject_id"),
                bs.c.game_id,
                games.c.game_date_est,
                bs.c.pts,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(bs.c.player_id == req.player_id)
            .order_by(games.c.game_date_est, bs.c.game_id)
        )
    else:
        bs = _boxscore_team_table()
        echo["team_id"] = req.team_id

        base = (
            select(
                bs.c.team_id.label("subject_id"),
                bs.c.game_id,
                games.c.game_date_est,
                bs.c.pts,
            )
            .select_from(bs.join(games, games.c.game_id == bs.c.game_id))
            .where(bs.c.team_id == req.team_id)
            .order_by(games.c.game_date_est, bs.c.game_id)
        )

    base_sq = base.subquery()

    # Rolling window over ordered games for the subject.
    window_sum = (
        func.sum(base_sq.c.pts)
        .over(
            partition_by=base_sq.c.subject_id,
            order_by=(base_sq.c.game_date_est, base_sq.c.game_id),
            rows=(req.span_length - 1) * -1,
        )
        .label("span_pts")
    )

    row_number = (
        func.row_number()
        .over(
            partition_by=base_sq.c.subject_id,
            order_by=(base_sq.c.game_date_est, base_sq.c.game_id),
        )
        .label("rn")
    )

    spans_sq = (
        select(
            base_sq.c.subject_id,
            base_sq.c.game_id.label("end_game_id"),
            base_sq.c.game_date_est,
            window_sum,
            row_number,
        )
        .select_from(base_sq)
        .subquery()
    )

    # Only keep rows where we have a full window (rn >= span_length)
    spans = select(
        spans_sq.c.subject_id,
        func.lag(spans_sq.c.game_id, req.span_length - 1)
        .over(
            partition_by=spans_sq.c.subject_id,
            order_by=(spans_sq.c.game_date_est, spans_sq.c.game_id),
        )
        .label("start_game_id"),
        spans_sq.c.end_game_id,
        func.cast(func.literal(req.span_length), func.Integer()).label(
            "span_length",
        ),
        func.literal("pts").label("stat"),
        spans_sq.c.span_pts.label("value"),
    ).where(spans_sq.c.rn >= req.span_length)

    # Deterministic ordering: highest value first, then subject_id, start/end id
    spans = spans.order_by(
        spans.c.value.desc(),
        spans.c.subject_id,
        spans.c.start_game_id,
        spans.c.end_game_id,
    )

    count_stmt = select(func.count()).select_from(spans.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(spans.limit(page_size).offset(offset))).mappings()

    data: List[SpanFinderResponseRow] = []
    for row in rows:
        data.append(
            SpanFinderResponseRow(
                subject_id=row["subject_id"],
                start_game_id=row["start_game_id"],
                end_game_id=row["end_game_id"],
                span_length=row["span_length"],
                stat=str(row["stat"]),
                value=float(row["value"]),
            )
        )

    return PaginatedResponse[SpanFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

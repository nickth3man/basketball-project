from __future__ import annotations

from typing import Dict, List, Tuple

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, select, table, column
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_pagination, parse_comma_ints
from api.models import (
    FiltersEcho,
    PbpEventRow,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(tags=["pbp"])


def _pbp_events_table():
    return table(
        "pbp_events",
        column("game_id"),
        column("eventnum"),
        column("period"),
        column("clk"),
        column("clk_remaining"),
        column("event_type"),
        column("team_id"),
        column("opponent_team_id"),
        column("player1_id"),
        column("player2_id"),
        column("player3_id"),
        column("description"),
        column("home_score"),
        column("away_score"),
    )


@router.get(
    "/games/{game_id}/pbp",
    response_model=PaginatedResponse,
)
async def get_game_pbp(
    game_id: str,
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
    period: int | None = Query(
        None,
        description="Filter by period number.",
    ),
    event_type: str | None = Query(
        None,
        description="Filter by event_type.",
    ),
    team_id: int | None = Query(
        None,
        description="Filter by team_id on event.",
    ),
    player_id: int | None = Query(
        None,
        description="Filter if player appears as player1_id.",
    ),
) -> PaginatedResponse:
    page, page_size = page_data
    echo: Dict[str, object] = {"game_id": game_id}

    pbp = _pbp_events_table()

    query = select(
        pbp.c.game_id,
        pbp.c.eventnum,
        pbp.c.period,
        pbp.c.clk,
        pbp.c.event_type,
        pbp.c.team_id,
        pbp.c.player1_id,
        pbp.c.description,
        pbp.c.home_score,
        pbp.c.away_score,
    ).where(pbp.c.game_id == game_id)

    where_clauses = []

    if period is not None:
        echo["period"] = period
        where_clauses.append(pbp.c.period == period)

    if event_type:
        echo["event_type"] = event_type
        where_clauses.append(pbp.c.event_type == event_type)

    if team_id is not None:
        echo["team_id"] = team_id
        where_clauses.append(pbp.c.team_id == team_id)

    if player_id is not None:
        echo["player_id"] = player_id
        where_clauses.append(pbp.c.player1_id == player_id)

    if where_clauses:
        query = query.where(and_(*where_clauses))

    query = query.order_by(pbp.c.eventnum)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(query.limit(page_size).offset(offset))
    ).mappings()

    data: List[PbpEventRow] = [PbpEventRow(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )
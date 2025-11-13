from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    EventFinderRequest,
    EventFinderResponseRow,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(tags=["tools", "event-finder"])


def _pbp_events_table():
    return table(
        "pbp_events",
        column("game_id"),
        column("eventnum"),
        column("period"),
        column("clk"),
        column("event_type"),
        column("team_id"),
        column("player1_id"),
        column("description"),
    )


@router.post(
    "/tools/event-finder",
    response_model=PaginatedResponse[EventFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def event_finder(
    req: EventFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[EventFinderResponseRow]:
    """
    Query pbp_events using simple equality/IN filters.

    Canonical behavior:
    - Supports filtering by game_ids, event_types, player_ids, team_ids.
    - No fuzzy search; all filters are exact or IN matches.
    - Stable ordering by (game_id, eventnum) for deterministic pagination.
    """
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    pbp = _pbp_events_table()

    where_clauses: List[Any] = []
    echo: Dict[str, Any] = {}

    if req.game_ids:
        where_clauses.append(pbp.c.game_id.in_(req.game_ids))
        echo["game_ids"] = req.game_ids

    if req.event_types:
        where_clauses.append(pbp.c.event_type.in_(req.event_types))
        echo["event_types"] = req.event_types

    if req.player_ids:
        where_clauses.append(pbp.c.player1_id.in_(req.player_ids))
        echo["player_ids"] = req.player_ids

    if req.team_ids:
        where_clauses.append(pbp.c.team_id.in_(req.team_ids))
        echo["team_ids"] = req.team_ids

    query = select(
        pbp.c.game_id,
        pbp.c.eventnum,
        pbp.c.event_type,
        pbp.c.period,
        pbp.c.clk,
        pbp.c.team_id,
        pbp.c.player1_id,
        pbp.c.description,
    ).select_from(pbp)

    if where_clauses:
        query = query.where(and_(*where_clauses))

    query = query.order_by(pbp.c.game_id, pbp.c.eventnum)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data: List[EventFinderResponseRow] = [
        EventFinderResponseRow(
            game_id=row["game_id"],
            eventnum=row["eventnum"],
            event_type=row.get("event_type"),
            period=row.get("period"),
            clk=row.get("clk"),
            team_id=row.get("team_id"),
            player1_id=row.get("player1_id"),
            description=row.get("description"),
        )
        for row in rows
    ]

    return PaginatedResponse[EventFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


# Backwards-compatible alias so api.main can import `tools_pbp_search.router`
tools_pbp_search = router

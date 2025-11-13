from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select, table, column
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_pagination, parse_comma_ints
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    Team,
    TeamSeasonSummary,
)

router = APIRouter(tags=["teams"])


def _teams_table():
    return table(
        "teams",
        column("team_id"),
        column("team_abbrev"),
        column("team_name"),
        column("team_city"),
        column("start_season"),
        column("end_season"),
        column("is_active"),
    )


def _team_history_table():
    return table(
        "team_history",
        column("team_history_id"),
        column("team_id"),
        column("season_end_year"),
        column("team_abbrev"),
        column("team_name"),
        column("team_city"),
    )


def _team_season_table():
    return table(
        "team_season",
        column("team_season_id"),
        column("team_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


def _team_season_totals_table():
    return table(
        "team_season_totals",
        column("team_season_id"),
        column("g"),
        column("pts"),
    )


def _team_season_opp_totals_table():
    return table(
        "team_season_opponent_totals",
        column("team_season_id"),
        column("opp_pts"),
    )


@router.get("/teams", response_model=PaginatedResponse)
async def list_teams(
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
    team_ids: str | None = Query(
        None,
        description="Comma-separated list of team_id values.",
    ),
    q: str | None = Query(
        None,
        description="Free-text search over team name/city/abbrev.",
    ),
    is_active: bool | None = Query(
        None,
        description="Filter by active franchises.",
    ),
) -> PaginatedResponse:
    page, page_size = page_data

    echo: Dict[str, Any] = {}
    filters: List[Any] = []

    ids = parse_comma_ints(team_ids)
    if ids:
        echo["team_ids"] = ids
        filters.append(("team_id", "in", ids))

    if q:
        echo["q"] = q

    if is_active is not None:
        echo["is_active"] = is_active

    teams = _teams_table()
    query = select(
        teams.c.team_id,
        teams.c.team_abbrev,
        teams.c.team_name,
        teams.c.team_city,
        teams.c.start_season,
        teams.c.end_season,
        teams.c.is_active,
    )

    where_clauses = []
    for key, op, value in filters:
        col = getattr(teams.c, key)
        if op == "in":
            where_clauses.append(col.in_(value))

    if is_active is not None:
        where_clauses.append(teams.c.is_active.is_(is_active))

    if q:
        pattern = f"%{q.lower()}%"
        where_clauses.append(
            func.lower(teams.c.team_name).like(pattern)
            | func.lower(teams.c.team_city).like(pattern)
            | func.lower(teams.c.team_abbrev).like(pattern)
        )

    if where_clauses:
        query = query.where(and_(*where_clauses))

    query = query.order_by(teams.c.team_name, teams.c.team_id)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(query.limit(page_size).offset(offset))
    ).mappings()

    data = [Team(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


@router.get(
    "/teams/{team_id}",
    response_model=Team,
    responses={404: {"model": ErrorResponse}},
)
async def get_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
) -> Team:
    teams = _teams_table()

    stmt = (
        select(
            teams.c.team_id,
            teams.c.team_abbrev,
            teams.c.team_name,
            teams.c.team_city,
            teams.c.start_season,
            teams.c.end_season,
            teams.c.is_active,
        )
        .where(teams.c.team_id == team_id)
        .limit(1)
    )

    row = (await db.execute(stmt)).mappings().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Team not found",
        )

    return Team(**dict(row))


@router.get(
    "/teams/{team_id}/seasons",
    response_model=PaginatedResponse,
)
async def get_team_seasons(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
) -> PaginatedResponse:
    page, page_size = page_data

    ts = _team_season_table()
    tst = _team_season_totals_table()
    topt = _team_season_opp_totals_table()

    base = (
        select(
            ts.c.team_season_id,
            ts.c.team_id,
            ts.c.season_end_year,
            ts.c.is_playoffs,
            tst.c.g,
            tst.c.pts,
            topt.c.opp_pts,
        )
        .join(tst, tst.c.team_season_id == ts.c.team_season_id, isouter=True)
        .join(
            topt,
            topt.c.team_season_id == ts.c.team_season_id,
            isouter=True,
        )
        .where(ts.c.team_id == team_id)
        .order_by(ts.c.season_end_year, ts.c.team_season_id)
    )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(base.limit(page_size).offset(offset))
    ).mappings()

    data = [TeamSeasonSummary(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw={"team_id": team_id}),
    )
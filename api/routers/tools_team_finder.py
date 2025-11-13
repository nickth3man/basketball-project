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
    TeamGameFinderRequest,
    TeamGameFinderResponseRow,
    TeamSeasonFinderRequest,
    TeamSeasonFinderResponseRow,
)

router = APIRouter(tags=["tools", "team-finder"])


def _teams_table():
    return table(
        "teams",
        column("team_id"),
        column("abbrev"),
        column("name"),
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


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


def _boxscore_team_table():
    return table(
        "boxscore_team",
        column("game_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("is_home"),
        column("pts"),
    )


@router.post(
    "/tools/team-season-finder",
    response_model=PaginatedResponse[TeamSeasonFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def team_season_finder(
    req: TeamSeasonFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TeamSeasonFinderResponseRow]:
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    ts = _team_season_table()
    tst = _team_season_totals_table()

    where_clauses: List[Any] = []
    echo: Dict[str, Any] = {}

    if req.team_ids:
        where_clauses.append(ts.c.team_id.in_(req.team_ids))
        echo["team_ids"] = req.team_ids

    if req.from_season is not None:
        where_clauses.append(ts.c.season_end_year >= req.from_season)
        echo["from_season"] = req.from_season

    if req.to_season is not None:
        where_clauses.append(ts.c.season_end_year <= req.to_season)
        echo["to_season"] = req.to_season

    if req.is_playoffs is not None:
        where_clauses.append(ts.c.is_playoffs.is_(req.is_playoffs))
        echo["is_playoffs"] = req.is_playoffs

    query = select(
        ts.c.team_season_id,
        ts.c.team_id,
        ts.c.season_end_year,
        tst.c.g,
        tst.c.pts,
    ).select_from(ts.join(tst, tst.c.team_season_id == ts.c.team_season_id))

    if where_clauses:
        query = query.where(and_(*where_clauses))

    # Deterministic ordering: by season, team, team_season_id
    query = query.order_by(
        ts.c.season_end_year,
        ts.c.team_id,
        ts.c.team_season_id,
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [
        TeamSeasonFinderResponseRow(
            team_season_id=row["team_season_id"],
            team_id=row["team_id"],
            season_end_year=row["season_end_year"],
            g=row.get("g"),
            pts=row.get("pts"),
        )
        for row in rows
    ]

    return PaginatedResponse[TeamSeasonFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


@router.post(
    "/tools/team-game-finder",
    response_model=PaginatedResponse[TeamGameFinderResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def team_game_finder(
    req: TeamGameFinderRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TeamGameFinderResponseRow]:
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    bs = _boxscore_team_table()
    games = _games_table()

    where_clauses: List[Any] = []
    echo: Dict[str, Any] = {}

    if req.team_ids:
        where_clauses.append(bs.c.team_id.in_(req.team_ids))
        echo["team_ids"] = req.team_ids

    if req.from_season is not None:
        where_clauses.append(games.c.season_end_year >= req.from_season)
        echo["from_season"] = req.from_season

    if req.to_season is not None:
        where_clauses.append(games.c.season_end_year <= req.to_season)
        echo["to_season"] = req.to_season

    if req.is_playoffs is not None:
        where_clauses.append(games.c.is_playoffs.is_(req.is_playoffs))
        echo["is_playoffs"] = req.is_playoffs

    query = select(
        bs.c.game_id,
        bs.c.team_id,
        bs.c.is_home,
        bs.c.pts,
        (bs.c.pts - bs.c.opponent_team_id).label(
            "opp_pts_dummy"
        ),  # placeholder not used in response
    ).select_from(bs.join(games, games.c.game_id == bs.c.game_id))

    if where_clauses:
        query = query.where(and_(*where_clauses))

    # True opp_pts using window-less expression from joined rows via self-join:
    # To preserve a single-pass, re-build query computing opp_pts using aggregation.
    # We keep deterministic ordering by season_end_year, game_id, team_id.
    bs_alias = _boxscore_team_table()
    opp_pts_case = func.max(
        case(
            (bs_alias.c.team_id == bs.c.opponent_team_id, bs_alias.c.pts),
            else_=None,
        )
    )

    query = select(
        bs.c.game_id,
        bs.c.team_id,
        bs.c.is_home,
        bs.c.pts,
        opp_pts_case.label("opp_pts"),
        games.c.season_end_year,
    ).select_from(
        bs.join(games, games.c.game_id == bs.c.game_id).join(
            bs_alias,
            bs_alias.c.game_id == bs.c.game_id,
            isouter=True,
        )
    )

    if where_clauses:
        query = query.where(and_(*where_clauses))

    query = query.group_by(
        bs.c.game_id,
        bs.c.team_id,
        bs.c.is_home,
        bs.c.pts,
        games.c.season_end_year,
    ).order_by(
        games.c.season_end_year.desc().nullslast(),
        bs.c.game_id,
        bs.c.team_id,
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (await db.execute(query.limit(page_size).offset(offset))).mappings()

    data = [
        TeamGameFinderResponseRow(
            game_id=row["game_id"],
            team_id=row["team_id"],
            is_home=bool(row["is_home"]) if row["is_home"] is not None else None,
            pts=row.get("pts"),
            opp_pts=row.get("opp_pts"),
        )
        for row in rows
    ]

    return PaginatedResponse[TeamGameFinderResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

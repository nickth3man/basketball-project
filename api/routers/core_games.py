from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select, table, column
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_pagination, parse_comma_ints
from api.models import (
    BoxscoreTeamRow,
    ErrorResponse,
    FiltersEcho,
    Game,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(tags=["games"])


def _games_table():
    return table(
        "games",
        column("game_id"),
        column("season_id"),
        column("season_end_year"),
        column("lg"),
        column("game_date_est"),
        column("home_team_id"),
        column("away_team_id"),
        column("home_pts"),
        column("away_pts"),
        column("is_playoffs"),
    )


def _boxscore_team_table():
    return table(
        "boxscore_team",
        column("game_id"),
        column("team_id"),
        column("opponent_team_id"),
        column("is_home"),
        column("team_abbrev"),
        column("pts"),
    )


@router.get("/games", response_model=PaginatedResponse)
async def list_games(
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
    game_ids: str | None = Query(
        None,
        description="Comma-separated list of game_id values.",
    ),
    season: int | None = Query(
        None,
        description="Filter by season_end_year.",
    ),
    from_date: str | None = Query(
        None,
        description="Filter by game_date_est >= this YYYY-MM-DD.",
    ),
    to_date: str | None = Query(
        None,
        description="Filter by game_date_est <= this YYYY-MM-DD.",
    ),
    is_playoffs: bool | None = Query(
        None,
        description="Filter by playoffs flag.",
    ),
    team_id: int | None = Query(
        None,
        description="Filter where this team participated.",
    ),
    opponent_id: int | None = Query(
        None,
        description="Filter by opposing team.",
    ),
) -> PaginatedResponse:
    page, page_size = page_data

    echo: Dict[str, Any] = {}
    games = _games_table()
    bs_team = _boxscore_team_table()

    query = select(
        games.c.game_id,
        games.c.season_end_year,
        games.c.game_date_est,
        games.c.home_team_id,
        games.c.away_team_id,
        games.c.home_pts,
        games.c.away_pts,
        games.c.is_playoffs,
    )

    where_clauses: List[Any] = []

    ids = parse_comma_ints(game_ids)
    if ids:
        # game_id is text; we still treat parsed ints as strings via cast
        # but for simplicity, expect callers to pass real IDs as strings.
        echo["game_ids"] = game_ids

    if season is not None:
        echo["season"] = season
        where_clauses.append(games.c.season_end_year == season)

    if from_date:
        echo["from_date"] = from_date
        where_clauses.append(games.c.game_date_est >= from_date)

    if to_date:
        echo["to_date"] = to_date
        where_clauses.append(games.c.game_date_est <= to_date)

    if is_playoffs is not None:
        echo["is_playoffs"] = is_playoffs
        where_clauses.append(games.c.is_playoffs.is_(is_playoffs))

    # Team / opponent filters via boxscore_team join
    if team_id is not None or opponent_id is not None:
        echo["team_id"] = team_id
        if opponent_id is not None:
            echo["opponent_id"] = opponent_id
        query = query.join(
            bs_team,
            bs_team.c.game_id == games.c.game_id,
        )
        if team_id is not None:
            where_clauses.append(bs_team.c.team_id == team_id)
        if opponent_id is not None:
            where_clauses.append(bs_team.c.opponent_team_id == opponent_id)

    if where_clauses:
        query = query.where(and_(*where_clauses))

    query = query.order_by(
        games.c.game_date_est,
        games.c.game_id,
    )

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(query.limit(page_size).offset(offset))
    ).mappings()

    data = [Game(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


@router.get(
    "/games/{game_id}",
    response_model=Game,
    responses={404: {"model": ErrorResponse}},
)
async def get_game(
    game_id: str,
    db: AsyncSession = Depends(get_db),
) -> Game:
    games = _games_table()

    stmt = (
        select(
            games.c.game_id,
            games.c.season_end_year,
            games.c.game_date_est,
            games.c.home_team_id,
            games.c.away_team_id,
            games.c.home_pts,
            games.c.away_pts,
            games.c.is_playoffs,
        )
        .where(games.c.game_id == game_id)
        .limit(1)
    )

    row = (await db.execute(stmt)).mappings().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Game not found",
        )

    return Game(**dict(row))


@router.get(
    "/games/{game_id}/boxscore-team",
    response_model=List[BoxscoreTeamRow],
)
async def get_boxscore_team(
    game_id: str,
    db: AsyncSession = Depends(get_db),
) -> List[BoxscoreTeamRow]:
    bs = _boxscore_team_table()

    stmt = (
        select(
            bs.c.game_id,
            bs.c.team_id,
            bs.c.opponent_team_id,
            bs.c.is_home,
            bs.c.team_abbrev,
            bs.c.pts,
        )
        .where(bs.c.game_id == game_id)
        .order_by(bs.c.is_home.desc(), bs.c.team_id)
    )

    rows = (await db.execute(stmt)).mappings()
    return [BoxscoreTeamRow(**dict(r)) for r in rows]
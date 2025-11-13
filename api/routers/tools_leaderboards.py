from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    Table,
    and_,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import (
    games_table,
    get_db,
    metadata,
    player_season_table,
    players_table,
    teams_table,
)
from api.models import (
    ErrorResponse,
    FiltersEcho,
    LeaderboardsRequest,
    LeaderboardsResponseRow,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(tags=["tools", "leaderboards"])

# [BUG][RELIABILITY][P1] Table definitions mix Column() (correct)
# and column() (incorrect).
# column() is for query expressions, not table definitions.
# Causes runtime errors.

player_season_totals_table = Table(
    "player_season_totals",
    metadata,
    Column("seas_id", Integer),
    Column("pts", Integer),
)

# Define additional tables not in api.db
team_season_table = Table(
    "team_season",
    metadata,
    Column("team_season_id", Integer),
    Column("team_id", Integer),
    Column("season_end_year", Integer),
    Column("is_playoffs", Boolean),
)

team_season_totals_table = Table(
    "team_season_totals",
    metadata,
    Column("team_season_id", Integer),
    Column("pts", Integer),
)

boxscore_player_table = Table(
    "boxscore_player",
    metadata,
    Column("game_id", String(20)),
    Column("player_id", Integer),
    Column("pts", Integer),
)


# Whitelist mapping: (scope, stat) -> (label, selectable expression factory)
# Only minimal canonical combinations implemented.
def _get_scope_stat(spec: LeaderboardsRequest):
    scope = spec.scope
    stat = spec.stat

    if scope == "player_season" and stat == "pts":

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                player_season_table.c.player_id.label("subject_id"),
                players_table.c.full_name.label("label"),
                player_season_totals_table.c.pts.label("stat"),
                player_season_table.c.season_end_year,
            ).select_from(
                player_season_table.join(
                    player_season_totals_table,
                    player_season_totals_table.c.seas_id
                    == player_season_table.c.seas_id,
                ).join(
                    players_table,
                    players_table.c.player_id == player_season_table.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            # One row per (player, season) already; order by stat desc
            base = base.order_by(
                player_season_totals_table.c.pts.desc().nullslast(),
                player_season_table.c.player_id,
                player_season_table.c.season_end_year,
            )
            return base, player_season_table.c.season_end_year

        return build_query

    if scope == "player_career" and stat == "pts":

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                player_season_table.c.player_id.label("subject_id"),
                players_table.c.full_name.label("label"),
                func.sum(player_season_totals_table.c.pts).label("stat"),
            ).select_from(
                player_season_table.join(
                    player_season_totals_table,
                    player_season_totals_table.c.seas_id
                    == player_season_table.c.seas_id,
                ).join(
                    players_table,
                    players_table.c.player_id == player_season_table.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.group_by(
                player_season_table.c.player_id, players_table.c.full_name
            ).order_by(
                func.sum(player_season_totals_table.c.pts).desc().nullslast(),
                player_season_table.c.player_id,
            )
            return base, None

        return build_query

    if scope == "team_season" and stat == "pts":

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                team_season_table.c.team_id.label("subject_id"),
                teams_table.c.abbrev.label("label"),
                team_season_totals_table.c.pts.label("stat"),
                team_season_table.c.season_end_year,
            ).select_from(
                team_season_table.join(
                    team_season_totals_table,
                    team_season_totals_table.c.team_season_id
                    == team_season_table.c.team_season_id,
                ).join(
                    teams_table,
                    teams_table.c.team_id == team_season_table.c.team_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.order_by(
                team_season_totals_table.c.pts.desc().nullslast(),
                team_season_table.c.team_id,
                team_season_table.c.season_end_year,
            )
            return base, team_season_table.c.season_end_year

        return build_query

    if scope == "single_game" and stat == "pts":

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                boxscore_player_table.c.player_id.label("subject_id"),
                players_table.c.full_name.label("label"),
                boxscore_player_table.c.pts.label("stat"),
                games_table.c.season_end_year,
                boxscore_player_table.c.game_id,
            ).select_from(
                boxscore_player_table.join(
                    games_table,
                    games_table.c.game_id == boxscore_player_table.c.game_id,
                ).join(
                    players_table,
                    players_table.c.player_id == boxscore_player_table.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.order_by(
                boxscore_player_table.c.pts.desc().nullslast(),
                boxscore_player_table.c.player_id,
                boxscore_player_table.c.game_id,
            )
            return base, games_table.c.season_end_year

        return build_query

    # Unsupported combination
    return None


@router.post(
    "/tools/leaderboards",
    response_model=PaginatedResponse[LeaderboardsResponseRow],
    responses={400: {"model": ErrorResponse}},
)
async def leaderboards(
    req: LeaderboardsRequest,
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[LeaderboardsResponseRow]:
    """
    Minimal leaderboard implementation.

    Supported (scope, stat) combinations:
    - (player_season, pts)
    - (player_career, pts)
    - (team_season, pts)
    - (single_game, pts)

    Unsupported combinations return 400 with ErrorResponse.
    """
    page = req.page
    page_size = req.page_size

    if page < 1 or page_size < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="page and page_size must be positive",
        )

    build_query = _get_scope_stat(req)
    if build_query is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported scope/stat combination",
        )

    echo: Dict[str, Any] = {
        "scope": req.scope,
        "stat": req.stat,
    }

    # Apply filters based on request parameters
    filters: List[Any] = []

    if req.season_end_year is not None:
        echo["season_end_year"] = req.season_end_year
        filters.append(player_season_table.c.season_end_year == req.season_end_year)

    if req.is_playoffs is not None:
        echo["is_playoffs"] = req.is_playoffs
        filters.append(player_season_table.c.is_playoffs == req.is_playoffs)

    # Build base query and get season column
    base, season_col = build_query(filters)

    # Get total count
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Add pagination and execute
    offset = (page - 1) * page_size
    rows = (await db.execute(base.limit(page_size).offset(offset))).mappings()

    data: List[LeaderboardsResponseRow] = []
    for row in rows:
        data.append(
            LeaderboardsResponseRow(
                subject_id=row["subject_id"],
                label=row["label"],
                stat=float(row["stat"]) if row["stat"] is not None else 0.0,
                season_end_year=(
                    int(row["season_end_year"])
                    if season_col and row[season_col] is not None
                    else None
                ),
                game_id=row["game_id"] if "game_id" in row else None,
            )
        )

    return PaginatedResponse[LeaderboardsResponseRow](
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )

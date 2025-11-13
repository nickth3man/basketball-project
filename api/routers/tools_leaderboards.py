from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, case, column, func, select, table
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.models import (
    ErrorResponse,
    FiltersEcho,
    LeaderboardsRequest,
    LeaderboardsResponseRow,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter(tags=["tools", "leaderboards"])


def _player_season_table():
    return table(
        "player_season",
        column("seas_id"),
        column("player_id"),
        column("season_end_year"),
        column("is_playoffs"),
    )


def _player_season_totals_table():
    return table(
        "player_season_totals",
        column("seas_id"),
        column("pts"),
    )


def _players_table():
    return table(
        "players",
        column("player_id"),
        column("full_name"),
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
        column("pts"),
    )


def _teams_table():
    return table(
        "teams",
        column("team_id"),
        column("abbrev"),
    )


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
        column("season_end_year"),
        column("is_playoffs"),
    )


# Whitelist mapping: (scope, stat) -> (label, selectable expression factory)
# Only minimal canonical combinations implemented.
def _get_scope_stat(spec: LeaderboardsRequest):
    scope = spec.scope
    stat = spec.stat

    if scope == "player_season" and stat == "pts":
        ps = _player_season_table()
        pst = _player_season_totals_table()
        players = _players_table()

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                ps.c.player_id.label("subject_id"),
                players.c.full_name.label("label"),
                pst.c.pts.label("stat"),
                ps.c.season_end_year,
            ).select_from(
                ps.join(pst, pst.c.seas_id == ps.c.seas_id).join(
                    players,
                    players.c.player_id == ps.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            # One row per (player, season) already; order by stat desc
            base = base.order_by(
                pst.c.pts.desc().nullslast(),
                ps.c.player_id,
                ps.c.season_end_year,
            )
            return base, ps.c.season_end_year

        return build_query

    if scope == "player_career" and stat == "pts":
        ps = _player_season_table()
        pst = _player_season_totals_table()
        players = _players_table()

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                ps.c.player_id.label("subject_id"),
                players.c.full_name.label("label"),
                func.sum(pst.c.pts).label("stat"),
            ).select_from(
                ps.join(pst, pst.c.seas_id == ps.c.seas_id).join(
                    players,
                    players.c.player_id == ps.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.group_by(ps.c.player_id, players.c.full_name).order_by(
                func.sum(pst.c.pts).desc().nullslast(),
                ps.c.player_id,
            )
            return base, None

        return build_query

    if scope == "team_season" and stat == "pts":
        ts = _team_season_table()
        tst = _team_season_totals_table()
        teams = _teams_table()

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                ts.c.team_id.label("subject_id"),
                teams.c.abbrev.label("label"),
                tst.c.pts.label("stat"),
                ts.c.season_end_year,
            ).select_from(
                ts.join(tst, tst.c.team_season_id == ts.c.team_season_id).join(
                    teams,
                    teams.c.team_id == ts.c.team_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.order_by(
                tst.c.pts.desc().nullslast(),
                ts.c.team_id,
                ts.c.season_end_year,
            )
            return base, ts.c.season_end_year

        return build_query

    if scope == "single_game" and stat == "pts":
        bs = _boxscore_player_table()
        games = _games_table()
        players = _players_table()

        def build_query(filters: List[Any]) -> Tuple[Any, Any]:
            base = select(
                bs.c.player_id.label("subject_id"),
                players.c.full_name.label("label"),
                bs.c.pts.label("stat"),
                games.c.season_end_year,
                bs.c.game_id,
            ).select_from(
                bs.join(games, games.c.game_id == bs.c.game_id).join(
                    players,
                    players.c.player_id == bs.c.player_id,
                )
            )
            if filters:
                base = base.where(and_(*filters))
            base = base.order_by(
                bs.c.pts.desc().nullslast(),
                bs.c.player_id,
                bs.c.game_id,
            )
            return base, games.c.season_end_year

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

    filters: List[Any] = []
    echo: Dict[str, Any] = {
        "scope": req.scope,
        "stat": req.stat,
    }

    # Optional modifiers
    if req.season_end_year is not None:
        echo["season_end_year"] = req.season_end_year
        # Many scopes use this; safe to apply when column present in query builder.
        # We defer actual binding to builder by passing generic expressions.
        # Builder will AND them in where() if applicable.
        # To keep everything simple and explicit, we let each builder inspect this echo
        # via filters list constructed below.
    if req.is_playoffs is not None:
        echo["is_playoffs"] = req.is_playoffs

    # Translate generic filters into concrete expressions; builders will use them
    # only when relevant columns exist.
    if req.season_end_year is not None:
        filters.append(column("season_end_year") == req.season_end_year)
    if req.is_playoffs is not None:
        filters.append(column("is_playoffs").is_(req.is_playoffs))

    # Build base selectable and potential season column
    base, season_col = build_query(filters)

    # Count total rows using subquery
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

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
                    if "season_end_year" in row and row["season_end_year"] is not None
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

"""
Load games and boxscore_team (and optionally boxscore_player if present).

Constraints from schema:
- games: one row per game_id
- boxscore_team: one row per (game_id, team_id)
- Foreign keys:
  - games.home_team_id / away_team_id -> teams(team_id)
  - games.season_id -> seasons(season_id)
  - boxscore_team.game_id -> games(game_id)
  - boxscore_team.team_id/opponent_team_id -> teams(team_id)

Behavior:
- Uses CSVs from docs/phase_0_csv_inventory.json via etl.paths.
- If a required game-level CSV is missing, logs and skips.
- For boxscore_team, if inputs are missing, logs and skips.
- Uses id_resolution helpers (team + season) for IDs.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

import polars as pl
from psycopg import Connection

from .config import Config
from .db import copy_from_polars, truncate_table
from .id_resolution import (
    GameLookup,
    SeasonLookup,
    TeamLookup,
    build_game_lookup,
    build_season_lookup,
    build_team_lookup,
    resolve_season_id,
    resolve_team_id_from_abbrev,
)
from .logging_utils import get_logger, log_structured
from .paths import (
    GAME_SUMMARY_CSV,
    GAMES_CSV,
    LINE_SCORE_CSV,
    OTHER_STATS_CSV,
    resolve_csv_path,
)

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def _load_dims_for_games(conn: Connection) -> Tuple[pl.DataFrame, pl.DataFrame]:
    with conn.cursor() as cur:
        cur.execute("SELECT team_id, team_abbrev FROM teams")
        teams = pl.from_records(
            cur.fetchall(),
            schema=["team_id", "team_abbrev"],
        )

        cur.execute("SELECT season_id, season_end_year, lg FROM seasons")
        seasons = pl.from_records(
            cur.fetchall(),
            schema=["season_id", "season_end_year", "lg"],
        )

    return teams, seasons


def load_games(config: Config, conn: Connection) -> None:
    """
    Load games table from base game CSVs.

    Priority:
    - If GAMES_CSV exists, treat it as canonical.
    - Else, attempt to construct from GAME_SUMMARY_CSV.
    """
    teams_df, seasons_df = _load_dims_for_games(conn)
    team_lu = build_team_lookup(teams_df)
    season_lu = build_season_lookup(seasons_df)

    games_path = resolve_csv_path(config, GAMES_CSV)
    raw_games = _read_csv_if_exists(games_path)

    if raw_games is None:
        summary_path = resolve_csv_path(config, GAME_SUMMARY_CSV)
        raw_games = _read_csv_if_exists(summary_path)

    if raw_games is None:
        logger.warning("games load skipped: no games CSV found")
        return

    df = raw_games

    # Standardize core columns where present.
    rename_map = {}
    for candidate, target in [
        ("GAME_ID", "game_id"),
        ("game_id", "game_id"),
        ("SEASON", "season_end_year"),
        ("season", "season_end_year"),
        ("SEASON_ID", "season_end_year"),
        ("GAME_DATE", "game_date_est"),
        ("GAME_DATE_EST", "game_date_est"),
        ("GAME_TIME", "game_time_est"),
        ("HOME_TEAM_ABBREV", "home_team_abbrev"),
        ("VISITOR_TEAM_ABBREV", "away_team_abbrev"),
        ("HOME_ABBREV", "home_team_abbrev"),
        ("AWAY_ABBREV", "away_team_abbrev"),
        ("HOME_PTS", "home_pts"),
        ("AWAY_PTS", "away_pts"),
    ]:
        if candidate in df.columns:
            rename_map[candidate] = target
    if rename_map:
        df = df.rename(rename_map)

    # Derive lg where absent
    if "lg" not in df.columns:
        df = df.with_columns(pl.lit("NBA").alias("lg"))

    # Resolve season_id
    def _resolve_season(row) -> Optional[int]:
        year = row.get("season_end_year")
        if year is None:
            return None
        return resolve_season_id(int(year), row.get("lg"), season_lu)

    if "season_end_year" in df.columns:
        df = df.with_columns(
            pl.struct(["season_end_year", "lg"])
            .map_elements(_resolve_season, return_dtype=pl.Int64)
            .alias("season_id")
        )
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("season_id"))

    # Resolve team_ids from abbrevs
    def _resolve_team(abbrev_col: str, season_col: str, row) -> Optional[int]:
        abbr = row.get(abbrev_col)
        season = row.get(season_col)
        if abbr is None or season is None:
            return None
        return resolve_team_id_from_abbrev(str(abbr), int(season), team_lu)

    if "home_team_abbrev" in df.columns:
        df = df.with_columns(
            pl.struct(["home_team_abbrev", "season_end_year"])
            .map_elements(
                lambda r: _resolve_team("home_team_abbrev", "season_end_year", r),
                return_dtype=pl.Int64,
            )
            .alias("home_team_id")
        )
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("home_team_id"))

    if "away_team_abbrev" in df.columns:
        df = df.with_columns(
            pl.struct(["away_team_abbrev", "season_end_year"])
            .map_elements(
                lambda r: _resolve_team("away_team_abbrev", "season_end_year", r),
                return_dtype=pl.Int64,
            )
            .alias("away_team_id")
        )
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("away_team_id"))

    # Ensure required columns exist
    required_cols = [
        "game_id",
        "season_id",
        "season_end_year",
        "lg",
        "game_date_est",
        "game_time_est",
        "home_team_id",
        "away_team_id",
        "home_team_abbrev",
        "away_team_abbrev",
        "home_pts",
        "away_pts",
        "attendance",
        "arena",
        "is_playoffs",
        "is_neutral_site",
        "data_source",
    ]
    for col in required_cols:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    truncate_table(conn, "games", cascade=True)
    copy_from_polars(df.select(required_cols), "games", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded games",
        rows=df.height,
    )


def load_boxscore_team(config: Config, conn: Connection) -> None:
    """
    Load boxscore_team from line score / other stats CSVs if available.

    Requirements:
    - One row per (game_id, team_id).
    - Must reference an existing games row.
    """
    line_path = resolve_csv_path(config, LINE_SCORE_CSV)
    other_path = resolve_csv_path(config, OTHER_STATS_CSV)

    line_df = _read_csv_if_exists(line_path)
    if line_df is None:
        logger.warning("boxscore_team load skipped: linescore.csv not found")
        return

    other_df = _read_csv_if_exists(other_path)

    with conn.cursor() as cur:
        cur.execute("SELECT game_id, home_team_id, away_team_id FROM games")
        games_df = pl.from_records(
            cur.fetchall(),
            schema=["game_id", "home_team_id", "away_team_id"],
        )

        cur.execute("SELECT team_id, team_abbrev FROM teams")
        teams_df = pl.from_records(
            cur.fetchall(),
            schema=["team_id", "team_abbrev"],
        )

    team_lu = build_team_lookup(teams_df)
    game_lu = build_game_lookup(
        games_df.select(["game_id"])
    )

    # Normalize line score
    rename_map = {}
    for candidate, target in [
        ("GAME_ID", "game_id"),
        ("TEAM_ABBREV", "team_abbrev"),
        ("PTS", "pts"),
        ("FG", "fg"),
        ("FGA", "fga"),
        ("FG3", "fg3"),
        ("FG3A", "fg3a"),
        ("FT", "ft"),
        ("FTA", "fta"),
        ("ORB", "orb"),
        ("DRB", "drb"),
        ("TRB", "trb"),
        ("AST", "ast"),
        ("STL", "stl"),
        ("BLK", "blk"),
        ("TOV", "tov"),
        ("PF", "pf"),
    ]:
        if candidate in line_df.columns:
            rename_map[candidate] = target
    if rename_map:
        line_df = line_df.rename(rename_map)

    # Resolve team_id using season-independent abbrev mapping as a fallback.
    # If season is available, it can be incorporated later by enhancement.
    def _resolve_team_id(row) -> Optional[int]:
        abbr = row.get("team_abbrev")
        if not abbr:
            return None
        # No season in this CSV; use simple abbrev mapping
        return team_lu.by_abbrev.get(str(abbr).upper())

    line_df = line_df.with_columns(
        pl.struct(["team_abbrev"])
        .map_elements(_resolve_team_id, return_dtype=pl.Int64)
        .alias("team_id")
    )

    # Determine is_home using games table
    game_map = {
        r["game_id"]: (r["home_team_id"], r["away_team_id"])
        for r in games_df.iter_rows(named=True)
    }

    def _is_home(row) -> Optional[bool]:
        gid = row.get("game_id")
        tid = row.get("team_id")
        if not gid or tid is None:
            return None
        if gid not in game_map:
            return None
        home_id, away_id = game_map[gid]
        if tid == home_id:
            return True
        if tid == away_id:
            return False
        return None

    line_df = line_df.with_columns(
        pl.struct(["game_id", "team_id"])
        .map_elements(_is_home, return_dtype=pl.Boolean)
        .alias("is_home")
    )

    # Merge other_df if present for advanced stats (pace, ortg, drtg, etc.)
    if other_df is not None and not other_df.is_empty():
        # Attempt to align on (game_id, team_abbrev)
        other_renamed = other_df.rename(
            {
                k: v
                for k, v in {
                    "GAME_ID": "game_id",
                    "TEAM_ABBREV": "team_abbrev",
                    "PACE": "pace",
                    "ORTG": "ortg",
                    "DRTG": "drtg",
                }.items()
                if k in other_df.columns
            }
        )
        join_keys = [c for c in ["game_id", "team_abbrev"] if c in other_renamed.columns]
        if join_keys:
            line_df = line_df.join(other_renamed, on=join_keys, how="left")

    # Filter to rows that have valid game_id and team_id present in dims
    line_df = line_df.filter(
        pl.col("game_id").is_in(list(game_lu.by_game_id.keys()))
        & pl.col("team_id").is_not_null()
    )

    # Ensure required columns
    required_cols = [
        "game_id",
        "team_id",
        "is_home",
        "team_abbrev",
        "pts",
        "fg",
        "fga",
        "fg3",
        "fg3a",
        "ft",
        "fta",
        "orb",
        "drb",
        "trb",
        "ast",
        "stl",
        "blk",
        "tov",
        "pf",
        "pace",
        "ortg",
        "drtg",
    ]
    for col in required_cols:
        if col not in line_df.columns:
            line_df = line_df.with_columns(pl.lit(None).alias(col))

    truncate_table(conn, "boxscore_team")
    copy_from_polars(line_df.select(required_cols), "boxscore_team", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded boxscore_team",
        rows=line_df.height,
    )


def load_games_and_boxscores(config: Config, conn: Connection) -> None:
    """
    Orchestrator for games + boxscore_team.
    """
    load_games(config, conn)
    load_boxscore_team(config, conn)
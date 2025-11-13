"""
Player-season hub and satellite loaders.

Implements Phase 2 loading for:
- player_season (hub)
- player_season_per_game
- player_season_totals
- player_season_per36
- player_season_per100
- player_season_advanced

Key rules (per schema_overview):
- player_season is keyed by seas_id from playerseasoninfo.csv.
- TOT rows:
  - is_total = true
  - team_id NULL, team_abbrev = 'TOT'
- League averages:
  - is_league_average = true
  - team_id NULL
- Satellites:
  - Strict 1:1 with player_season via seas_id.
  - Load only rows with matching seas_id in hub.
"""

from __future__ import annotations

import os
from typing import Optional, Set

import polars as pl
from psycopg import Connection

from .config import Config
from .db import copy_from_polars, truncate_table
from .id_resolution import (
    build_player_lookup,
    build_season_lookup,
    build_team_lookup,
    resolve_season_id,
    resolve_team_id_from_abbrev,
)
from .logging_utils import get_logger, log_structured
from .paths import (
    PLAYER_ADVANCED_CSV,
    PLAYER_PER36_CSV,
    PLAYER_PER100_CSV,
    PLAYER_PER_GAME_CSV,
    PLAYER_SEASON_INFO_CSV,
    PLAYER_TOTALS_CSV,
    resolve_csv_path,
)

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def _load_dimension_dataframes(
    conn: Connection,
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Load minimal dimension snapshots from DB for id resolution.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, slug, full_name, first_name, last_name FROM players"
        )
        players = pl.from_records(
            cur.fetchall(),
            schema=["player_id", "slug", "full_name", "first_name", "last_name"],
        )

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

    return players, teams, seasons


def load_player_season_hub(config: Config, conn: Connection) -> None:
    """
    Build player_season hub from playerseasoninfo.csv.
    """
    psi_path = resolve_csv_path(config, PLAYER_SEASON_INFO_CSV)
    psi = _read_csv_if_exists(psi_path)
    if psi is None:
        logger.warning("player_season hub load skipped: playerseasoninfo.csv not found")
        return

    players_df, teams_df, seasons_df = _load_dimension_dataframes(conn)
    _player_lu = build_player_lookup(players_df)  # noqa: F841
    team_lu = build_team_lookup(teams_df)
    season_lu = build_season_lookup(seasons_df)

    # Normalize and build hub rows
    df = psi.rename(
        {
            "seas_id": "seas_id",
            "player_id": "player_id",
            "season": "season_end_year",
            "tm": "team_abbrev",
            "lg": "lg",
            "age": "age",
            "pos": "position",
            "experience": "experience",
        }
    )

    # TOT and league average handling
    df = df.with_columns(
        [
            # TOT rows
            pl.when(pl.col("team_abbrev") == "TOT")
            .then(True)
            .otherwise(False)
            .alias("is_total"),
            # league average: mark when team_abbrev is 'League Average' (if present)
            pl.when(pl.col("team_abbrev").str.to_lowercase() == "league average")
            .then(True)
            .otherwise(False)
            .alias("is_league_average"),
            pl.lit(False).alias("is_playoffs"),
        ]
    )

    # Resolve season_id
    def _resolve_season(row) -> Optional[int]:
        return resolve_season_id(
            int(row["season_end_year"]),
            row.get("lg"),
            season_lu,
        )

    df = df.with_columns(
        pl.struct(["season_end_year", "lg"])
        .map_elements(_resolve_season, return_dtype=pl.Int64)
        .alias("season_id")
    )

    # Resolve team_id, except for TOT/league-average where team_id must be NULL
    def _resolve_team(row) -> Optional[int]:
        if row["is_total"] or row["is_league_average"]:
            return None
        abbrev = row.get("team_abbrev")
        season = row.get("season_end_year")
        return resolve_team_id_from_abbrev(abbrev, season, team_lu)

    df = df.with_columns(
        pl.struct(["team_abbrev", "season_end_year", "is_total", "is_league_average"])
        .map_elements(_resolve_team, return_dtype=pl.Int64)
        .alias("team_id")
    )

    # Ensure required columns
    required = [
        "seas_id",
        "player_id",
        "season_id",
        "season_end_year",
        "team_id",
        "team_abbrev",
        "lg",
        "age",
        "position",
        "experience",
        "is_total",
        "is_league_average",
        "is_playoffs",
    ]
    for col in required:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    truncate_table(conn, "player_season", cascade=True)
    copy_from_polars(df.select(required), "player_season", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season hub",
        rows=df.height,
    )


def _load_hub_seas_ids(conn: Connection) -> Set[int]:
    with conn.cursor() as cur:
        cur.execute("SELECT seas_id FROM player_season")
        rows = cur.fetchall()
    return {int(r[0]) for r in rows}


def _filter_satellite(
    df: Optional[pl.DataFrame], hub_seas_ids: Set[int]
) -> Optional[pl.DataFrame]:
    if df is None or df.is_empty():
        return None
    if "seas_id" not in df.columns:
        return None
    return df.filter(pl.col("seas_id").is_in(hub_seas_ids))


def load_player_season_per_game(config: Config, conn: Connection) -> None:
    path = resolve_csv_path(config, PLAYER_PER_GAME_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("player_season_per_game load skipped: CSV not found")
        return

    hub_ids = _load_hub_seas_ids(conn)
    df = _filter_satellite(df.rename({"seas_id": "seas_id"}), hub_ids)
    if df is None:
        logger.info("No per_game rows after filtering; skipping")
        return

    truncate_table(conn, "player_season_per_game")
    copy_from_polars(df, "player_season_per_game", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season_per_game",
        rows=df.height,
    )


def load_player_season_totals(config: Config, conn: Connection) -> None:
    path = resolve_csv_path(config, PLAYER_TOTALS_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("player_season_totals load skipped: CSV not found")
        return

    hub_ids = _load_hub_seas_ids(conn)
    df = _filter_satellite(df, hub_ids)
    if df is None:
        logger.info("No totals rows after filtering; skipping")
        return

    truncate_table(conn, "player_season_totals")
    copy_from_polars(df, "player_season_totals", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season_totals",
        rows=df.height,
    )


def load_player_season_per36(config: Config, conn: Connection) -> None:
    path = resolve_csv_path(config, PLAYER_PER36_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("player_season_per36 load skipped: CSV not found")
        return

    hub_ids = _load_hub_seas_ids(conn)
    df = _filter_satellite(df, hub_ids)
    if df is None:
        logger.info("No per36 rows after filtering; skipping")
        return

    truncate_table(conn, "player_season_per36")
    copy_from_polars(df, "player_season_per36", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season_per36",
        rows=df.height,
    )


def load_player_season_per100(config: Config, conn: Connection) -> None:
    path = resolve_csv_path(config, PLAYER_PER100_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("player_season_per100 load skipped: CSV not found")
        return

    hub_ids = _load_hub_seas_ids(conn)
    df = _filter_satellite(df, hub_ids)
    if df is None:
        logger.info("No per100 rows after filtering; skipping")
        return

    truncate_table(conn, "player_season_per100")
    copy_from_polars(df, "player_season_per100", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season_per100",
        rows=df.height,
    )


def load_player_season_advanced(config: Config, conn: Connection) -> None:
    path = resolve_csv_path(config, PLAYER_ADVANCED_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("player_season_advanced load skipped: CSV not found")
        return

    hub_ids = _load_hub_seas_ids(conn)
    df = _filter_satellite(df, hub_ids)
    if df is None:
        logger.info("No advanced rows after filtering; skipping")
        return

    truncate_table(conn, "player_season_advanced")
    copy_from_polars(df, "player_season_advanced", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded player_season_advanced",
        rows=df.height,
    )


def load_all_player_seasons(config: Config, conn: Connection) -> None:
    """
    Orchestrate player-season hub and satellite loads.
    """
    load_player_season_hub(config, conn)
    load_player_season_per_game(config, conn)
    load_player_season_totals(config, conn)
    load_player_season_per36(config, conn)
    load_player_season_per100(config, conn)
    load_player_season_advanced(config, conn)

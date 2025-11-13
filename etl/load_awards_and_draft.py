"""
Load awards and draft tables.

Targets:
- awards_all_star_selections
- awards_player_shares
- awards_end_of_season_teams
- awards_end_of_season_voting
- draft_picks

Key rules:
- Prefer numeric player_id / team_id from CSVs when present.
- Otherwise resolve via id_resolution helpers from names/slugs.
- If a row cannot be resolved deterministically:
  - Keep nullable FKs as NULL.
  - Do not drop the row unless violating hard PK/FK constraints.
- Missing CSVs are logged and skipped.
"""

from __future__ import annotations

import os
from typing import Optional

import polars as pl
from psycopg import Connection

from .config import Config
from .db import copy_from_polars, truncate_table
from .id_resolution import (
    PlayerLookup,
    SeasonLookup,
    TeamLookup,
    build_player_lookup,
    build_season_lookup,
    build_team_lookup,
    resolve_player_id_from_name,
    resolve_season_id,
    resolve_team_id_from_abbrev,
)
from .logging_utils import get_logger, log_structured
from .paths import (
    AWARDS_ALL_STAR_CSV,
    AWARDS_END_OF_SEASON_TEAMS_CSV,
    AWARDS_END_OF_SEASON_VOTING_CSV,
    AWARDS_PLAYER_SHARES_CSV,
    DRAFT_PICKS_CSV,
    resolve_csv_path,
)

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def _build_dimension_lookups(conn: Connection) -> tuple[PlayerLookup, TeamLookup, SeasonLookup]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, slug, full_name, first_name, last_name FROM players"
        )
        players_df = pl.from_records(
            cur.fetchall(),
            schema=["player_id", "slug", "full_name", "first_name", "last_name"],
        )

        cur.execute("SELECT team_id, team_abbrev FROM teams")
        teams_df = pl.from_records(
            cur.fetchall(),
            schema=["team_id", "team_abbrev"],
        )

        cur.execute("SELECT season_id, season_end_year, lg FROM seasons")
        seasons_df = pl.from_records(
            cur.fetchall(),
            schema=["season_id", "season_end_year", "lg"],
        )

    return (
        build_player_lookup(players_df),
        build_team_lookup(teams_df),
        build_season_lookup(seasons_df),
    )


def _resolve_player(
    row: dict,
    id_col: str,
    name_col: str,
    lookup: PlayerLookup,
) -> Optional[int]:
    numeric = row.get(id_col)
    name = row.get(name_col) or ""
    if numeric not in (None, ""):
        try:
            numeric = int(numeric)
        except Exception:
            numeric = None
    return resolve_player_id_from_name(str(name), lookup, numeric_id=numeric)


def _resolve_team(
    row: dict,
    abbrev_col: str,
    season_col: str,
    lookup: TeamLookup,
) -> Optional[int]:
    abbr = row.get(abbrev_col)
    season = row.get(season_col)
    if not abbr or season is None:
        return None
    try:
        season_int = int(season)
    except Exception:
        return None
    return resolve_team_id_from_abbrev(str(abbr), season_int, lookup)


def _resolve_season(
    row: dict,
    season_col: str,
    lg_col: str,
    lookup: SeasonLookup,
) -> Optional[int]:
    year = row.get(season_col)
    if year is None:
        return None
    try:
        year_int = int(year)
    except Exception:
        return None
    lg = row.get(lg_col)
    return resolve_season_id(year_int, lg, lookup)


def load_awards_all_star(config: Config, conn: Connection) -> None:
    csv_path = resolve_csv_path(config, AWARDS_ALL_STAR_CSV)
    df = _read_csv_if_exists(csv_path)
    if df is None:
        logger.warning("awards_all_star_selections load skipped: CSV not found")
        return

    player_lu, _, season_lu = _build_dimension_lookups(conn)

    # Expected columns from inventory-style files:
    # season, lg, player, player_id?
    rename_map = {}
    for src, tgt in [
        ("season", "season_end_year"),
        ("lg", "lg"),
        ("player", "player_name"),
        ("player_id", "player_id_raw"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    # Resolve season_id
    def _season(row: dict) -> Optional[int]:
        return _resolve_season(row, "season_end_year", "lg", season_lu)

    if "season_end_year" in df.columns:
        df = df.with_columns(
            pl.struct(["season_end_year", "lg"])
            .map_elements(
                lambda r: _season(r),
                return_dtype=pl.Int64,
            )
            .alias("season_id")
        )
    else:
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("season_id"))

    # Resolve player_id
    def _player(row: dict) -> Optional[int]:
        return _resolve_player(row, "player_id_raw", "player_name", player_lu)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_player, return_dtype=pl.Int64)
        .alias("player_id")
    )

    # Ensure minimal set of columns as per schema.sql (rest left nullable)
    required = [
        "season_id",
        "season_end_year",
        "player_id",
    ]
    for c in required:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))

    truncate_table(conn, "awards_all_star_selections")
    copy_from_polars(df.select(required), "awards_all_star_selections", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded awards_all_star_selections",
        rows=df.height,
    )


def load_awards_player_shares(config: Config, conn: Connection) -> None:
    csv_path = resolve_csv_path(config, AWARDS_PLAYER_SHARES_CSV)
    df = _read_csv_if_exists(csv_path)
    if df is None:
        logger.warning("awards_player_shares load skipped: CSV not found")
        return

    player_lu, _, season_lu = _build_dimension_lookups(conn)

    rename_map = {}
    for src, tgt in [
        ("season", "season_end_year"),
        ("lg", "lg"),
        ("player", "player_name"),
        ("player_id", "player_id_raw"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    def _season(row: dict) -> Optional[int]:
        return _resolve_season(row, "season_end_year", "lg", season_lu)

    df = df.with_columns(
        pl.struct(["season_end_year", "lg"])
        .map_elements(lambda r: _season(r), return_dtype=pl.Int64)
        .alias("season_id")
    )

    def _player(row: dict) -> Optional[int]:
        return _resolve_player(row, "player_id_raw", "player_name", player_lu)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_player, return_dtype=pl.Int64)
        .alias("player_id")
    )

    # Keep measure columns as-is; they are schema-defined numeric fields.
    base_cols = ["season_id", "season_end_year", "player_id"]
    for c in base_cols:
        if c not in df.columns:
            df = df.with_columns(pl.lit(None).alias(c))

    truncate_table(conn, "awards_player_shares")
    copy_from_polars(df, "awards_player_shares", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded awards_player_shares",
        rows=df.height,
    )


def load_awards_end_of_season_teams(config: Config, conn: Connection) -> None:
    csv_path = resolve_csv_path(config, AWARDS_END_OF_SEASON_TEAMS_CSV)
    df = _read_csv_if_exists(csv_path)
    if df is None:
        logger.warning("awards_end_of_season_teams load skipped: CSV not found")
        return

    player_lu, _, season_lu = _build_dimension_lookups(conn)

    rename_map = {}
    for src, tgt in [
        ("season", "season_end_year"),
        ("lg", "lg"),
        ("player", "player_name"),
        ("player_id", "player_id_raw"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    def _season(row: dict) -> Optional[int]:
        return _resolve_season(row, "season_end_year", "lg", season_lu)

    df = df.with_columns(
        pl.struct(["season_end_year", "lg"])
        .map_elements(lambda r: _season(r), return_dtype=pl.Int64)
        .alias("season_id")
    )

    def _player(row: dict) -> Optional[int]:
        return _resolve_player(row, "player_id_raw", "player_name", player_lu)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_player, return_dtype=pl.Int64)
        .alias("player_id")
    )

    truncate_table(conn, "awards_end_of_season_teams")
    copy_from_polars(df, "awards_end_of_season_teams", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded awards_end_of_season_teams",
        rows=df.height,
    )


def load_awards_end_of_season_voting(config: Config, conn: Connection) -> None:
    csv_path = resolve_csv_path(config, AWARDS_END_OF_SEASON_VOTING_CSV)
    df = _read_csv_if_exists(csv_path)
    if df is None:
        logger.warning("awards_end_of_season_voting load skipped: CSV not found")
        return

    player_lu, _, season_lu = _build_dimension_lookups(conn)

    rename_map = {}
    for src, tgt in [
        ("season", "season_end_year"),
        ("lg", "lg"),
        ("player", "player_name"),
        ("player_id", "player_id_raw"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    def _season(row: dict) -> Optional[int]:
        return _resolve_season(row, "season_end_year", "lg", season_lu)

    df = df.with_columns(
        pl.struct(["season_end_year", "lg"])
        .map_elements(lambda r: _season(r), return_dtype=pl.Int64)
        .alias("season_id")
    )

    def _player(row: dict) -> Optional[int]:
        return _resolve_player(row, "player_id_raw", "player_name", player_lu)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_player, return_dtype=pl.Int64)
        .alias("player_id")
    )

    truncate_table(conn, "awards_end_of_season_voting")
    copy_from_polars(df, "awards_end_of_season_voting", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded awards_end_of_season_voting",
        rows=df.height,
    )


def load_draft_picks(config: Config, conn: Connection) -> None:
    csv_path = resolve_csv_path(config, DRAFT_PICKS_CSV)
    df = _read_csv_if_exists(csv_path)
    if df is None:
        logger.warning("draft_picks load skipped: CSV not found")
        return

    player_lu, team_lu, season_lu = _build_dimension_lookups(conn)

    rename_map = {}
    for src, tgt in [
        ("season", "season_end_year"),
        ("lg", "lg"),
        ("player", "player_name"),
        ("player_id", "player_id_raw"),
        ("team", "team_abbrev"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    def _season(row: dict) -> Optional[int]:
        return _resolve_season(row, "season_end_year", "lg", season_lu)

    df = df.with_columns(
        pl.struct(["season_end_year", "lg"])
        .map_elements(lambda r: _season(r), return_dtype=pl.Int64)
        .alias("season_id")
    )

    def _player(row: dict) -> Optional[int]:
        return _resolve_player(row, "player_id_raw", "player_name", player_lu)

    def _team(row: dict) -> Optional[int]:
        return _resolve_team(row, "team_abbrev", "season_end_year", team_lu)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_player, return_dtype=pl.Int64)
        .alias("player_id"),
        pl.struct(df.columns)
        .map_elements(_team, return_dtype=pl.Int64)
        .alias("team_id"),
    )

    truncate_table(conn, "draft_picks")
    copy_from_polars(df, "draft_picks", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded draft_picks",
        rows=df.height,
    )


def load_all_awards_and_draft(config: Config, conn: Connection) -> None:
    """
    Orchestrate awards + draft loaders.
    """
    load_awards_all_star(config, conn)
    load_awards_player_shares(config, conn)
    load_awards_end_of_season_teams(config, conn)
    load_awards_end_of_season_voting(config, conn)
    load_draft_picks(config, conn)
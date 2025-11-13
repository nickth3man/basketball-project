"""
Play-by-play loader.

Loads pbp_events from play_by_play-style CSV(s) into the canonical schema:

Table: pbp_events
Grain:
- One row per (game_id, eventnum)

Constraints:
- game_id must exist in games (FK)
- team_id/opponent_team_id, player*_id are nullable and resolved when possible
"""

from __future__ import annotations

import os
from typing import Optional

import polars as pl
from psycopg import Connection

from .config import Config
from .db import copy_from_polars, truncate_table
from .id_resolution import (
    GameLookup,
    PlayerLookup,
    TeamLookup,
    build_game_lookup,
    build_player_lookup,
    build_team_lookup,
    resolve_player_id_from_name,
)
from .logging_utils import get_logger, log_structured
from .paths import PBP_CSV, resolve_csv_path

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def _load_dimension_lookups(
    conn: Connection,
) -> tuple[GameLookup, PlayerLookup, TeamLookup]:
    with conn.cursor() as cur:
        cur.execute("SELECT game_id FROM games")
        games_df = pl.from_records(cur.fetchall(), schema=["game_id"])

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

    game_lu = build_game_lookup(games_df)
    player_lu = build_player_lookup(players_df)
    team_lu = build_team_lookup(teams_df)
    return game_lu, player_lu, team_lu


def load_pbp_events(config: Config, conn: Connection) -> None:
    """
    Load pbp_events from configured CSV.

    If file is missing, logs and skips gracefully.
    """
    path = resolve_csv_path(config, PBP_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("pbp_events load skipped: play_by_play.csv not found")
        return

    game_lu, player_lu, team_lu = _load_dimension_lookups(conn)

    # Standardize columns based on common play-by-play exports
    rename_map = {}
    for candidate, target in [
        ("GAME_ID", "game_id"),
        ("EVENTNUM", "eventnum"),
        ("PERIOD", "period"),
        ("PCTIMESTRING", "clk"),
        ("EVENTTYPE", "event_type"),
        ("HOMEDESCRIPTION", "home_desc"),
        ("VISITORDESCRIPTION", "away_desc"),
        ("SCORE", "score"),
        ("SCOREMARGIN", "scoremargin"),
        ("PLAYER1_ID", "player1_raw"),
        ("PLAYER2_ID", "player2_raw"),
        ("PLAYER3_ID", "player3_raw"),
        ("PLAYER1_NAME", "player1_name"),
        ("PLAYER2_NAME", "player2_name"),
        ("PLAYER3_NAME", "player3_name"),
        ("PLAYER1_TEAM_ABBREV", "player1_team_abbrev"),
        ("PLAYER2_TEAM_ABBREV", "player2_team_abbrev"),
        ("PLAYER3_TEAM_ABBREV", "player3_team_abbrev"),
        ("TEAM_ID", "team_raw"),
        ("OPP_TEAM_ID", "opp_team_raw"),
        ("TEAM_ABBREV", "team_abbrev"),
        ("OPP_TEAM_ABBREV", "opp_team_abbrev"),
    ]:
        if candidate in df.columns:
            rename_map[candidate] = target
    if rename_map:
        df = df.rename(rename_map)

    # Filter to rows with known game_ids
    if "game_id" not in df.columns or "eventnum" not in df.columns:
        logger.warning("pbp_events load skipped: missing game_id/eventnum columns")
        return

    df = df.filter(pl.col("game_id").is_in(list(game_lu.by_game_id.keys())))

    if df.is_empty():
        logger.info("No PBP rows after filtering to known games; skipping")
        return

    # Compute clk_remaining (simple: convert MM:SS to seconds in period)
    def _to_remaining(clk: str) -> Optional[float]:
        if not clk or not isinstance(clk, str):
            return None
        try:
            parts = clk.split(":")
            if len(parts) != 2:
                return None
            m, s = int(parts[0]), int(parts[1])
            # NBA periods: 12 minutes; OT: 5, but here we store raw MM:SS in
            # clk_remaining
            return float(m * 60 + s)
        except Exception:
            return None

    df = df.with_columns(
        pl.col("clk").cast(pl.Utf8),
    ).with_columns(
        pl.col("clk")
        .map_elements(_to_remaining, return_dtype=pl.Float64)
        .alias("clk_remaining")
    )

    # Resolve teams from abbrevs when available
    def _resolve_team_from_row(abbrev_field: str, row) -> Optional[int]:
        abbr = row.get(abbrev_field)
        if not abbr:
            return None
        # No season context here; rely on abbrev-only lookup
        return team_lu.by_abbrev.get(str(abbr).upper())

    df = df.with_columns(
        pl.struct(["team_abbrev"])
        .map_elements(
            lambda r: _resolve_team_from_row("team_abbrev", r), return_dtype=pl.Int64
        )
        .alias("team_id"),
        pl.struct(["opp_team_abbrev"])
        .map_elements(
            lambda r: _resolve_team_from_row("opp_team_abbrev", r),
            return_dtype=pl.Int64,
        )
        .alias("opponent_team_id"),
    )

    # Resolve players from numeric ids or names when available.
    def _resolve_player(raw_id_col: str, name_col: str, row) -> Optional[int]:
        raw = row.get(raw_id_col)
        name = row.get(name_col)
        try_numeric = None
        if raw not in (None, ""):
            try:
                try_numeric = int(raw)
            except Exception:
                try_numeric = None
        return resolve_player_id_from_name(
            name or "",
            player_lu,
            slug=None,
            numeric_id=try_numeric,
        )

    df = df.with_columns(
        pl.struct(["player1_raw", "player1_name"])
        .map_elements(
            lambda r: _resolve_player("player1_raw", "player1_name", r),
            return_dtype=pl.Int64,
        )
        .alias("player1_id"),
        pl.struct(["player2_raw", "player2_name"])
        .map_elements(
            lambda r: _resolve_player("player2_raw", "player2_name", r),
            return_dtype=pl.Int64,
        )
        .alias("player2_id"),
        pl.struct(["player3_raw", "player3_name"])
        .map_elements(
            lambda r: _resolve_player("player3_raw", "player3_name", r),
            return_dtype=pl.Int64,
        )
        .alias("player3_id"),
    )

    # Description and score columns
    if "description" not in df.columns:
        # Prefer combined textual descriptions if present
        desc_cols = [c for c in ["home_desc", "away_desc"] if c in df.columns]
        if desc_cols:
            df = df.with_columns(
                pl.concat_str(
                    [pl.col(c).fill_null("").alias(c) for c in desc_cols],
                    separator=" ",
                )
                .str.strip_chars()
                .alias("description")
            )
        else:
            df = df.with_columns(pl.lit(None).alias("description"))

    # Derive running scores if SCORE column present
    if "score" in df.columns:

        def _split_score(score: str) -> tuple[Optional[int], Optional[int]]:
            if not score or "-" not in score:
                return None, None
            try:
                home, away = score.split("-")
                return int(home), int(away)
            except Exception:
                return None, None

        df = df.with_columns(
            pl.col("score")
            .map_elements(lambda s: _split_score(s)[0], return_dtype=pl.Int64)
            .alias("home_score"),
            pl.col("score")
            .map_elements(lambda s: _split_score(s)[1], return_dtype=pl.Int64)
            .alias("away_score"),
        )
    else:
        df = df.with_columns(
            pl.lit(None, dtype=pl.Int64).alias("home_score"),
            pl.lit(None, dtype=pl.Int64).alias("away_score"),
        )

    # Ensure required columns
    required_cols = [
        "game_id",
        "eventnum",
        "period",
        "clk",
        "clk_remaining",
        "event_type",
        "option1",
        "option2",
        "option3",
        "team_id",
        "opponent_team_id",
        "player1_id",
        "player2_id",
        "player3_id",
        "description",
        "score",
        "home_score",
        "away_score",
    ]
    for col in required_cols:
        if col not in df.columns:
            df = df.with_columns(pl.lit(None).alias(col))

    # Enforce uniqueness on (game_id, eventnum) by grouping; keep first occurrence.
    df = df.sort(["game_id", "eventnum"]).unique(
        subset=["game_id", "eventnum"], keep="first"
    )

    truncate_table(conn, "pbp_events")
    copy_from_polars(df.select(required_cols), "pbp_events", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded pbp_events",
        rows=df.height,
    )

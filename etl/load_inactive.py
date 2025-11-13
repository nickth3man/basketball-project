"""
Load inactive_players table.

Source:
- inactive_players.csv (if present)

Grain:
- One row per (game_id, player_id) representing an officially inactive player.

Rules:
- Resolve game_id directly from CSV; must match an existing games row.
- Resolve player_id:
  - Prefer numeric ID from CSV if present.
  - Else resolve from name via PlayerLookup.
- If unresolved, row is skipped to avoid FK violations.
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
    build_game_lookup,
    build_player_lookup,
    resolve_player_id_from_name,
)
from .logging_utils import get_logger, log_structured
from .paths import INACTIVE_PLAYERS_CSV, resolve_csv_path

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def _build_lookups(conn: Connection) -> tuple[GameLookup, PlayerLookup]:
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

    return build_game_lookup(games_df), build_player_lookup(players_df)


def load_inactive_players(config: Config, conn: Connection) -> None:
    """
    Load inactive_players from CSV into canonical table.
    """
    path = resolve_csv_path(config, INACTIVE_PLAYERS_CSV)
    df = _read_csv_if_exists(path)
    if df is None:
        logger.warning("inactive_players load skipped: CSV not found")
        return

    game_lu, player_lu = _build_lookups(conn)

    # Normalize basic columns
    rename_map = {}
    for src, tgt in [
        ("GAME_ID", "game_id"),
        ("game_id", "game_id"),
        ("PLAYER_ID", "player_id_raw"),
        ("player_id", "player_id_raw"),
        ("PLAYER_NAME", "player_name"),
        ("player", "player_name"),
    ]:
        if src in df.columns:
            rename_map[src] = tgt
    if rename_map:
        df = df.rename(rename_map)

    if "game_id" not in df.columns:
        logger.warning("inactive_players load skipped: missing game_id column")
        return

    # Filter to known games only
    df = df.filter(pl.col("game_id").is_in(list(game_lu.by_game_id.keys())))
    if df.is_empty():
        logger.info("No inactive rows for known games; skipping")
        return

    # Resolve player_id
    def _resolve_player(row) -> Optional[int]:
        raw = row.get("player_id_raw")
        name = row.get("player_name") or ""
        numeric = None
        if raw not in (None, ""):
            try:
                numeric = int(raw)
            except Exception:
                numeric = None
        return resolve_player_id_from_name(name, player_lu, numeric_id=numeric)

    df = df.with_columns(
        pl.struct(df.columns)
        .map_elements(_resolve_player, return_dtype=pl.Int64)
        .alias("player_id")
    )

    # Drop rows where player_id could not be resolved to avoid FK violation
    df = df.drop_nulls("player_id")
    if df.is_empty():
        logger.info("All inactive rows unresolved; skipping")
        return

    # Deduplicate (game_id, player_id)
    df = df.select(["game_id", "player_id"]).unique()

    truncate_table(conn, "inactive_players")
    copy_from_polars(df, "inactive_players", conn)
    log_structured(
        logger,
        logger.level,
        "Loaded inactive_players",
        rows=df.height,
    )

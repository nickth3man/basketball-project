"""
Pure ID resolution helpers.

These functions operate only on in-memory structures (typically Polars DataFrames)
prepared by upstream loaders. No direct database I/O is performed here.

They implement deterministic resolution rules consistent with:
- db/schema.sql
- docs/schema_overview.md
- CSV inventory semantics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import polars as pl

from .logging_utils import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class PlayerLookup:
    by_id: Dict[int, int]
    by_slug: Dict[str, int]
    by_full_name: Dict[str, int]
    aliases: Dict[str, int]


@dataclass(frozen=True)
class TeamLookup:
    by_id: Dict[int, int]
    # (season_end_year, raw_abbrev) -> team_id
    by_season_abbrev: Dict[Tuple[int, str], int]
    # raw_abbrev (fallback when season not available)
    by_abbrev: Dict[str, int]


@dataclass(frozen=True)
class SeasonLookup:
    # (season_end_year, lg_normalized) -> season_id
    by_year_lg: Dict[Tuple[int, str], int]


@dataclass(frozen=True)
class GameLookup:
    by_game_id: Dict[str, str]


def build_player_lookup(
    players_df: pl.DataFrame,
    aliases_df: Optional[pl.DataFrame] = None,
) -> PlayerLookup:
    """
    Build canonical player lookup mappings.

    Expected columns:
    - players_df: player_id, slug, full_name, first_name, last_name
    - aliases_df (optional): alias_value, player_id
    """
    by_id: Dict[int, int] = {}
    by_slug: Dict[str, int] = {}
    by_full_name: Dict[str, int] = {}
    aliases: Dict[str, int] = {}

    if not players_df.is_empty():
        for row in players_df.select(
            ["player_id", "slug", "full_name", "first_name", "last_name"]
        ).iter_rows(named=True):
            pid = int(row["player_id"])
            by_id[pid] = pid

            slug = (row.get("slug") or "").strip()
            if slug:
                by_slug[slug.lower()] = pid

            full_name = (row.get("full_name") or "").strip()
            if full_name:
                by_full_name[full_name.lower()] = pid

            # Provide a basic "First Last" mapping if not already covered
            first = (row.get("first_name") or "").strip()
            last = (row.get("last_name") or "").strip()
            if first and last:
                name = f"{first} {last}".lower()
                by_full_name.setdefault(name, pid)

    if aliases_df is not None and not aliases_df.is_empty():
        for row in aliases_df.select(["alias_value", "player_id"]).iter_rows(
            named=True
        ):
            alias = (row.get("alias_value") or "").strip().lower()
            pid = row.get("player_id")
            if alias and pid is not None:
                aliases.setdefault(alias, int(pid))

    return PlayerLookup(
        by_id=by_id,
        by_slug=by_slug,
        by_full_name=by_full_name,
        aliases=aliases,
    )


def build_team_lookup(
    teams_df: pl.DataFrame,
    team_history_df: Optional[pl.DataFrame] = None,
    abbrev_map_df: Optional[pl.DataFrame] = None,
) -> TeamLookup:
    """
    Build team lookup with season-aware abbreviation mapping.

    Expected:
    - teams_df: team_id, team_abbrev
    - team_history_df: team_id, season_end_year, team_abbrev (or name metadata)
    - abbrev_map_df: season_end_year, raw_abbrev, team_id
    """
    by_id: Dict[int, int] = {}
    by_season_abbrev: Dict[Tuple[int, str], int] = {}
    by_abbrev: Dict[str, int] = {}

    if not teams_df.is_empty():
        for row in teams_df.select(["team_id", "team_abbrev"]).iter_rows(named=True):
            tid = int(row["team_id"])
            by_id[tid] = tid
            abbr = (row.get("team_abbrev") or "").strip()
            if abbr:
                by_abbrev.setdefault(abbr.upper(), tid)

    if team_history_df is not None and not team_history_df.is_empty():
        cols = [
            c
            for c in ["team_id", "season_end_year", "team_abbrev"]
            if c in team_history_df.columns
        ]
        if {"team_id", "season_end_year"}.issubset(set(cols)):
            for row in team_history_df.select(cols).iter_rows(named=True):
                tid = int(row["team_id"])
                season = int(row["season_end_year"])
                abbr = (row.get("team_abbrev") or "").strip()
                if abbr:
                    key = (season, abbr.upper())
                    by_season_abbrev.setdefault(key, tid)

    if abbrev_map_df is not None and not abbrev_map_df.is_empty():
        if {"season_end_year", "raw_abbrev", "team_id"}.issubset(abbrev_map_df.columns):
            for row in abbrev_map_df.select(
                ["season_end_year", "raw_abbrev", "team_id"]
            ).iter_rows(named=True):
                tid = row.get("team_id")
                season = row.get("season_end_year")
                abbr = (row.get("raw_abbrev") or "").strip()
                if tid is None or season is None or not abbr:
                    continue
                key = (int(season), abbr.upper())
                by_season_abbrev.setdefault(key, int(tid))
                # Best-effort season-agnostic fallback
                by_abbrev.setdefault(abbr.upper(), int(tid))

    return TeamLookup(
        by_id=by_id,
        by_season_abbrev=by_season_abbrev,
        by_abbrev=by_abbrev,
    )


def build_season_lookup(seasons_df: pl.DataFrame) -> SeasonLookup:
    """
    Build season lookup keyed by (season_end_year, normalized_lg).
    """
    by_year_lg: Dict[Tuple[int, str], int] = {}
    if not seasons_df.is_empty():
        for row in seasons_df.select(["season_id", "season_end_year", "lg"]).iter_rows(
            named=True
        ):
            sid = int(row["season_id"])
            year = int(row["season_end_year"])
            lg = (row.get("lg") or "NBA").strip().upper()
            key = (year, lg or "NBA")
            by_year_lg.setdefault(key, sid)
    return SeasonLookup(by_year_lg=by_year_lg)


def build_game_lookup(games_df: pl.DataFrame) -> GameLookup:
    """
    Build a game_id lookup; fairly trivial but kept for symmetry.
    """
    by_game_id: Dict[str, str] = {}
    if not games_df.is_empty():
        for row in games_df.select(["game_id"]).iter_rows(named=True):
            gid = (row.get("game_id") or "").strip()
            if gid:
                by_game_id.setdefault(gid, gid)
    return GameLookup(by_game_id=by_game_id)


def resolve_player_id_from_name(
    name: str,
    lookup: PlayerLookup,
    slug: Optional[str] = None,
    numeric_id: Optional[int] = None,
) -> Optional[int]:
    """
    Deterministic resolution order:
    1) numeric_id if present in by_id
    2) slug (case-insensitive) via by_slug
    3) name (case-insensitive) via by_full_name
    4) aliases (case-insensitive)
    """
    if numeric_id is not None and numeric_id in lookup.by_id:
        return numeric_id

    if slug:
        pid = lookup.by_slug.get(slug.strip().lower())
        if pid is not None:
            return pid

    key = (name or "").strip().lower()
    if key:
        pid = lookup.by_full_name.get(key)
        if pid is not None:
            return pid

        pid = lookup.aliases.get(key)
        if pid is not None:
            return pid

    return None


def resolve_team_id_from_abbrev(
    abbrev: str,
    season_end_year: Optional[int],
    lookup: TeamLookup,
) -> Optional[int]:
    """
    Resolve team_id from abbreviation with deterministic rules:
    1) If season_end_year provided: use (season_end_year, abbrev) mapping.
    2) Fallback to season-agnostic abbrev mapping.
    """
    if not abbrev:
        return None
    ab = abbrev.strip().upper()

    if season_end_year is not None:
        key = (int(season_end_year), ab)
        tid = lookup.by_season_abbrev.get(key)
        if tid is not None:
            return tid

    return lookup.by_abbrev.get(ab)


def resolve_season_id(
    season_end_year: int,
    lg: Optional[str],
    lookup: SeasonLookup,
) -> Optional[int]:
    """
    Resolve season_id from season_end_year and league code.

    Normalizes lg (default NBA if missing).
    """
    if season_end_year is None:
        return None
    lg_norm = (lg or "NBA").strip().upper() or "NBA"
    return lookup.by_year_lg.get((int(season_end_year), lg_norm))


def ensure_game_exists(game_id: str, lookup: GameLookup) -> bool:
    """
    Check if a game_id is known in the provided lookup.
    """
    if not game_id:
        return False
    return game_id in lookup.by_game_id

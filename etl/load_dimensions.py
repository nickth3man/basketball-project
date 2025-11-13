"""
Dimension loaders.

Implements Phase 2 loading for:
- players
- player_aliases
- teams
- team_history
- team_abbrev_mappings
- seasons

Rules:
- Use CSVs described in docs/phase_0_csv_inventory.json (via etl.paths).
- All logic uses COPY via etl.db helpers where practical.
- Missing optional CSVs are tolerated: logged as warnings and skipped.
"""

from __future__ import annotations

import os
from typing import Optional

import polars as pl
from psycopg import Connection

from .config import Config
from .db import copy_from_polars, execute, truncate_table
from .logging_utils import get_logger, log_structured
from .paths import (
    PLAYER_CAREER_INFO_CSV,
    PLAYER_CSV,
    PLAYER_DIRECTORY_CSV,
    TEAM_CSV,
    TEAM_DETAILS_CSV,
    TEAM_HISTORY_CSV,
    resolve_csv_path,
)

logger = get_logger(__name__)


def _read_csv_if_exists(path: str) -> Optional[pl.DataFrame]:
    if not os.path.exists(path):
        logger.warning("CSV missing; skipping", extra={"path": path})
        return None
    return pl.read_csv(path)


def load_players(config: Config, conn: Connection) -> None:
    """
    Load players dimension from:
    - player.csv (core ids, full_name, is_active)
    - playerdirectory.csv (slugs + mapping info)
    - playercareerinfo.csv (career span + HOF)
    """
    player_path = resolve_csv_path(config, PLAYER_CSV)
    directory_path = resolve_csv_path(config, PLAYER_DIRECTORY_CSV)
    career_path = resolve_csv_path(config, PLAYER_CAREER_INFO_CSV)

    player_df = _read_csv_if_exists(player_path)
    if player_df is None:
        logger.warning("players load skipped: player.csv not found")
        return

    directory_df = _read_csv_if_exists(directory_path)
    career_df = _read_csv_if_exists(career_path)

    # Normalize key columns
    player_df = player_df.rename(
        {
            "id": "player_id",
            "full_name": "full_name",
            "first_name": "first_name",
            "last_name": "last_name",
            "is_active": "is_active",
        }
    )

    if directory_df is not None:
        directory_df = directory_df.rename({"slug": "slug"})
    if career_df is not None:
        career_df = career_df.rename(
            {
                "hof": "hof_inducted",
                "first_seas": "rookie_year",
                "last_seas": "final_year",
            }
        )

    # Left join directory and career info on best-effort keys
    # playerdirectory has no numeric id: approximate via name match.
    if directory_df is not None:
        player_df = player_df.join(
            directory_df.select(
                [
                    pl.col("player").alias("dir_player"),
                    pl.col("slug"),
                ]
            ),
            left_on="full_name",
            right_on="dir_player",
            how="left",
        ).with_columns(pl.col("slug").cast(pl.Utf8).alias("slug"))

    if career_df is not None:
        player_df = player_df.join(
            career_df.select(
                [
                    "player_id",
                    "hof_inducted",
                    "rookie_year",
                    "final_year",
                ]
            ),
            on="player_id",
            how="left",
            suffix="_career",
        )

    # Map is_active int to boolean where present.
    if "is_active" in player_df.columns:
        player_df = player_df.with_columns(
            pl.when(pl.col("is_active") == 1)
            .then(True)
            .when(pl.col("is_active") == 0)
            .then(False)
            .otherwise(None)
            .alias("is_active")
        )

    # Ensure required columns exist for players table.
    for col in [
        "player_id",
        "slug",
        "full_name",
        "first_name",
        "last_name",
        "is_active",
        "birth_date",
        "birth_year",
        "height_inches",
        "weight_lbs",
        "country",
        "position",
        "shoots",
        "hof_inducted",
        "rookie_year",
        "final_year",
    ]:
        if col not in player_df.columns:
            player_df = player_df.with_columns(pl.lit(None).alias(col))

    # Truncate and load
    truncate_table(conn, "players", cascade=True)
    cols = [
        "player_id",
        "slug",
        "full_name",
        "first_name",
        "last_name",
        "is_active",
        "birth_date",
        "birth_year",
        "height_inches",
        "weight_lbs",
        "country",
        "position",
        "shoots",
        "hof_inducted",
        "rookie_year",
        "final_year",
    ]
    copy_from_polars(player_df.select(cols), "players", conn, columns=cols)
    log_structured(logger, logger.level, "Loaded players", rows=player_df.height)


def load_player_aliases(config: Config, conn: Connection) -> None:
    """
    Populate player_aliases from playerdirectory.csv (slug and name variants).
    """
    directory_path = resolve_csv_path(config, PLAYER_DIRECTORY_CSV)
    directory_df = _read_csv_if_exists(directory_path)
    player_path = resolve_csv_path(config, PLAYER_CSV)
    player_df = _read_csv_if_exists(player_path)

    if directory_df is None or player_df is None:
        logger.warning(
            "player_aliases load skipped: required CSVs not found",
            extra={"directory": directory_path, "player": player_path},
        )
        return

    player_df = player_df.rename({"id": "player_id", "full_name": "full_name"})
    # Join on name to map slug-based rows to numeric id.
    joined = directory_df.join(
        player_df.select(["player_id", "full_name"]),
        left_on="player",
        right_on="full_name",
        how="left",
    )

    alias_rows = []

    for row in joined.iter_rows(named=True):
        pid = row.get("player_id")
        slug = row.get("slug")
        name = row.get("player")
        if pid is None:
            continue
        if slug:
            alias_rows.append((pid, "slug", str(slug)))
        if name:
            alias_rows.append((pid, "name", str(name)))

    if not alias_rows:
        logger.info("No player_alias rows generated; skipping load")
        return

    truncate_table(conn, "player_aliases")
    alias_df = pl.DataFrame(
        alias_rows,
        schema=["player_id", "alias_type", "alias_value"],
    )
    copy_from_polars(alias_df, "player_aliases", conn)
    log_structured(logger, logger.level, "Loaded player_aliases", rows=len(alias_rows))


def load_teams(config: Config, conn: Connection) -> None:
    """
    Load teams and team_details/team_history.
    """
    team_df = _read_csv_if_exists(resolve_csv_path(config, TEAM_CSV))
    if team_df is None:
        logger.warning("teams load skipped: team.csv not found")
        return

    team_df = team_df.rename(
        {
            "id": "team_id",
            "full_name": "team_name",
            "city": "team_city",
            "abbreviation": "team_abbrev",
        }
    )

    for col in [
        "team_id",
        "team_abbrev",
        "team_name",
        "team_city",
        "start_season",
        "end_season",
        "is_active",
    ]:
        if col not in team_df.columns:
            team_df = team_df.with_columns(pl.lit(None).alias(col))

    truncate_table(conn, "teams", cascade=True)
    copy_from_polars(team_df, "teams", conn)
    log_structured(logger, logger.level, "Loaded teams", rows=team_df.height)

    # Optional team_details
    details_df = _read_csv_if_exists(resolve_csv_path(config, TEAM_DETAILS_CSV))
    if details_df is not None:
        truncate_table(conn, "team_details", cascade=True)
        copy_from_polars(details_df, "team_details", conn)
        log_structured(
            logger,
            logger.level,
            "Loaded team_details",
            rows=details_df.height,
        )

    # Optional team_history
    history_df = _read_csv_if_exists(resolve_csv_path(config, TEAM_HISTORY_CSV))
    if history_df is not None:
        truncate_table(conn, "team_history", cascade=True)
        copy_from_polars(history_df, "team_history", conn)
        log_structured(
            logger,
            logger.level,
            "Loaded team_history",
            rows=history_df.height,
        )


def load_seasons(config: Config, conn: Connection) -> None:
    """
    Load seasons dimension.

    Currently uses a simple SELECT DISTINCT from games-related CSVs or is driven
    by pre-built season files when present.
    """
    # Placeholder: assume seasons are already created by earlier migrations
    # or another loader; keep this minimal and idempotent.
    log_structured(logger, logger.level, "Seasons loader is currently a no-op")


def load_all_dimensions(
    config: Config,
    conn: Connection,
    mode: str = "full",
    mode_params: Optional[dict] = None,
    dry_run: bool = False,
    etl_run_id: Optional[int] = None,
    etl_run_step_id: Optional[int] = None,
) -> None:
    """
    Orchestrate dimension loads.

    Behavior:
    - mode="full": truncate + reload all relevant dimension tables (current behavior).
    - incremental modes: currently conservative full reload (dimensions are small).
    - dry_run=True: no writes, only existence checks and logs.
    """
    del mode_params  # not used yet; reserved for future slicing

    log_structured(
        logger,
        logger.level,
        "load_all_dimensions_start",
        mode=mode,
        dry_run=dry_run,
        etl_run_id=etl_run_id,
        etl_run_step_id=etl_run_step_id,
    )

    if dry_run:
        # Touch CSV paths to ensure they can be resolved; do not mutate DB.
        for logical_name, path in [
            ("PLAYER_CSV", resolve_csv_path(config, PLAYER_CSV)),
            ("PLAYER_DIRECTORY_CSV", resolve_csv_path(config, PLAYER_DIRECTORY_CSV)),
            (
                "PLAYER_CAREER_INFO_CSV",
                resolve_csv_path(config, PLAYER_CAREER_INFO_CSV),
            ),
            ("TEAM_CSV", resolve_csv_path(config, TEAM_CSV)),
        ]:
            exists = os.path.exists(path)
            log_structured(
                logger,
                logger.level,
                "dry_run_dimension_input",
                logical_name=logical_name,
                path=path,
                exists=exists,
            )
        return

    # Full or incremental: for now, reload dimensions completely (idempotent).
    load_players(config, conn)
    load_player_aliases(config, conn)
    load_teams(config, conn)
    load_seasons(config, conn)

    log_structured(
        logger,
        logger.level,
        "load_all_dimensions_end",
        mode=mode,
        etl_run_id=etl_run_id,
        etl_run_step_id=etl_run_step_id,
    )

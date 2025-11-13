"""
CLI entrypoint to run the full Phase 2 ETL against the Phase 1 canonical schema.

Execution order (by default / full mode):
1) Start etl_run and track CSV data_versions
2) Load core dimensions
3) Load player_season hub + satellites
4) Load team_season hub + satellites
5) Load games + boxscore_team
6) Load pbp_events
7) Load awards + draft tables
8) Load inactive_players
9) Run validations
10) Finalize etl_run status

Usage:
    python -m scripts.run_full_etl
or
    python scripts/run_full_etl.py

Environment:
- PG_DSN: PostgreSQL connection string
- CSV_ROOT: Root directory for CSV files (defaults to ./csv_files)
- Optional ETL behavior:
  - ETL_EXPECTATIONS_PATH: override for etl/expectations.yaml
  - ETL_ENABLE_EXPECTATIONS: toggle expectations / drift checks (default true)
  - ETL_MODE / ETL_MODE_PARAMS: defaults for mode when CLI flags omitted
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from typing import Any, Dict, List, Optional

from etl.config import Config, get_config
from etl.db import get_connection, release_connection
from etl.expectations_loader import Expectations, load_expectations
from etl.load_awards_and_draft import load_all_awards_and_draft
from etl.load_dimensions import load_all_dimensions
from etl.load_games_and_boxscores import load_games_and_boxscores
from etl.load_inactive import load_inactive_players
from etl.load_metadata import (
    finalize_etl_run,
    finalize_etl_step,
    start_etl_run,
    start_etl_step,
    track_all_csv_data_versions,
    write_etl_run_report,
)
from etl.load_pbp import load_pbp_events
from etl.load_player_seasons import load_all_player_seasons
from etl.load_team_seasons import load_all_team_seasons
from etl.logging_utils import get_logger, log_structured
from etl.schema_drift import write_schema_drift_report
from etl.validate import run_all_validations

logger = get_logger(__name__)


def _parse_args(config: Config) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local basketball ETL")

    parser.add_argument(
        "--mode",
        choices=[
            "full",
            "incremental_by_season",
            "incremental_by_date_range",
            "subset",
            "dry_run",
        ],
        default=config.etl_mode,
        help="ETL mode (default: from ETL_MODE env or 'full')",
    )
    parser.add_argument(
        "--season",
        action="append",
        dest="seasons",
        help=(
            "Season end year for incremental_by_season "
            "(can be specified multiple times)"
        ),
    )
    parser.add_argument(
        "--start-date",
        dest="start_date",
        help="Start date (YYYY-MM-DD) for incremental_by_date_range",
    )
    parser.add_argument(
        "--end-date",
        dest="end_date",
        help="End date (YYYY-MM-DD) for incremental_by_date_range",
    )
    parser.add_argument(
        "--subset",
        dest="subset",
        help=(
            "Comma-separated subset of loaders to run "
            "(dimensions,player_seasons,team_seasons,games,boxscores,pbp,awards,inactive,validations)"
        ),
    )
    parser.add_argument(
        "--dry-run",
        dest="dry_run_flag",
        action="store_true",
        help="Alias for --mode=dry_run (no writes; run expectations/validations only)",
    )

    args = parser.parse_args()

    if args.dry_run_flag:
        args.mode = "dry_run"

    return args


def _derive_mode_params(args: argparse.Namespace) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if args.mode == "incremental_by_season" and args.seasons:
        params["seasons"] = [int(s) for s in args.seasons]
    if args.mode == "incremental_by_date_range":
        if args.start_date:
            params["start_date"] = args.start_date
        if args.end_date:
            params["end_date"] = args.end_date
    if args.mode == "subset" and args.subset:
        subsets = [s.strip() for s in args.subset.split(",") if s.strip()]
        params["subset"] = subsets
    return params


def _should_run(step: str, mode: str, subset: Optional[List[str]]) -> bool:
    if mode == "subset" and subset is not None:
        return step in subset
    # All other modes: default include; loaders handle mode-specific behavior.
    return True


def main() -> int:
    config = get_config()
    args = _parse_args(config)

    mode: str = args.mode
    mode_params: Dict[str, Any] = _derive_mode_params(args)
    subset_list: Optional[List[str]] = mode_params.get("subset")

    # Fallback: if ETL_MODE_PARAMS env is set and no CLI params, merge it.
    if not mode_params and config.etl_mode_params:
        try:
            env_params = json.loads(config.etl_mode_params)
            if isinstance(env_params, dict):
                mode_params = env_params
        except Exception:  # noqa: BLE001
            pass

    dry_run = mode == "dry_run"

    conn = get_connection(config)
    etl_run_id = 0
    expectations: Expectations = (
        load_expectations(config) if config.enable_expectations else None
    )  # type: ignore[assignment]

    try:
        log_structured(
            logger,
            logger.level,
            "Starting ETL",
            mode=mode,
            mode_params_json=json.dumps(mode_params, sort_keys=True)
            if mode_params
            else "{}",
            dry_run=dry_run,
        )

        # Start ETL run (best-effort).
        etl_run_id = start_etl_run(
            conn,
            job_name="full_etl",
            mode=mode,
            params=mode_params,
            expectations=expectations,
        )

        # Track input versions early (no-op if tables missing).
        track_all_csv_data_versions(
            conn,
            config,
            etl_run_id=etl_run_id,
        )
        conn.commit()

        step_issues: List[dict] = []

        # 1) Dimensions
        if _should_run("dimensions", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="dimensions",
                loader_module="etl.load_dimensions",
            )
            try:
                if not dry_run:
                    load_all_dimensions(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                    output_tables=["players", "teams", "seasons"],
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 2) Player seasons
        if _should_run("player_seasons", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="player_seasons",
                loader_module="etl.load_player_seasons",
            )
            try:
                if not dry_run:
                    load_all_player_seasons(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 3) Team seasons
        if _should_run("team_seasons", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="team_seasons",
                loader_module="etl.load_team_seasons",
            )
            try:
                if not dry_run:
                    load_all_team_seasons(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 4) Games + boxscore_team
        if _should_run("games", mode, subset_list) or _should_run(
            "boxscores", mode, subset_list
        ):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="games_and_boxscores",
                loader_module="etl.load_games_and_boxscores",
            )
            try:
                if not dry_run:
                    load_games_and_boxscores(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 5) PBP events
        if _should_run("pbp", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="pbp_events",
                loader_module="etl.load_pbp",
            )
            try:
                if not dry_run:
                    load_pbp_events(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 6) Awards + draft
        if _should_run("awards", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="awards_and_draft",
                loader_module="etl.load_awards_and_draft",
            )
            try:
                if not dry_run:
                    load_all_awards_and_draft(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 7) Inactive players
        if _should_run("inactive", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="inactive_players",
                loader_module="etl.load_inactive",
            )
            try:
                if not dry_run:
                    load_inactive_players(
                        config,
                        conn,
                        mode=mode,
                        mode_params=mode_params,
                        dry_run=dry_run,
                        etl_run_id=etl_run_id,
                        etl_run_step_id=step_id,
                    )
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # 8) Validations
        if _should_run("validations", mode, subset_list):
            step_id = start_etl_step(
                conn,
                etl_run_id,
                step_name="validations",
                loader_module="etl.validate",
            )
            try:
                # run_all_validations handles its own reporting;
                # pass etl_run_id when non-zero.
                run_all_validations(conn, etl_run_id=etl_run_id or None)
                finalize_etl_step(
                    conn,
                    step_id,
                    status="succeeded",
                )
                conn.commit()
            except Exception as exc:  # noqa: BLE001
                finalize_etl_step(
                    conn,
                    step_id,
                    status="failed",
                    error_message=str(exc),
                )
                conn.commit()
                raise

        # Optional: schema drift summary report when expectations enabled
        if expectations and expectations.csv_sources:
            try:
                # Detailed per-loader checks are done inside loaders;
                # here we only ensure report dir.
                write_schema_drift_report(etl_run_id or None, issues=step_issues)
            except Exception:  # noqa: BLE001
                pass

        finalize_etl_run(conn, etl_run_id, status="succeeded")
        conn.commit()

        write_etl_run_report(
            etl_run_id,
            {
                "mode": mode,
                "mode_params": mode_params,
                "dry_run": dry_run,
            },
        )

        log_structured(logger, logger.level, "ETL completed successfully")
        return 0

    except Exception as exc:  # noqa: BLE001
        logger.error("ETL failed: %s", exc)
        traceback.print_exc()

        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass

        try:
            finalize_etl_run(conn, etl_run_id, status="failed", message=str(exc))
            conn.commit()
        except Exception:  # noqa: BLE001
            # If even this fails, nothing more we can do.
            pass

        return 1

    finally:
        try:
            release_connection(conn)
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    sys.exit(main())

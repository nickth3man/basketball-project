"""
CLI entrypoint to run the full Phase 2 ETL against the Phase 1 canonical schema.

Execution order:
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
"""

from __future__ import annotations

import sys
import traceback

from etl.config import get_config
from etl.db import get_connection, release_connection
from etl.load_awards_and_draft import load_all_awards_and_draft
from etl.load_dimensions import load_all_dimensions
from etl.load_games_and_boxscores import load_games_and_boxscores
from etl.load_inactive import load_inactive_players
from etl.load_metadata import (
    finalize_etl_run,
    start_etl_run,
    track_all_csv_data_versions,
)
from etl.load_player_seasons import load_all_player_seasons
from etl.load_team_seasons import load_all_team_seasons
from etl.load_pbp import load_pbp_events
from etl.logging_utils import get_logger, log_structured
from etl.validate import run_all_validations


logger = get_logger(__name__)


def main() -> int:
    config = get_config()
    conn = get_connection(config)
    etl_run_id = 0

    try:
        log_structured(logger, logger.level, "Starting full ETL")
        etl_run_id = start_etl_run(conn, job_name="full_etl")

        # Track input versions early
        track_all_csv_data_versions(conn, config, etl_run_id)
        conn.commit()

        # 1) Dimensions
        log_structured(logger, logger.level, "Loading dimensions")
        load_all_dimensions(config, conn)
        conn.commit()

        # 2) Player seasons
        log_structured(logger, logger.level, "Loading player seasons")
        load_all_player_seasons(config, conn)
        conn.commit()

        # 3) Team seasons
        log_structured(logger, logger.level, "Loading team seasons")
        load_all_team_seasons(config, conn)
        conn.commit()

        # 4) Games + boxscore_team
        log_structured(logger, logger.level, "Loading games and boxscores")
        load_games_and_boxscores(config, conn)
        conn.commit()

        # 5) PBP events
        log_structured(logger, logger.level, "Loading play-by-play events")
        load_pbp_events(config, conn)
        conn.commit()

        # 6) Awards + draft
        log_structured(logger, logger.level, "Loading awards and draft data")
        load_all_awards_and_draft(config, conn)
        conn.commit()

        # 7) Inactive players
        log_structured(logger, logger.level, "Loading inactive players")
        load_inactive_players(config, conn)
        conn.commit()

        # 8) Validations
        log_structured(logger, logger.level, "Running validations")
        run_all_validations(conn)
        conn.commit()

        finalize_etl_run(conn, etl_run_id, status="succeeded")
        conn.commit()
        log_structured(logger, logger.level, "Full ETL completed successfully")
        return 0

    except Exception as exc:  # noqa: BLE001
        logger.error("Full ETL failed: %s", exc)
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
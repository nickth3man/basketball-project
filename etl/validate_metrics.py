from __future__ import annotations

"""
Lightweight metrics sanity validation harness.

Usage (non-interactive):

    python -m etl.validate_metrics

Behavior:

- Uses the same configuration mechanism as other ETL modules.
- Connects via etl.db.get_connection / etl.db.release_connection.
- Runs cheap range / plausibility checks over advanced metric views.
- Logs out-of-bounds rows (capped) and exits non-zero on extreme anomalies.
- Does not mutate data or depend on API/front-end code.

These checks are intentionally broad and permissive. They are guards
against obviously broken ETL/math, not authoritative analytics.
"""

from typing import Tuple

from psycopg import Connection

from .config import get_config
from .db import get_connection, release_connection
from .logging_utils import get_logger, log_structured

logger = get_logger(__name__)


# -----------------------
# Helper query primitives
# -----------------------


def _sample_out_of_range(
    conn: Connection,
    table: str,
    column: str,
    min_value: float | None,
    max_value: float | None,
    limit: int = 20,
) -> list[Tuple]:
    """
    Return up to `limit` rows where value is outside [min_value, max_value].

    If min_value or max_value is None, only apply the bound that is not None.
    """
    where_clauses: list[str] = ["{col} IS NOT NULL".format(col=column)]
    params: list[float] = []

    if min_value is not None:
        where_clauses.append(f"{column} < %s")
        params.append(float(min_value))
    if max_value is not None:
        where_clauses.append(f"{column} > %s")
        params.append(float(max_value))

    if len(where_clauses) == 1:
        # No bounds supplied; nothing to check.
        return []

    sql = f"""
        SELECT *
        FROM {table}
        WHERE {" OR ".join(where_clauses[1:])}
        LIMIT {int(limit)}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    if rows:
        log_structured(
            logger,
            logger.level,
            "Metrics sanity: found out-of-range values",
            table=table,
            column=column,
            count=len(rows),
        )
    else:
        log_structured(
            logger,
            logger.level,
            "Metrics sanity: no out-of-range values",
            table=table,
            column=column,
        )

    return rows


def _check_metric_range(
    conn: Connection,
    table: str,
    column: str,
    min_value: float | None,
    max_value: float | None,
    hard_min: float | None,
    hard_max: float | None,
    label: str,
    anomalies: list[str],
) -> None:
    """
    Run a soft and hard bound check for a metric column.

    - If values fall outside [min_value, max_value], they are logged as warnings.
    - If values fall outside [hard_min, hard_max], they are considered fatal.
    """
    samples = _sample_out_of_range(conn, table, column, min_value, max_value)
    if samples:
        logger.warning(
            "Metrics sanity warning for %s.%s (%s): %d rows outside soft bounds",
            table,
            column,
            label,
            len(samples),
        )

    if hard_min is None and hard_max is None:
        return

    hard_where: list[str] = [f"{column} IS NOT NULL"]
    params: list[float] = []

    if hard_min is not None:
        hard_where.append(f"{column} < %s")
        params.append(float(hard_min))
    if hard_max is not None:
        hard_where.append(f"{column} > %s")
        params.append(float(hard_max))

    sql = f"""
        SELECT COUNT(*)
        FROM {table}
        WHERE {" OR ".join(hard_where[1:])}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        cnt = int(row[0]) if row and row[0] is not None else 0

    if cnt > 0:
        msg = (
            f"Extreme anomalies for {label} in {table}.{column}: "
            f"{cnt} rows outside hard bounds"
        )
        logger.error(msg)
        anomalies.append(msg)
    else:
        log_structured(
            logger,
            logger.level,
            "Metrics sanity: within hard bounds",
            table=table,
            column=column,
            label=label,
        )


# -------------
# Checks
# -------------


def _check_player_advanced_metrics(conn: Connection, anomalies: list[str]) -> None:
    table = "vw_player_season_advanced"

    # True Shooting Percentage (ts_pct): [0, 1.5] soft, [0, 3] hard
    _check_metric_range(
        conn,
        table,
        "ts_pct",
        0.0,
        1.5,
        0.0,
        3.0,
        "True Shooting %",
        anomalies,
    )

    # eFG%: [0, 1.5] soft, [0, 3] hard
    _check_metric_range(
        conn,
        table,
        "efg_pct",
        0.0,
        1.5,
        0.0,
        3.0,
        "Effective FG%",
        anomalies,
    )

    # WS/48: [-1, 1.5] soft, [-5, 5] hard
    _check_metric_range(
        conn,
        table,
        "ws_per_48",
        -1.0,
        1.5,
        -5.0,
        5.0,
        "WS/48",
        anomalies,
    )

    # BPM, OBPM, DBPM: [-20, 20] soft, [-40, 40] hard
    for col, label in [
        ("bpm", "BPM"),
        ("obpm", "OBPM"),
        ("dbpm", "DBPM"),
    ]:
        _check_metric_range(
            conn,
            table,
            col,
            -20.0,
            20.0,
            -40.0,
            40.0,
            label,
            anomalies,
        )


def _check_team_advanced_metrics(conn: Connection, anomalies: list[str]) -> None:
    table = "vw_team_season_advanced"

    # Offensive rating (ortg): soft [50, 150], hard [0, 300]
    _check_metric_range(
        conn,
        table,
        "ortg",
        50.0,
        150.0,
        0.0,
        300.0,
        "Team ORtg",
        anomalies,
    )

    # Defensive rating (drtg): soft [50, 150], hard [0, 300]
    _check_metric_range(
        conn,
        table,
        "drtg",
        50.0,
        150.0,
        0.0,
        300.0,
        "Team DRtg",
        anomalies,
    )

    # Net rating (nrtg): soft [-50, 50], hard [-200, 200]
    _check_metric_range(
        conn,
        table,
        "nrtg",
        -50.0,
        50.0,
        -200.0,
        200.0,
        "Team NRtg",
        anomalies,
    )


def run_all_metric_checks(conn: Connection) -> list[str]:
    """
    Run all metrics sanity checks.

    Returns:
        anomalies: list of fatal anomaly descriptions.
    """
    anomalies: list[str] = []

    _check_player_advanced_metrics(conn, anomalies)
    _check_team_advanced_metrics(conn, anomalies)

    return anomalies


# -------------
# Entrypoint
# -------------


def main() -> None:
    """
    Run metrics sanity validations.

    Exit codes:
    - 0: all checks within hard bounds (soft anomalies logged as warnings).
    - 1: extreme anomalies detected outside hard bounds.
    - 2: unexpected runtime error (e.g., connection issues).
    """
    config = get_config()
    conn: Connection | None = None
    try:
        conn = get_connection(config)

        anomalies = run_all_metric_checks(conn)

        if anomalies:
            for msg in anomalies:
                logger.error("METRICS ANOMALY: %s", msg)
            log_structured(
                logger,
                logger.level,
                "Metrics validation failed",
                anomaly_count=len(anomalies),
            )
            raise SystemExit(1)

        log_structured(
            logger,
            logger.level,
            "Metrics validation passed",
            anomaly_count=0,
        )
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error during metrics validation: %s", exc)
        raise SystemExit(2)
    finally:
        if conn is not None:
            release_connection(conn)


if __name__ == "__main__":
    main()

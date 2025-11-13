import json
import os
import time
from typing import Any, Dict, Iterable, List, Optional

import polars as pl
from psycopg import Connection

from .expectations_loader import (
    Expectations,
    get_csv_expectation,
    get_table_expectation,
)
from .logging_utils import (
    get_logger,
    log_etl_event,
    log_schema_drift_issue,
)

logger = get_logger(__name__)


def _safe_mkdir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:  # noqa: BLE001
        # Do not break ETL on filesystem issues.
        logger.warning(
            "Failed to create directory for schema drift reports", extra={"path": path}
        )


def _normalize_polars_type(dt: pl.DataType) -> str:
    """
    Map Polars dtypes to coarse-grained logical types for comparison.
    """
    if dt in (
        pl.Int8,
        pl.Int16,
        pl.Int32,
        pl.Int64,
        pl.UInt8,
        pl.UInt16,
        pl.UInt32,
        pl.UInt64,
    ):
        return "int"
    if dt in (pl.Float32, pl.Float64):
        return "float"
    if dt == pl.Boolean:
        return "bool"
    if dt in (pl.Utf8, pl.Categorical, pl.Enum):
        return "text"
    if dt in (pl.Date,):
        return "date"
    if dt in (pl.Datetime,):
        return "timestamp"
    return "other"


def _severity(
    expectations: Expectations, policy_key: str, default: str = "warn"
) -> str:
    val = expectations.defaults.get(policy_key, default)
    return str(val) if isinstance(val, str) and val else default


def _issue(
    etl_run_id: Optional[int],
    source_type: str,
    source_id: str,
    issue_type: str,
    severity: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "etl_run_id": etl_run_id,
        "source_type": source_type,
        "source_id": source_id,
        "issue_type": issue_type,
        "severity": severity,
        "details": details,
    }


# -----------------------------
# CSV source schema drift
# -----------------------------


def check_csv_source_schema(
    source_id: str,
    file_path: str,
    df: pl.DataFrame,
    expectations: Expectations,
    etl_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Compare a CSV DataFrame's columns/types against expectations.

    If expectations for this source_id are missing, returns [].
    """
    exp = get_csv_expectation(expectations, source_id)
    if not exp:
        return []

    issues: List[Dict[str, Any]] = []

    schema_cfg = exp.get("schema") or {}
    expected_cols_cfg: Iterable[Dict[str, Any]] = schema_cfg.get("columns") or []
    expected_pk: Iterable[str] = schema_cfg.get("primary_key") or []

    expected_cols = {c["name"]: c for c in expected_cols_cfg if "name" in c}
    actual_cols = list(df.columns)

    # Missing / extra columns
    for name, meta in expected_cols.items():
        if name not in actual_cols:
            sev = exp.get("drift_policy", {}).get(
                "on_missing_column",
                _severity(expectations, "on_missing_column"),
            )
            issue = _issue(
                etl_run_id,
                "csv",
                source_id,
                "missing_column",
                sev,
                {"column": name, "file_path": file_path},
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "csv",
                source_id,
                "missing_column",
                sev,
                issue["details"],
            )

    for name in actual_cols:
        if name not in expected_cols:
            sev = exp.get("drift_policy", {}).get(
                "on_extra_column",
                _severity(expectations, "on_extra_column"),
            )
            issue = _issue(
                etl_run_id,
                "csv",
                source_id,
                "extra_column",
                sev,
                {"column": name, "file_path": file_path},
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "csv",
                source_id,
                "extra_column",
                sev,
                issue["details"],
            )

    # Type mismatches (best-effort)
    actual_schema = {
        name: _normalize_polars_type(dtype) for name, dtype in df.schema.items()
    }
    for name, meta in expected_cols.items():
        if name not in actual_schema:
            continue
        expected_type = str(meta.get("type") or "").lower()
        if not expected_type:
            continue
        actual_type = actual_schema[name]
        if expected_type != actual_type:
            sev = exp.get("drift_policy", {}).get(
                "on_type_mismatch",
                _severity(expectations, "on_type_mismatch"),
            )
            issue = _issue(
                etl_run_id,
                "csv",
                source_id,
                "type_mismatch",
                sev,
                {
                    "column": name,
                    "expected_type": expected_type,
                    "actual_type": actual_type,
                    "file_path": file_path,
                },
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "csv",
                source_id,
                "type_mismatch",
                sev,
                issue["details"],
            )

    # Minimal PK uniqueness check (if configured)
    if expected_pk:
        try:
            null_counts = df.select(
                [
                    pl.col(col).is_null().sum().alias(col)
                    for col in expected_pk
                    if col in df.columns
                ]
            ).to_dict(as_series=False)
            has_nulls = any(
                (null_counts.get(col) or [0])[0] > 0
                for col in expected_pk
                if col in null_counts
            )
            if has_nulls:
                sev = exp.get("drift_policy", {}).get(
                    "on_null_in_required",
                    _severity(expectations, "on_null_in_required"),
                )
                issue = _issue(
                    etl_run_id,
                    "csv",
                    source_id,
                    "null_in_primary_key",
                    sev,
                    {"primary_key": list(expected_pk), "file_path": file_path},
                )
                issues.append(issue)
                log_schema_drift_issue(
                    logger,
                    etl_run_id,
                    "csv",
                    source_id,
                    "null_in_primary_key",
                    sev,
                    issue["details"],
                )

            # Uniqueness
            if all(col in df.columns for col in expected_pk):
                total = df.height
                if total > 0:
                    unique = df.select(pl.all().is_duplicated().any()).item()
                    if bool(unique):
                        sev = exp.get("drift_policy", {}).get(
                            "on_primary_key_violation",
                            _severity(expectations, "on_primary_key_violation"),
                        )
                        issue = _issue(
                            etl_run_id,
                            "csv",
                            source_id,
                            "primary_key_violation",
                            sev,
                            {
                                "primary_key": list(expected_pk),
                                "file_path": file_path,
                            },
                        )
                        issues.append(issue)
                        log_schema_drift_issue(
                            logger,
                            etl_run_id,
                            "csv",
                            source_id,
                            "primary_key_violation",
                            sev,
                            issue["details"],
                        )
        except Exception:  # noqa: BLE001
            # Ignore PK check failures; logging only.
            pass

    # Row count zero check
    if df.height == 0:
        sev = exp.get("drift_policy", {}).get(
            "on_row_count_zero",
            _severity(expectations, "on_row_count_zero"),
        )
        issue = _issue(
            etl_run_id,
            "csv",
            source_id,
            "row_count_zero",
            sev,
            {"file_path": file_path},
        )
        issues.append(issue)
        log_schema_drift_issue(
            logger,
            etl_run_id,
            "csv",
            source_id,
            "row_count_zero",
            sev,
            issue["details"],
        )

    return issues


# -----------------------------
# Table schema drift
# -----------------------------


def _introspect_table_schema(conn: Connection, table_name: str) -> List[Dict[str, Any]]:
    sql = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        ORDER BY ordinal_position
    """
    with conn.cursor() as cur:
        cur.execute(sql, (table_name,))
        rows = cur.fetchall()

    return [
        {
            "name": str(name),
            "type": str(dtype),
            "nullable": (nullable == "YES"),
        }
        for (name, dtype, nullable) in rows
    ]


def check_table_schema(
    conn: Connection,
    table_name: str,
    expectations: Expectations,
    etl_run_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Compare actual DB table schema vs expectations.

    If expectations for this table are missing or the table does not exist, returns [].
    """
    exp = get_table_expectation(expectations, table_name)
    if not exp:
        return []

    # Introspect; if no columns, assume table missing and skip.
    try:
        actual_cols = _introspect_table_schema(conn, table_name)
    except Exception:  # noqa: BLE001
        return []

    if not actual_cols:
        return []

    issues: List[Dict[str, Any]] = []

    expected_cols_cfg: Iterable[Dict[str, Any]] = exp.get("expected_columns") or []
    _expected_pk: Iterable[str] = exp.get("primary_key") or []  # noqa: F841

    expected_cols = {c["name"]: c for c in expected_cols_cfg if "name" in c}
    actual_cols_map = {c["name"]: c for c in actual_cols}

    # Missing / extra columns
    for name, meta in expected_cols.items():
        if name not in actual_cols_map:
            sev = _severity(expectations, "on_missing_column")
            issue = _issue(
                etl_run_id,
                "table",
                table_name,
                "missing_column",
                sev,
                {"column": name},
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "table",
                table_name,
                "missing_column",
                sev,
                issue["details"],
            )

    for name, meta in actual_cols_map.items():
        if name not in expected_cols:
            sev = _severity(expectations, "on_extra_column")
            issue = _issue(
                etl_run_id,
                "table",
                table_name,
                "extra_column",
                sev,
                {"column": name},
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "table",
                table_name,
                "extra_column",
                sev,
                issue["details"],
            )

    # Type and nullability checks (coarse)
    for name, exp_meta in expected_cols.items():
        if name not in actual_cols_map:
            continue
        actual = actual_cols_map[name]
        exp_type = str(exp_meta.get("type") or "").lower()
        act_type = str(actual.get("type") or "").lower()
        if exp_type and (exp_type not in act_type):
            sev = _severity(expectations, "on_type_mismatch")
            issue = _issue(
                etl_run_id,
                "table",
                table_name,
                "type_mismatch",
                sev,
                {
                    "column": name,
                    "expected_type": exp_type,
                    "actual_type": act_type,
                },
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "table",
                table_name,
                "type_mismatch",
                sev,
                issue["details"],
            )

        exp_nullable = exp_meta.get("nullable")
        if exp_nullable is not None and bool(exp_nullable) != bool(
            actual.get("nullable")
        ):
            sev = _severity(expectations, "on_type_mismatch")
            issue = _issue(
                etl_run_id,
                "table",
                table_name,
                "nullability_mismatch",
                sev,
                {
                    "column": name,
                    "expected_nullable": bool(exp_nullable),
                    "actual_nullable": bool(actual.get("nullable")),
                },
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "table",
                table_name,
                "nullability_mismatch",
                sev,
                issue["details"],
            )

    # Quality expectation: min_rows
    quality = exp.get("quality_expectations") or {}
    min_rows = quality.get("min_rows")
    if isinstance(min_rows, int) and min_rows > 0:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                row = cur.fetchone()
                count = int(row[0]) if row and row[0] is not None else 0
        except Exception:  # noqa: BLE001
            count = None

        if count is not None and count < min_rows:
            sev = _severity(expectations, "on_row_count_zero")
            issue = _issue(
                etl_run_id,
                "table",
                table_name,
                "row_count_below_min",
                sev,
                {"min_rows": min_rows, "actual_rows": count},
            )
            issues.append(issue)
            log_schema_drift_issue(
                logger,
                etl_run_id,
                "table",
                table_name,
                "row_count_below_min",
                sev,
                issue["details"],
            )

    return issues


# -----------------------------
# Report writer
# -----------------------------


def write_schema_drift_report(
    etl_run_id: Optional[int],
    issues: List[Dict[str, Any]],
) -> Optional[str]:
    """
    Write a schema drift report if any issues exist.

    Returns the report file path or None if nothing was written.
    """
    if not issues:
        return None

    reports_dir = os.path.join("var", "reports", "etl")
    _safe_mkdir(reports_dir)

    if etl_run_id:
        suffix = str(etl_run_id)
    else:
        suffix = str(int(time.time()))

    path = os.path.join(reports_dir, f"schema_drift_{suffix}.json")

    payload = {
        "etl_run_id": etl_run_id,
        "issue_count": len(issues),
        "issues": issues,
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        log_etl_event(
            logger,
            "schema_drift_report_written",
            etl_run_id=etl_run_id,
            path=path,
            issue_count=len(issues),
        )
        return path
    except Exception:  # noqa: BLE001
        logger.warning("Failed to write schema drift report", extra={"path": path})
        return None

"""
Metadata loaders for ETL runs, steps, issues, and data_versions.

Relies solely on canonical Phase 1+ schema objects when present:

- etl_runs
- etl_run_steps
- etl_run_issues
- data_versions

Responsibilities:
- Open / finalize etl_runs records around ETL orchestrations.
- Track CSV data_versions by checksum for known logical sources.
- Record step-level metadata (etl_run_steps) for individual loaders.
- Record issues (etl_run_issues) for schema drift / validations, etc.
- Write simple JSON reports to var/reports/etl when possible.

All helpers are best-effort and MUST NOT break ETL if metadata tables
or directories are missing. Callers should treat missing IDs (0 / None)
as "metadata disabled".
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from psycopg import Connection

from .config import Config
from .expectations_loader import Expectations
from .logging_utils import get_logger, log_etl_event, log_structured
from .paths import all_known_csvs, resolve_csv_path

logger = get_logger(__name__)


# -----------------------
# Internal helpers
# -----------------------


def _table_exists(conn: Connection, table_name: str) -> bool:
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = %s
        LIMIT 1
    """
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            return cur.fetchone() is not None
    except Exception:  # noqa: BLE001
        return False


def _file_checksum(path: str, algo: str = "sha256") -> Optional[str]:
    if not os.path.exists(path):
        return None

    algo = (algo or "sha256").lower()
    try:
        digest = hashlib.new(algo)
    except Exception:  # noqa: BLE001
        digest = hashlib.sha256()

    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_existing_data_versions(conn: Connection) -> Dict[str, str]:
    if not _table_exists(conn, "data_versions"):
        return {}

    sql = "SELECT source_name, checksum FROM data_versions"
    with conn.cursor() as cur:
        cur.execute(sql)
        return {row[0]: row[1] for row in cur.fetchall()}


def _upsert_data_version(
    conn: Connection,
    source_name: str,
    checksum: str,
    etl_run_id: int,
) -> None:
    if not _table_exists(conn, "data_versions"):
        return

    sql = """
        INSERT INTO data_versions (source_name, checksum, last_loaded_etl_run_id, updated_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (source_name)
        DO UPDATE SET
          checksum = EXCLUDED.checksum,
          last_loaded_etl_run_id = EXCLUDED.last_loaded_etl_run_id,
          updated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql, (source_name, checksum, etl_run_id))


def _safe_mkdir(path: str) -> None:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception:  # noqa: BLE001
        # Logging only; never break ETL.
        logger.warning("Failed to create directory", extra={"path": path})


# -----------------------
# ETL run lifecycle
# -----------------------


def start_etl_run(
    conn: Connection,
    job_name: str = "full_etl",
    mode: str = "full",
    params: Optional[Dict[str, Any]] = None,
    expectations: Optional[Expectations] = None,
) -> int:
    """
    Insert an etl_runs row and return its id.

    If etl_runs table does not exist (e.g., schema not applied), this is a no-op
    and returns 0 so callers can still proceed.
    """
    if not _table_exists(conn, "etl_runs"):
        logger.warning("etl_runs table missing; skipping ETL run tracking")
        return 0

    started_at = datetime.now(timezone.utc)
    params_json = params or {}
    expectations_version = expectations.version if expectations is not None else None

    sql = """
        INSERT INTO etl_runs (job_name, mode, params, status, started_at, created_by, expectations_version)
        VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)
        RETURNING etl_run_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                job_name,
                mode,
                json.dumps(params_json),
                "running",
                started_at,
                "local",
                expectations_version,
            ),
        )
        etl_run_id = int(cur.fetchone()[0])

    log_structured(
        logger,
        logger.level,
        "Started etl_run",
        etl_run_id=etl_run_id,
        job_name=job_name,
        mode=mode,
    )
    return etl_run_id


def finalize_etl_run(
    conn: Connection,
    etl_run_id: int,
    status: str,
    message: Optional[str] = None,
) -> None:
    """
    Update etl_runs status. Safe no-op if etl_run_id == 0 or table missing.
    """
    if etl_run_id == 0 or not _table_exists(conn, "etl_runs"):
        return

    finished_at = datetime.now(timezone.utc)
    sql = """
        UPDATE etl_runs
        SET status = %s,
            finished_at = %s,
            message = COALESCE(%s, message)
        WHERE etl_run_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (status, finished_at, message, etl_run_id))

    log_structured(
        logger,
        logger.level,
        "Finalized etl_run",
        etl_run_id=etl_run_id,
        status=status,
    )


# -----------------------
# Step-level helpers
# -----------------------


def start_etl_step(
    conn: Connection,
    etl_run_id: int,
    step_name: str,
    loader_module: str,
    input_files: Optional[Iterable[str]] = None,
) -> Optional[int]:
    """
    Open an etl_run_steps record.

    Returns etl_run_step_id or None if metadata is unavailable.
    """
    if etl_run_id == 0 or not _table_exists(conn, "etl_run_steps"):
        return None

    started_at = datetime.now(timezone.utc)
    files_json = list(input_files) if input_files else None

    sql = """
        INSERT INTO etl_run_steps (
            etl_run_id,
            step_name,
            loader_module,
            status,
            started_at,
            input_files
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb)
        RETURNING etl_run_step_id
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                etl_run_id,
                step_name,
                loader_module,
                "running",
                started_at,
                json.dumps(files_json) if files_json is not None else None,
            ),
        )
        step_id = int(cur.fetchone()[0])

    log_etl_event(
        logger,
        "etl_run_step_started",
        etl_run_id=etl_run_id,
        etl_run_step_id=step_id,
        step_name=step_name,
        loader_module=loader_module,
    )
    return step_id


def finalize_etl_step(
    conn: Connection,
    etl_run_step_id: Optional[int],
    status: str,
    rows_inserted: Optional[int] = None,
    rows_updated: Optional[int] = None,
    rows_deleted: Optional[int] = None,
    output_tables: Optional[Iterable[str]] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Finalize an etl_run_steps record.

    Safe no-op when step_id is None or table missing.
    """
    if etl_run_step_id is None or not _table_exists(conn, "etl_run_steps"):
        return

    finished_at = datetime.now(timezone.utc)
    tables_json = list(output_tables) if output_tables else None

    sql = """
        UPDATE etl_run_steps
        SET status = %s,
            finished_at = %s,
            rows_inserted = COALESCE(%s, rows_inserted),
            rows_updated = COALESCE(%s, rows_updated),
            rows_deleted = COALESCE(%s, rows_deleted),
            output_tables = COALESCE(%s::jsonb, output_tables),
            error_message = COALESCE(%s, error_message)
        WHERE etl_run_step_id = %s
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                status,
                finished_at,
                rows_inserted,
                rows_updated,
                rows_deleted,
                json.dumps(tables_json) if tables_json is not None else None,
                error_message,
                etl_run_step_id,
            ),
        )

    log_etl_event(
        logger,
        "etl_run_step_finalized",
        etl_run_step_id=etl_run_step_id,
        status=status,
    )


# -----------------------
# Issue recording
# -----------------------


def record_issue(
    conn: Connection,
    etl_run_id: int,
    step_name: Optional[str],
    source_type: str,
    source_id: str,
    issue_type: str,
    severity: str,
    details: Dict[str, Any],
) -> None:
    """
    Insert an issue row into etl_run_issues.

    Safe no-op if table missing or etl_run_id == 0.
    """
    if etl_run_id == 0 or not _table_exists(conn, "etl_run_issues"):
        return

    sql = """
        INSERT INTO etl_run_issues (
            etl_run_id,
            step_name,
            source_type,
            source_id,
            issue_type,
            severity,
            details
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    etl_run_id,
                    step_name,
                    source_type,
                    source_id,
                    issue_type,
                    severity,
                    json.dumps(details),
                ),
            )
    except Exception as exc:  # noqa: BLE001
        # Log but do not propagate.
        log_structured(
            logger,
            logger.level,
            "Failed to record etl_run_issue",
            error=str(exc),
        )


# -----------------------
# Data versions
# -----------------------


def track_all_csv_data_versions(
    conn: Connection,
    config: Config,
    etl_run_id: int,
    hash_algorithm: str = "sha256",
) -> None:
    """
    For each known CSV:

    - If file exists, compute checksum and upsert into data_versions.
    - If missing, log a warning and skip.

    Safe no-op when data_versions table is absent.
    """
    existing = _load_existing_data_versions(conn)
    mapping = all_known_csvs()

    for logical_name, rel_path in mapping.items():
        full_path = resolve_csv_path(config, rel_path)
        checksum = _file_checksum(full_path, algo=hash_algorithm)
        if checksum is None:
            log_structured(
                logger,
                logger.level,
                "CSV file missing; skipping data_versions entry",
                logical_name=logical_name,
                path=full_path,
            )
            continue

        if existing.get(logical_name) == checksum:
            # Already up-to-date; nothing to do.
            continue

        _upsert_data_version(conn, logical_name, checksum, etl_run_id)

    log_structured(
        logger,
        logger.level,
        "Completed data_versions sync",
        etl_run_id=etl_run_id,
        tracked=len(mapping),
    )


# -----------------------
# On-disk run report
# -----------------------


def write_etl_run_report(etl_run_id: int, summary: Dict[str, Any]) -> Optional[str]:
    """
    Write a JSON summary of an ETL run to var/reports/etl.

    Safe no-op if directories cannot be created or write fails.
    """
    if etl_run_id <= 0:
        return None

    reports_dir = os.path.join("var", "reports", "etl")
    _safe_mkdir(reports_dir)

    path = os.path.join(reports_dir, f"etl_run_{etl_run_id}.json")
    payload = {
        "etl_run_id": etl_run_id,
        "summary": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
        log_etl_event(
            logger,
            "etl_run_report_written",
            etl_run_id=etl_run_id,
            path=path,
        )
        return path
    except Exception:  # noqa: BLE001
        logger.warning("Failed to write etl_run report", extra={"path": path})
        return None

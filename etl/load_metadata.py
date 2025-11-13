"""
Metadata loaders for ETL runs and data_versions.

Relies solely on the canonical Phase 1 schema objects:
- etl_runs
- data_versions

Responsibilities:
- Open a new etl_runs record at the start of an ETL.
- Compute checksums for known CSV files and upsert into data_versions.
- Mark etl_runs as succeeded/failed.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from typing import Dict, Optional

import polars as pl
from psycopg import Connection

from .config import Config
from .logging_utils import get_logger, log_structured
from .paths import all_known_csvs, resolve_csv_path

logger = get_logger(__name__)


def _table_exists(conn: Connection, table_name: str) -> bool:
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = %s
        LIMIT 1
    """
    with conn.cursor() as cur:
        cur.execute(sql, (table_name,))
        return cur.fetchone() is not None


def start_etl_run(conn: Connection, job_name: str = "full_etl") -> int:
    """
    Insert an etl_runs row and return its id.

    If etl_runs table does not exist (e.g., schema not applied), this is a no-op
    and returns 0 so callers can still proceed.
    """
    if not _table_exists(conn, "etl_runs"):
        logger.warning("etl_runs table missing; skipping ETL run tracking")
        return 0

    started_at = datetime.now(timezone.utc)
    sql = """
        INSERT INTO etl_runs (job_name, status, started_at)
        VALUES (%s, %s, %s)
        RETURNING etl_run_id
    """
    with conn.cursor() as cur:
        cur.execute(sql, (job_name, "running", started_at))
        etl_run_id = cur.fetchone()[0]
    log_structured(logger, logger.level, "Started etl_run", etl_run_id=etl_run_id)
    return int(etl_run_id)


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


def _file_checksum(path: str) -> Optional[str]:
    if not os.path.exists(path):
        return None

    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha.update(chunk)
    return sha.hexdigest()


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


def track_all_csv_data_versions(
    conn: Connection,
    config: Config,
    etl_run_id: int,
) -> None:
    """
    For each known CSV:
    - If file exists, compute checksum and upsert into data_versions.
    - If missing, log a warning and skip.
    """
    existing = _load_existing_data_versions(conn)
    mapping = all_known_csvs()

    for logical_name, rel_path in mapping.items():
        full_path = resolve_csv_path(config, rel_path)
        checksum = _file_checksum(full_path)
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
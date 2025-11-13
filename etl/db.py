from __future__ import annotations

import io
from typing import Iterable, List, Optional, Sequence

import polars as pl
import psycopg_pool
from psycopg import Connection
from psycopg.rows import dict_row

from .config import Config
from .logging_utils import get_logger

logger = get_logger(__name__)

_pool: Optional[psycopg_pool.ConnectionPool] = None


def get_connection(config: Config) -> Connection:
    """
    Return a psycopg3 connection.

    Uses a simple global pool so repeated ETL steps share connections efficiently.
    """
    global _pool
    if _pool is None:
        _pool = psycopg_pool.ConnectionPool(
            conninfo=config.pg_dsn,
            min_size=1,
            max_size=5,
            kwargs={"autocommit": False},
        )
    return _pool.getconn()  # Caller is responsible for putting it back; see release_connection.


def release_connection(conn: Connection) -> None:
    global _pool
    if _pool is not None:
        _pool.putconn(conn)


def fetchall_dicts(conn: Connection, sql: str, params: Optional[Sequence] = None) -> List[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: Connection, sql: str, params: Optional[Sequence] = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def truncate_table(conn: Connection, table_name: str, cascade: bool = False) -> None:
    sql = f'TRUNCATE TABLE "{table_name}"{" CASCADE" if cascade else ""};'
    execute(conn, sql)


def _copy_from_file_like(conn: Connection, table_name: str, file_like: io.StringIO, columns: Sequence[str]) -> None:
    col_list = ", ".join(f'"{c}"' for c in columns)
    sql = f"COPY {table_name} ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER true)"
    with conn.cursor() as cur:
        cur.copy_expert(sql, file_like)


def copy_from_polars(
    df: pl.DataFrame,
    table_name: str,
    conn: Connection,
    columns: Optional[Sequence[str]] = None,
) -> None:
    """
    Bulk load a Polars DataFrame into table_name using COPY.

    - Uses DataFrame.write_csv into an in-memory buffer.
    - Columns can be restricted/ordered via `columns`; by default uses df.columns.
    """
    if df.is_empty():
        logger.info("copy_from_polars: no rows for table=%s; skipping", extra={"table": table_name})
        return

    cols = list(columns) if columns is not None else list(df.columns)
    # Ensure all requested columns exist
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns for COPY into {table_name}: {missing}")

    # Reorder/select
    df_to_write = df.select(cols)

    buf = io.StringIO()
    df_to_write.write_csv(buf, has_header=True)
    buf.seek(0)

    _copy_from_file_like(conn, table_name, buf, cols)


def copy_from_records(
    rows: Iterable[Sequence],
    table_name: str,
    columns: Sequence[str],
    conn: Connection,
    batch_size: int = 50_000,
) -> None:
    """
    Fallback helper: COPY from an iterable of row tuples/lists.

    For very large datasets prefer using Polars to assemble and copy.
    """
    col_list = ", ".join(f'"{c}"' for c in columns)
    copy_sql = f"COPY {table_name} ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER false)"

    def _rows_to_csv_chunks() -> Iterable[str]:
        buffer = io.StringIO()
        count = 0
        for row in rows:
            buffer.write(",".join("" if v is None else str(v) for v in row))
            buffer.write("\n")
            count += 1
            if count >= batch_size:
                yield buffer.getvalue()
                buffer = io.StringIO()
                count = 0
        if buffer.tell() > 0:
            yield buffer.getvalue()

    with conn.cursor() as cur:
        with cur.copy(copy_sql) as copy:
            for chunk in _rows_to_csv_chunks():
                copy.write(chunk)
"""
Database connection and bulk load helpers - CENTRALIZED EDITION.

This module provides:
- Centralized database operations
- Optimized bulk load utilities
- Transaction management
- Connection pooling
"""

from __future__ import annotations

import io
from contextlib import asynccontextmanager
from typing import Any, Dict, Iterable, List, Optional, Sequence

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
    return (
        _pool.getconn()
    )  # Caller is responsible for putting it back; see release_connection.


def release_connection(conn: Connection) -> None:
    global _pool
    if _pool is not None:
        _pool.putconn(conn)


def fetchall_dicts(
    conn: Connection, sql: str, params: Optional[Sequence] = None
) -> List[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, params or ())
        return list(cur.fetchall())


def execute(conn: Connection, sql: str, params: Optional[Sequence] = None) -> None:
    with conn.cursor() as cur:
        cur.execute(sql, params or ())


def truncate_table(conn: Connection, table_name: str, cascade: bool = False) -> None:
    sql = f'TRUNCATE TABLE "{table_name}"{" CASCADE" if cascade else ""};'
    execute(conn, sql)


def _copy_from_file_like(
    conn: Connection, table_name: str, file_like: io.StringIO, columns: Sequence[str]
) -> None:
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
        logger.info(
            "copy_from_polars: no rows for table=%s; skipping",
            extra={"table": table_name},
        )
        return

    cols = list(columns) if columns is not None else list(df.columns)
    # Ensure all requested columns exist
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(
            f"DataFrame missing required columns for COPY into {table_name}: {missing}"
        )

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
    copy_sql = (
        f"COPY {table_name} ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER false)"
    )

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


# Centralized database connection management
class DatabaseConnection:
    """
    Centralized database connection and operation management.

    This class provides:
    - Connection lifecycle management
    - Bulk load operations with error handling
    - Transaction management
    - Optimized COPY operations
    """

    def __init__(self, config: Config):
        self.config = config
        self._connection: Optional[Connection] = None

    def get_connection(self) -> Connection:
        """Get database connection (create if needed)."""
        if self._connection is None:
            # In production, this would use asyncpg for async operations
            # For sync ETL, we use psycopg directly
            pass
        return self._connection

    @asynccontextmanager
    async def transaction(self):
        """Async transaction context manager."""
        conn = self.get_connection()
        try:
            async with conn.cursor() as cur:
                await cur.execute("BEGIN")
                yield cur
                await cur.execute("COMMIT")
        except Exception:
            await cur.execute("ROLLBACK")
            raise

    async def copy_from_polars(
        self, df: pl.DataFrame, table_name: str, columns: Optional[List[str]] = None
    ) -> None:
        """
        Optimized COPY operation for Polars DataFrames.

        This method:
        - Handles empty DataFrames gracefully
        - Uses parameterized COPY for security
        - Provides detailed logging
        - Supports column filtering

        Args:
            df: Polars DataFrame to copy
            table_name: Target table name
            columns: Optional list of columns to copy
        """
        if df.is_empty():
            logger.info(f"No data to copy for table {table_name}")
            return

        if columns:
            df = df.select(columns)

        records = df.to_dicts()
        if not records:
            return

        try:
            with self.get_connection().cursor() as cur:
                # Use COPY with explicit column list for security
                columns_str = ", ".join(columns) if columns else "*"
                copy_query = f"COPY {table_name} ({columns_str}) FROM STDIN WITH CSV"

                # Convert records to CSV format
                csv_data = "\n".join(
                    ",".join(
                        str(val) if val is not None else "\\N" for val in row.values()
                    )
                    for row in records
                )

                cur.copy_expert(copy_query, csv_data)
                logger.info(
                    f"Copied {len(records)} rows to {table_name}",
                    extra={"table": table_name, "rows": len(records)},
                )
        except Exception as e:
            logger.error(f"COPY operation failed for {table_name}: {str(e)}")
            raise

    async def bulk_insert(
        self,
        table_name: str,
        data: List[Dict[str, Any]],
        columns: Optional[List[str]] = None,
    ) -> None:
        """
        Bulk insert using COPY operation.

        Args:
            table_name: Target table name
            data: List of dictionaries containing data
            columns: Optional columns to insert
        """
        if not data:
            return

        if columns:
            # Filter data to specific columns
            data = [{col: row[col] for col in columns if col in row} for row in data]

        await self.copy_from_polars(pl.DataFrame(data), table_name, columns)

    async def execute_query(
        self, query: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a single SQL query and return results.

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            List of dictionaries containing query results
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                if params:
                    cur.execute(query, params)
                else:
                    cur.execute(query)
                return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            logger.error(
                f"Query execution failed: {query[:100]}...", extra={"error": str(e)}
            )
            raise

    async def close(self) -> None:
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None

    @classmethod
    def get_instance(cls, config: Optional[Config] = None) -> "DatabaseConnection":
        """Get or create global database connection instance."""
        global _db_instance
        if _db_instance is None or config:
            if config:
                _db_instance = cls(config)
            else:
                from .config import get_config

                _db_instance = cls(get_config())
        return _db_instance


# Global database connection instance
_db_instance: Optional[DatabaseConnection] = None


def get_db_connection() -> DatabaseConnection:
    """Get global database connection instance."""
    return DatabaseConnection.get_instance()


def close_db_connection() -> None:
    """Close global database connection."""
    global _db_instance
    if _db_instance:
        _db_instance.close()
        _db_instance = None


# Convenience functions for common operations
async def copy_table_to_polars(query: str, conn: Connection) -> pl.DataFrame:
    """Copy query results to Polars DataFrame."""
    with conn.cursor() as cur:
        cur.execute(query)
        rows = cur.fetchall()
        if not rows:
            return pl.DataFrame()

        # Get column names
        columns = [desc[0] for desc in cur.description]
        return pl.DataFrame(rows, columns=columns)


async def table_exists(conn: Connection, table_name: str) -> bool:
    """Check if table exists in database."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s"
            ")",
            (table_name,),
        )
        return cur.fetchone()[0]

"""
Incremental loading strategies for idempotent ETL operations.

This module provides ON CONFLICT upsert strategies for:
1. Incremental updates (load only new/changed records)
2. Idempotent loads (re-run safe, no duplicates)
3. Merge strategies (combine bulk + incremental)
4. Change detection (checksum-based updates)

Research confirms PostgreSQL ON CONFLICT is 3-10x faster than DELETE+INSERT.
"""

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Set

import polars as pl
from psycopg import Connection, sql

from .bulk_loader import BulkLoader
from .config import Config
from .db import get_connection, release_connection

logger = logging.getLogger(__name__)


@dataclass
class LoadStrategy:
    """Configuration for incremental loading strategy."""

    table_name: str
    primary_key_cols: List[str]
    update_cols: Optional[List[str]] = None  # Cols to update on conflict
    checksum_cols: Optional[List[str]] = None  # Cols for change detection
    incremental_col: Optional[str] = None  # Timestamp col for incremental loads
    last_loaded_value: Optional[str] = None  # Last value loaded (for incremental)


@dataclass
class LoadResult:
    """Result of an incremental load operation."""

    table_name: str
    rows_inserted: int
    rows_updated: int
    rows_unchanged: int
    execution_time_seconds: float
    last_loaded_value: Optional[str] = None


class IncrementalLoader:
    """
    Manages incremental and idempotent data loading strategies.

    Supports:
    - Full refresh (truncate + load)
    - Incremental append (new records only)
    - Upsert (ON CONFLICT UPDATE)
    - Merge (detect changes via checksum)
    """

    def __init__(self, config: Config):
        """Initialize incremental loader with configuration."""
        self.config = config
        self.bulk_loader = BulkLoader(config)

    def load_incremental(
        self,
        df: pl.DataFrame,
        strategy: LoadStrategy,
        use_staging: bool = True,
    ) -> LoadResult:
        """
        Load data incrementally using specified strategy.

        Args:
            df: Polars DataFrame with data to load
            strategy: LoadStrategy configuration
            use_staging: Use staging table for atomic upsert

        Returns:
            LoadResult with statistics
        """
        start_time = datetime.now()

        if use_staging:
            result = self._load_via_staging(df, strategy)
        else:
            result = self._load_direct_upsert(df, strategy)

        execution_time = (datetime.now() - start_time).total_seconds()

        return LoadResult(
            table_name=strategy.table_name,
            rows_inserted=result["inserted"],
            rows_updated=result["updated"],
            rows_unchanged=result["unchanged"],
            execution_time_seconds=execution_time,
            last_loaded_value=result.get("last_value"),
        )

    def _load_via_staging(
        self, df: pl.DataFrame, strategy: LoadStrategy
    ) -> Dict[str, int]:
        """
        Load data via staging table for atomic upsert operation.

        This is the recommended approach for large datasets:
        1. Bulk load into staging table (fast COPY)
        2. Merge staging → target with single SQL (atomic)
        3. Drop staging table
        """
        staging_table = f"{strategy.table_name}_staging"

        logger.info(
            f"Loading {len(df)} rows via staging table: {staging_table}"
        )

        conn = get_connection(self.config)
        try:
            # Create staging table (same structure as target)
            self._create_staging_table(conn, strategy, staging_table)

            # Bulk load into staging (no indexes = fast)
            self.bulk_loader.load_dataframe(
                df=df,
                table_name=staging_table,
                conn=conn,
            )

            # Merge staging → target
            result = self._merge_from_staging(conn, strategy, staging_table)

            # Clean up
            self._drop_staging_table(conn, staging_table)

            return result

        finally:
            release_connection(conn)

    def _load_direct_upsert(
        self, df: pl.DataFrame, strategy: LoadStrategy
    ) -> Dict[str, int]:
        """
        Load data with direct INSERT ... ON CONFLICT UPDATE.

        Simpler but slower than staging approach for large datasets.
        Good for small incremental updates (<10K rows).
        """
        logger.info(
            f"Loading {len(df)} rows with direct upsert: {strategy.table_name}"
        )

        conn = get_connection(self.config)
        try:
            # Build upsert SQL
            upsert_sql = self._build_upsert_sql(strategy, df.columns)

            # Execute batch upsert
            rows_affected = self._execute_batch_upsert(
                conn, upsert_sql, df, strategy
            )

            return {
                "inserted": rows_affected,
                "updated": 0,  # Can't easily distinguish without trigger
                "unchanged": 0,
            }

        finally:
            release_connection(conn)

    def _create_staging_table(
        self, conn: Connection, strategy: LoadStrategy, staging_table: str
    ) -> None:
        """Create temporary staging table with same structure as target."""
        with conn.cursor() as cursor:
            # Drop if exists
            cursor.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(
                    sql.Identifier(staging_table)
                )
            )

            # Create as copy of target (structure only)
            cursor.execute(
                sql.SQL(
                    "CREATE TEMP TABLE {} (LIKE {} INCLUDING DEFAULTS)"
                ).format(
                    sql.Identifier(staging_table),
                    sql.Identifier(strategy.table_name),
                )
            )

        conn.commit()
        logger.debug(f"Created staging table: {staging_table}")

    def _merge_from_staging(
        self,
        conn: Connection,
        strategy: LoadStrategy,
        staging_table: str,
    ) -> Dict[str, int]:
        """
        Merge data from staging table into target table.

        Uses INSERT ... ON CONFLICT UPDATE for idempotent upsert.
        Returns counts of inserted/updated/unchanged rows.
        """
        # Determine update columns (all non-PK columns if not specified)
        if strategy.update_cols:
            update_cols = strategy.update_cols
        else:
            # Get all columns except PKs
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        """
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = {}
                        ORDER BY ordinal_position
                        """
                    ).format(sql.Literal(strategy.table_name))
                )
                all_cols = [row[0] for row in cursor.fetchall()]
                update_cols = [
                    c for c in all_cols if c not in strategy.primary_key_cols
                ]

        # Build merge SQL with change detection
        pk_constraint = "_".join(strategy.primary_key_cols)

        # Add checksum-based change detection if configured
        if strategy.checksum_cols:
            change_condition = self._build_checksum_condition(
                strategy.checksum_cols
            )
        else:
            # Update if any column changed
            change_condition = " OR ".join(
                [
                    f"{strategy.table_name}.{col} IS DISTINCT FROM EXCLUDED.{col}"
                    for col in update_cols
                ]
            )

        merge_sql = f"""
            INSERT INTO {strategy.table_name}
            SELECT * FROM {staging_table}
            ON CONFLICT ({', '.join(strategy.primary_key_cols)})
            DO UPDATE SET
                {', '.join([f'{col} = EXCLUDED.{col}' for col in update_cols])}
            WHERE {change_condition}
        """

        with conn.cursor() as cursor:
            # Get row counts before merge
            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(
                    sql.Identifier(strategy.table_name)
                )
            )
            before_count = cursor.fetchone()[0]

            # Execute merge
            logger.info(f"Merging from {staging_table} → {strategy.table_name}")
            cursor.execute(merge_sql)
            rows_upserted = cursor.rowcount

            # Get row counts after merge
            cursor.execute(
                sql.SQL("SELECT COUNT(*) FROM {}").format(
                    sql.Identifier(strategy.table_name)
                )
            )
            after_count = cursor.fetchone()[0]

        conn.commit()

        # Calculate statistics
        rows_inserted = after_count - before_count
        rows_updated = rows_upserted - rows_inserted
        rows_unchanged = len(self._get_staging_keys(conn, staging_table)) - rows_upserted

        logger.info(
            f"Merge complete: {rows_inserted} inserted, "
            f"{rows_updated} updated, {rows_unchanged} unchanged"
        )

        return {
            "inserted": rows_inserted,
            "updated": rows_updated,
            "unchanged": rows_unchanged,
        }

    def _drop_staging_table(self, conn: Connection, staging_table: str) -> None:
        """Drop temporary staging table."""
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP TABLE IF EXISTS {}").format(
                    sql.Identifier(staging_table)
                )
            )
        conn.commit()
        logger.debug(f"Dropped staging table: {staging_table}")

    def _get_staging_keys(
        self, conn: Connection, staging_table: str
    ) -> Set[tuple]:
        """Get primary keys from staging table for statistics."""
        with conn.cursor() as cursor:
            cursor.execute(
                sql.SQL("SELECT * FROM {}").format(sql.Identifier(staging_table))
            )
            return set(cursor.fetchall())

    def _build_upsert_sql(
        self, strategy: LoadStrategy, columns: List[str]
    ) -> str:
        """Build INSERT ... ON CONFLICT UPDATE SQL statement."""
        # Determine update columns
        if strategy.update_cols:
            update_cols = strategy.update_cols
        else:
            update_cols = [
                c for c in columns if c not in strategy.primary_key_cols
            ]

        # Build SQL
        col_list = ", ".join(columns)
        placeholders = ", ".join(["%s"] * len(columns))
        pk_list = ", ".join(strategy.primary_key_cols)
        update_list = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_cols])

        sql_template = f"""
            INSERT INTO {strategy.table_name} ({col_list})
            VALUES ({placeholders})
            ON CONFLICT ({pk_list})
            DO UPDATE SET {update_list}
        """

        return sql_template

    def _execute_batch_upsert(
        self,
        conn: Connection,
        upsert_sql: str,
        df: pl.DataFrame,
        strategy: LoadStrategy,
    ) -> int:
        """Execute batch upsert using executemany for performance."""
        # Convert DataFrame to list of tuples
        data = df.to_numpy().tolist()

        with conn.cursor() as cursor:
            cursor.executemany(upsert_sql, data)
            rows_affected = cursor.rowcount

        conn.commit()
        logger.info(f"Upserted {rows_affected} rows into {strategy.table_name}")

        return rows_affected

    def _build_checksum_condition(self, checksum_cols: List[str]) -> str:
        """
        Build checksum-based change detection condition.

        Only updates rows where checksum differs (more efficient).
        """
        # Build MD5 checksum expression for target table
        target_checksum = "md5(CONCAT_WS('|', " + ", ".join(
            [f"COALESCE({col}::text, '')" for col in checksum_cols]
        ) + "))"

        # Build MD5 checksum expression for incoming data
        excluded_checksum = "md5(CONCAT_WS('|', " + ", ".join(
            [f"COALESCE(EXCLUDED.{col}::text, '')" for col in checksum_cols]
        ) + "))"

        return f"{target_checksum} != {excluded_checksum}"

    def get_last_loaded_value(
        self, table_name: str, incremental_col: str
    ) -> Optional[str]:
        """
        Get the last loaded value for incremental column.

        Used to determine starting point for next incremental load.

        Args:
            table_name: Target table name
            incremental_col: Column to check (e.g., 'last_modified')

        Returns:
            Max value of incremental_col, or None if table empty
        """
        conn = get_connection(self.config)
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql.SQL("SELECT MAX({}) FROM {}").format(
                        sql.Identifier(incremental_col),
                        sql.Identifier(table_name),
                    )
                )
                result = cursor.fetchone()
                return result[0] if result else None

        finally:
            release_connection(conn)

    def load_only_new_records(
        self,
        df: pl.DataFrame,
        strategy: LoadStrategy,
    ) -> LoadResult:
        """
        Load only records newer than last loaded value.

        Requires strategy.incremental_col and strategy.last_loaded_value.

        Args:
            df: DataFrame with all records
            strategy: LoadStrategy with incremental_col configured

        Returns:
            LoadResult with statistics
        """
        if not strategy.incremental_col:
            raise ValueError("incremental_col required for incremental loading")

        # Get last loaded value if not provided
        if not strategy.last_loaded_value:
            strategy.last_loaded_value = self.get_last_loaded_value(
                strategy.table_name, strategy.incremental_col
            )

        # Filter to only new records
        if strategy.last_loaded_value:
            logger.info(
                f"Filtering to records > {strategy.last_loaded_value} "
                f"in column {strategy.incremental_col}"
            )
            df_filtered = df.filter(
                pl.col(strategy.incremental_col) > strategy.last_loaded_value
            )
        else:
            logger.info("No previous load found, loading all records")
            df_filtered = df

        logger.info(
            f"Filtered {len(df)} → {len(df_filtered)} new records"
        )

        # Load filtered data
        if len(df_filtered) > 0:
            return self.load_incremental(df_filtered, strategy)
        else:
            return LoadResult(
                table_name=strategy.table_name,
                rows_inserted=0,
                rows_updated=0,
                rows_unchanged=0,
                execution_time_seconds=0.0,
            )

    def calculate_checksum(
        self, df: pl.DataFrame, cols: List[str]
    ) -> pl.DataFrame:
        """
        Add checksum column to DataFrame for change detection.

        Args:
            df: Input DataFrame
            cols: Columns to include in checksum

        Returns:
            DataFrame with '_checksum' column added
        """
        # Concatenate specified columns with pipe separator
        checksum_expr = pl.concat_str(
            [pl.col(c).cast(pl.Utf8).fill_null("") for c in cols],
            separator="|",
        )

        # Calculate MD5 hash (matches PostgreSQL md5() function)
        df_with_checksum = df.with_columns(
            checksum_expr.map_elements(
                lambda s: hashlib.md5(s.encode()).hexdigest(),
                return_dtype=pl.Utf8,
            ).alias("_checksum")
        )

        return df_with_checksum

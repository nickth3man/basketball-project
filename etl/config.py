import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Config:
    """
    Central ETL configuration.

    Values:
    - pg_dsn: PostgreSQL connection string.
    - csv_root: Root directory where all CSV files (from docs/phase_0_csv_inventory.json) live.
    - copy_batch_size: Number of rows per COPY buffer flush (for from_records fallback).
    - etl_schema: Target schema name (defaults to 'public'; keep aligned with db/schema.sql).
    """
    pg_dsn: str
    csv_root: str = "./csv_files"
    copy_batch_size: int = 50_000
    etl_schema: str = "public"

    @property
    def effective_csv_root(self) -> str:
        # Normalize for callers; no trailing slash assumptions.
        return self.csv_root.rstrip("/\\")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def get_config() -> Config:
    """
    Build a Config from environment variables with sensible defaults.

    Environment:
    - PG_DSN: full PostgreSQL DSN string.
    - CSV_ROOT: root directory for CSV files.
    - COPY_BATCH_SIZE: integer for batch size (optional).
    - ETL_SCHEMA: target schema (defaults to 'public').
    """
    pg_dsn = _get_env(
        "PG_DSN",
        "postgresql://postgres:postgres@localhost:5432/basketball",
    )

    csv_root = _get_env("CSV_ROOT", "./csv_files")
    etl_schema = _get_env("ETL_SCHEMA", "public")

    copy_batch_size_env = _get_env("COPY_BATCH_SIZE")
    if copy_batch_size_env:
        try:
            copy_batch_size = int(copy_batch_size_env)
        except ValueError:
            copy_batch_size = 50_000
    else:
        copy_batch_size = 50_000

    return Config(
        pg_dsn=pg_dsn,
        csv_root=csv_root,
        copy_batch_size=copy_batch_size,
        etl_schema=etl_schema,
    )
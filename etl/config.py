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
    - expectations_path: Path to expectations YAML (default: etl/expectations.yaml).
    - enable_expectations: Whether to enable expectations & schema drift checks.
    - etl_mode: High-level ETL execution mode (full / incremental_* / subset / dry_run).
    - etl_mode_params: Optional JSON-encoded parameters for the chosen mode.
    """

    pg_dsn: str
    csv_root: str = "./csv_files"
    copy_batch_size: int = 50_000
    etl_schema: str = "public"

    # Expectations / quality config
    expectations_path: str = "etl/expectations.yaml"
    enable_expectations: bool = True

    # Mode + parameters (used by scripts/run_full_etl and loaders)
    etl_mode: str = "full"
    etl_mode_params: Optional[str] = None  # raw JSON string; callers can json.loads

    @property
    def effective_csv_root(self) -> str:
        # Normalize for callers; no trailing slash assumptions.
        return self.csv_root.rstrip("/\\")


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def get_config() -> Config:
    """
    Build a Config from environment variables with sensible defaults.

    Environment:
    - PG_DSN: full PostgreSQL DSN string.
    - CSV_ROOT: root directory for CSV files.
    - COPY_BATCH_SIZE: integer for batch size (optional).
    - ETL_SCHEMA: target schema (defaults to 'public').
    - ETL_EXPECTATIONS_PATH: override for expectations.yaml location.
    - ETL_ENABLE_EXPECTATIONS: "true"/"false" to toggle expectations and drift checks.
    - ETL_MODE: default ETL mode if not provided via CLI (full, incremental_by_season, etc.).
    - ETL_MODE_PARAMS: JSON string with mode parameters (e.g. seasons/date ranges/subsets).
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

    expectations_path = _get_env("ETL_EXPECTATIONS_PATH", "etl/expectations.yaml")
    enable_expectations = _get_bool_env("ETL_ENABLE_EXPECTATIONS", True)

    etl_mode = _get_env("ETL_MODE", "full") or "full"
    etl_mode_params = _get_env("ETL_MODE_PARAMS")

    return Config(
        pg_dsn=pg_dsn,
        csv_root=csv_root,
        copy_batch_size=copy_batch_size,
        etl_schema=etl_schema,
        expectations_path=expectations_path,
        enable_expectations=enable_expectations,
        etl_mode=etl_mode,
        etl_mode_params=etl_mode_params,
    )

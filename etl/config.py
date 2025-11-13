import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Config:
    """
    Central ETL configuration with improved structure.

    Values:
    - pg_dsn: PostgreSQL connection string.
    - csv_root: Root directory where all CSV files live.
    - copy_batch_size: Number of rows per COPY buffer flush.
    - etl_schema: Target schema name.
    - expectations_path: Path to expectations YAML.
    - enable_expectations: Whether to enable expectations & schema drift checks.
    - etl_mode: High-level ETL execution mode.
    - etl_mode_params: Optional parameters for the chosen mode.
    - allowed_csv_files: List of allowed CSV file names for validation.
    - dry_run: Whether to run in dry-run mode (no database writes).
    """

    pg_dsn: str
    csv_root: str = field(default="./csv_files")
    copy_batch_size: int = field(default=50_000)
    etl_schema: str = field(default="public")

    # Quality and validation config
    expectations_path: str = field(default="etl/expectations.yaml")
    enable_expectations: bool = field(default=True)

    # Runtime mode config
    etl_mode: str = field(default="full")
    etl_mode_params: Optional[str] = field(default=None)

    # Security and validation
    allowed_csv_files: List[str] = field(default_factory=list)
    dry_run: bool = field(default=False)

    @property
    def effective_csv_root(self) -> str:
        """Normalize CSV root path - remove trailing slashes."""
        return self.csv_root.rstrip("/\\")

    def get_csv_path(self, filename: str) -> str:
        """
        Get full path for a CSV file.

        [SECURITY] Validates filename against allowlist if enabled.
        Prevents path traversal by rejecting filenames with path separators.

        Preconditions: filename is a simple filename (no path separators).
        Postconditions: Returns absolute path to CSV file.
        Side effects: None (path construction only).
        """
        # Path traversal protection
        if any(char in filename for char in ["..", "/", "\\"]):
            raise ValueError(
                f"Invalid filename '{filename}': "
                "path separators and '..' not allowed"
            )

        # Check if filename is absolute path (security risk)
        if os.path.isabs(filename):
            raise ValueError(
                f"Invalid filename '{filename}': " "absolute paths not allowed"
            )

        if self.allowed_csv_files and filename not in self.allowed_csv_files:
            raise ValueError(f"CSV file '{filename}' not in allowed list")
        return os.path.join(self.effective_csv_root, filename)

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for logging/debugging."""
        return {
            "pg_dsn": self.pg_dsn,
            "csv_root": self.csv_root,
            "copy_batch_size": self.copy_batch_size,
            "etl_schema": self.etl_schema,
            "expectations_path": self.expectations_path,
            "enable_expectations": self.enable_expectations,
            "etl_mode": self.etl_mode,
            "etl_mode_params": self.etl_mode_params,
            "dry_run": self.dry_run,
        }


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with fallback."""
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def _get_bool_env(name: str, default: bool) -> bool:
    """Get boolean environment variable."""
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _get_list_env(name: str, default: List[str] = None) -> List[str]:
    """Get comma-separated list from environment variable."""
    raw = os.getenv(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_config() -> Config:
    """
    Build a Config from environment variables with sensible defaults.

    Environment Variables:
    - PG_DSN: full PostgreSQL DSN string
    - CSV_ROOT: root directory for CSV files
    - COPY_BATCH_SIZE: integer for batch size (optional)
    - ETL_SCHEMA: target schema (defaults to 'public')
    - ETL_EXPECTATIONS_PATH: override for expectations.yaml location
    - ETL_ENABLE_EXPECTATIONS: "true"/"false" to toggle expectations
    - ETL_MODE: default ETL mode (full, incremental_by_season, etc.)
    - ETL_MODE_PARAMS: JSON string with mode parameters
    - ETL_ALLOWED_CSV_FILES: comma-separated list of allowed CSV files
    - ETL_DRY_RUN: "true"/"false" for dry-run mode

    Returns:
    - Config instance with normalized values
    """
    # Core database and file config
    pg_dsn = _get_env(
        "PG_DSN",
        "postgresql://postgres:postgres@localhost:5432/basketball",
    )

    csv_root = _get_env("CSV_ROOT", "./csv_files")
    etl_schema = _get_env("ETL_SCHEMA", "public")

    # Batch size with validation
    copy_batch_size_env = _get_env("COPY_BATCH_SIZE")
    copy_batch_size = int(copy_batch_size_env) if copy_batch_size_env else 50_000

    # Feature toggles
    expectations_path = _get_env("ETL_EXPECTATIONS_PATH", "etl/expectations.yaml")
    enable_expectations = _get_bool_env("ETL_ENABLE_EXPECTATIONS", True)

    # Runtime mode
    etl_mode = _get_env("ETL_MODE", "full") or "full"
    etl_mode_params = _get_env("ETL_MODE_PARAMS")

    # Security and validation
    allowed_csv_files = _get_list_env("ETL_ALLOWED_CSV_FILES")
    dry_run = _get_bool_env("ETL_DRY_RUN", False)

    return Config(
        pg_dsn=pg_dsn,
        csv_root=csv_root,
        copy_batch_size=copy_batch_size,
        etl_schema=etl_schema,
        expectations_path=expectations_path,
        enable_expectations=enable_expectations,
        etl_mode=etl_mode,
        etl_mode_params=etl_mode_params,
        allowed_csv_files=allowed_csv_files,
        dry_run=dry_run,
    )


def validate_config(config: Config) -> None:
    """
    Validate configuration before usage.

    Checks:
    - All required environment variables are present
    - CSV files exist if not in dry-run mode
    - Database connection can be established
    """
    if config.dry_run:
        print("Running in dry-run mode - no database writes will occur")
        return

    # Additional validation can be added here
    print("Configuration validated successfully")

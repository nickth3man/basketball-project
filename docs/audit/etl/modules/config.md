# ETL Config Contract & Runtime Inputs

_Source: [`etl/config.py`](../../../etl/config.py:1)_

## 1. Purpose & Role

`Config` encapsulates all ETL runtime configuration derived from environment variables. It is:

- The canonical source for:
  - Database connection info
  - CSV filesystem layout
  - Batch sizing
  - Target schema
  - Expectations/validation toggles
  - ETL execution mode
  - CSV allowlisting
  - Dry-run behavior
- Purely in-process; it does not perform I/O beyond environment reads and path construction.
- Designed to be safe-by-default and backwards compatible with full-run behavior.

## 2. Inputs

### 2.1 Environment Variables

Resolved via helper functions `_get_env`, `_get_bool_env`, `_get_list_env`:

- `PG_DSN`
  - Used by: `get_config()`
  - Default: `postgresql://postgres:postgres@localhost:5432/basketball`
  - Semantics: Primary PostgreSQL DSN for ETL operations.

- `CSV_ROOT`
  - Default: `./csv_files`
  - Semantics: Root directory for all ETL input CSVs.
  - Used to form `Config.csv_root` and `effective_csv_root`.

- `COPY_BATCH_SIZE`
  - Default: `50_000`
  - Parsed as `int`.
  - Semantics: Number of rows per COPY buffer flush; performance tuning only.

- `ETL_SCHEMA`
  - Default: `public`
  - Semantics: Target DB schema for ETL-managed tables.

- `ETL_EXPECTATIONS_PATH`
  - Default: `etl/expectations.yaml`
  - Semantics: Filesystem path to expectations YAML.
  - Drives `Config.expectations_path`.

- `ETL_ENABLE_EXPECTATIONS`
  - Default: `True`
  - Parsed case-insensitively from `{1,true,yes,on}`.
  - Semantics: Master toggle for expectations and schema drift checks.

- `ETL_MODE`
  - Default: `"full"`
  - Semantics: High-level ETL mode selection (e.g. `full`, `incremental_by_season`, etc.).
  - Interpretation performed by callers; `Config` stores string only.

- `ETL_MODE_PARAMS`
  - Default: `None`
  - Semantics: JSON/text blob of mode-specific parameters (e.g. seasons, date ranges).
  - Not parsed here; consumers are responsible.

- `ETL_ALLOWED_CSV_FILES`
  - Default: empty list
  - Parsed as comma-separated list.
  - Semantics: Allowlist of permitted CSV filenames for secure file resolution.

- `ETL_DRY_RUN`
  - Default: `False`
  - Semantics: If true, ETL should perform read-only operations with no DB writes.

### 2.2 Internal Helpers

- `_get_env(name, default)`:
  - Returns env value or `default` if unset/empty.
- `_get_bool_env(name, default)`:
  - Returns boolean from common truthy/falsey strings, else `default`.
- `_get_list_env(name, default)`:
  - Returns stripped list from comma-separated env; empty list if unset.

## 3. Outputs

### 3.1 Config Object Fields

Constructed by `get_config()`:

- `pg_dsn: str`
  - Effective DSN for all ETL DB connections.

- `csv_root: str`
  - Raw CSV root path (may contain trailing slash).

- `copy_batch_size: int`
  - Effective batch size for COPY-style operations.

- `etl_schema: str`
  - Target schema name; used by downstream SQL/DDL, not modified here.

- `expectations_path: str`
  - Effective path to expectations YAML.

- `enable_expectations: bool`
  - Controls whether expectations/schema drift modules should run.

- `etl_mode: str`
  - Selected mode; interpreted by loaders/orchestrators.

- `etl_mode_params: Optional[str]`
  - Raw parameter payload; semantics are consumer-defined.

- `allowed_csv_files: List[str]`
  - Allowlisted filenames enforced by `get_csv_path`.

- `dry_run: bool`
  - Global indicator that ETL should avoid writes and treat operations as no-op where honored.

### 3.2 Derived Methods

- `Config.effective_csv_root`:
  - Returns `csv_root` with trailing `/` or `\` removed.
  - Used to normalize path joins.

- `Config.get_csv_path(filename: str) -> str`
  - Constructs full path to a CSV file under `effective_csv_root`.
  - Applies security and validation rules (see §4).

- `Config.to_dict() -> Dict[str, Any]`
  - Safe, read-only snapshot for logging/diagnostics.

## 4. Keys, Security Invariants & Merge Logic

Although `Config` is not a DB entity, it enforces important invariants:

1. **Path traversal protection**
   - Rejects `filename` containing `".."`, `"/"`, or `"\\"`.
   - Rejects absolute paths via `os.path.isabs`.
   - Effect: Callers cannot escape `CSV_ROOT` through `get_csv_path`.
   - Failure mode: Raises `ValueError` with a descriptive message.

2. **Allowlist enforcement (`allowed_csv_files`)**
   - When non-empty, `filename` must be in `allowed_csv_files`.
   - Failure mode: Raises `ValueError("CSV file '{filename}' not in allowed list")`.
   - Ensures only known/approved CSVs are read.

3. **Deterministic defaults**
   - All unset/empty env vars fall back to explicit defaults.
   - Guarantees stable behavior in local/dev environments.

4. **No implicit DB actions**
   - `validate_config(config)` currently:
     - Logs a message for dry-run.
     - Otherwise prints "Configuration validated successfully".
     - No connection attempts or filesystem scans are performed.
   - This preserves non-invasive behavior; actual validation is left to callers.

## 5. Assumptions

- Environment is the single source of truth; there is no layered config (e.g. TOML/YAML) here.
- Callers will:
  - Use `get_config()` once and pass the resulting object through ETL flows.
  - Respect `dry_run` and `enable_expectations` semantics when performing writes/checks.
  - Interpret `etl_mode` / `etl_mode_params` according to documented orchestration behavior.
- Defaults are chosen to:
  - Work for a standard local Postgres + `./csv_files` layout.
  - Preserve existing ETL behavior when no new envs are set.

## 6. Failure Modes

- Misconfiguration via env:
  - Invalid `COPY_BATCH_SIZE` (non-int) raises `ValueError` during `int()` cast.
  - Invalid `ETL_*` booleans result in fallback to default (non-fatal).
- File resolution:
  - Invalid or non-allowlisted filenames in `get_csv_path` raise `ValueError`.
- These are **early, explicit failures** intended to prevent:
  - Reading from unintended locations.
  - Silent mis-routing of CSV inputs.

## 7. Existing Validations & Hooks

- `validate_config(config: Config)`:
  - Currently a stub-level hook:
    - If `dry_run` is true: prints a message and returns.
    - Otherwise prints a success message.
  - Commented intent mentions:
    - Checking required env vars.
    - Verifying CSV existence (when not in dry-run).
    - Verifying DB connectivity.
  - No runtime behavior is changed; the function is safe to call in all contexts.

## 8. Summary for Track 1 Audit

- `etl/config.py` defines a **pure, centralized configuration contract**.
- Runtime inputs are strictly from environment variables; no hidden defaults beyond those documented above.
- Output is an immutable `Config` object plus safe helpers for:
  - CSV path resolution with strong security guarantees.
  - Introspection via `to_dict`.
- There is **no direct DB or filesystem mutation**; behavior is fully compatible with the “no runtime behavior changes” constraint for this audit.
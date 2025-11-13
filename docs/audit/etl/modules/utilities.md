# ETL Utilities & Logging Behavior

_Sources:_
- [`etl/logging_utils.py`](../../../etl/logging_utils.py:1)
- [`etl/paths.py`](../../../etl/paths.py:1)

This artifact documents how ETL utilities handle path resolution and logging, and how they impact observability and lineage. Behavior is descriptive only; no runtime changes.

---

## 1. Logging Utilities (`etl/logging_utils.py`)

### 1.1 Purpose

Provides a small, centralized logging layer for ETL modules:

- Ensures consistent log formatting.
- Adds lightweight, key/value-style structured logging.
- Exposes ETL-specific helpers for steps, validation, and schema drift.
- Respects existing application logging if already configured.

### 1.2 Inputs

- `ETL_LOG_LEVEL` (env var)
  - Read once at import as `LOG_LEVEL = os.getenv("ETL_LOG_LEVEL", "INFO").upper()`.
  - Controls root logger level when this module configures logging.
  - If unset: defaults to `INFO`.

- Call-site parameters:
  - All helpers accept:
    - A `logging.Logger` instance.
    - A message string.
    - Arbitrary keyword fields (`**fields`) used as structured context.

### 1.3 Behavior & Outputs

#### 1.3.1 Root Logger Configuration

- `_configure_root_logger()`:
  - If any handlers already exist on the root logger:
    - Returns without changes (assumes caller/app owns logging).
  - Otherwise:
    - Creates a `StreamHandler` (stdout/stderr as per logging defaults).
    - Applies formatter:

      ```text
      %(asctime)s %(levelname)s %(name)s %(message)s [%(filename)s:%(lineno)d]
      ```

    - Sets root level to `LOG_LEVEL`.
    - Attaches handler to root.

- Impact:
  - Ensures ETL scripts run standalone with sensible logs.
  - Avoids double configuration when embedded in a larger app.

#### 1.3.2 Logger Access

- `get_logger(name: str) -> logging.Logger`:
  - Ensures root is configured (idempotent).
  - Returns `logging.getLogger(name)`.
  - Used across ETL modules to keep consistent style.

#### 1.3.3 Structured Logging

- `log_structured(logger, level, message, **fields)`:
  - If `logger.isEnabledFor(level)` is false:
    - Returns without formatting.
  - Otherwise:
    - Serializes `fields` as `key=value` tokens joined by spaces.
    - Emits:

      ```text
      <message> | key1=val1 key2=val2 ...
      ```

    - via `logger.log(level, formatted_message)`.

- Effect on observability:
  - All ETL logs that use this helper include machine-parseable key/value context.
  - Enables downstream log search / correlation (e.g. filter on `etl_run_id=...`).

#### 1.3.4 ETL-Specific Helpers

Each helper is a thin wrapper around `log_structured`:

- `log_etl_event(logger, event, **fields)`
  - Generic event marker, no fixed schema.
  - Example usage: `"etl_run_start"`, `"etl_run_end"` with run identifiers.

- `log_etl_step_start(logger, etl_run_id, step_name, **fields)`
  - Emits `etl_step_start` with:
    - `etl_run_id`
    - `step_name`
    - Any additional context (e.g. loader name, mode).
  - Used to delineate ETL phases.

- `log_etl_step_end(logger, etl_run_id, step_name, status, **fields)`
  - Emits `etl_step_end` with:
    - `etl_run_id`
    - `step_name`
    - `status` (e.g. `success`, `error`)
    - Optional metrics (e.g. row counts, durations).

- `log_schema_drift_issue(logger, etl_run_id, source_type, source_id, issue_type, severity, details)`
  - Emits `schema_drift_issue` with:
    - `etl_run_id`
    - `source_type` (e.g. `csv`, `table`)
    - `source_id` (concrete identifier)
    - `issue_type` and `severity`
    - Arbitrary `details` expanded into key/value pairs.
  - Intended for expectations/schema drift reporting.

- `log_validation_issue(logger, etl_run_id, check_id, severity, status, details)`
  - Emits `validation_issue` with:
    - `etl_run_id`
    - `check_id` (stable identifier for the validation)
    - `severity` and `status`
    - Extra `details`.
  - Used by validation harnesses to record specific check failures/warnings.

### 1.4 Assumptions & Failure Modes

- Assumes:
  - If an enclosing application wants custom logging, it sets handlers before importing/using ETL modules.
- Failure modes:
  - Mis-set `ETL_LOG_LEVEL` falls back to `.upper()` string; invalid levels behave per stdlib logging (no special ETL handling).
- No DB or ETL behavior changes:
  - Logging is side-effect-only for observability.
  - All helpers are safe no-ops when levels are disabled.

---

## 2. Path Utilities (`etl/paths.py`)

### 2.1 Purpose

Defines a canonical mapping from logical CSV concepts to relative filenames and a resolver that:

- Centralizes CSV naming based on [`docs/phase_0_csv_inventory.json`](../../../docs/phase_0_csv_inventory.json:1) (by convention).
- Ensures all ETL modules derive physical CSV paths from `Config.effective_csv_root`.
- Simplifies inventory, lineage, and validation of input sources.

### 2.2 Defined Constants (Relative Filenames)

All of the following are **relative** names; they are not absolute paths and do not include the CSV root:

- Player-related:
  - `PLAYER_CSV = "player.csv"`
  - `PLAYER_DIRECTORY_CSV = "playerdirectory.csv"`
  - `COMMON_PLAYER_INFO_CSV = "common_player_info.csv"`
  - `PLAYER_SEASON_INFO_CSV = "playerseasoninfo.csv"`
  - `PLAYER_CAREER_INFO_CSV = "playercareerinfo.csv"`

- Team-related:
  - `TEAM_CSV = "team.csv"`
  - `TEAM_HISTORY_CSV = "team_history.csv"`
  - `TEAM_DETAILS_CSV = "team_details.csv"`

- Player-season satellites:
  - `PLAYER_PER_GAME_CSV = "playerstatspergame.csv"`
  - `PLAYER_TOTALS_CSV = "playerstatstotals.csv"`
  - `PLAYER_PER36_CSV = "playerstatsper36.csv"`
  - `PLAYER_PER100_CSV = "playerstatsper100poss.csv"`
  - `PLAYER_ADVANCED_CSV = "playerstatsadvanced.csv"`

- Team-season stats:
  - `TEAM_TOTALS_CSV = "teamstats.csv"`
  - `TEAM_PER_GAME_CSV = "teamstatspergame.csv"`
  - `TEAM_PER100_CSV = "teamstatsper100poss.csv"`
  - `TEAM_OPP_TOTALS_CSV = "oppteamstats.csv"`
  - `TEAM_OPP_PER_GAME_CSV = "oppteamstatspergame.csv"`
  - `TEAM_OPP_PER100_CSV = "teamstatsper100poss.csv"`

- Games & box scores:
  - `GAMES_CSV = "games.csv"`
  - `GAME_SUMMARY_CSV = "gamesummary.csv"`
  - `LINE_SCORE_CSV = "linescore.csv"`
  - `OTHER_STATS_CSV = "other_stats.csv"`
  - `BOX_SCORE_PLAYER_CSV = "boxscore_player.csv"`

- Play-by-play:
  - `PBP_CSV = "play_by_play.csv"`

- Awards & draft:
  - `AWARDS_ALL_STAR_CSV = "all_starselections.csv"`
  - `AWARDS_PLAYER_SHARES_CSV = "playerawardshares.csv"`
  - `AWARDS_END_OF_SEASON_TEAMS_CSV = "endofseasonteams.csv"`
  - `AWARDS_END_OF_SEASON_VOTING_CSV = "endofseasonteams_voting.csv"`
  - `DRAFT_PICKS_CSV = "draft_history.csv"`

- Inactive:
  - `INACTIVE_PLAYERS_CSV = "inactive_players.csv"`

These constants provide a single, auditable reference for how ETL expects its upstream CSVs to be named.

### 2.3 Path Resolution

#### 2.3.1 `resolve_csv_path(config: Config, relative_name: str) -> str`

- Implementation:
  - Returns `os.path.join(config.effective_csv_root, relative_name)`.
- Semantics:
  - Uses `Config.effective_csv_root` (trailing separators stripped) to avoid double separators.
  - Receives `relative_name` from the constants above.
- Security & lineage:
  - Trusts `relative_name` to be a simple filename from this module.
  - Any additional protection (e.g., allowlist, traversal checks) is enforced upstream by:
    - `Config.get_csv_path()` and `allowed_csv_files` when used.
  - Consumers that call `resolve_csv_path` directly follow a consistent location scheme:
    - Inputs are always under the configured CSV root.

#### 2.3.2 `all_known_csvs() -> Dict[str, str>`

- Returns a dict:
  - Keys: logical labels (e.g. `"player"`, `"games"`, `"pbp"`, `"awards_all_star"`, `"inactive_players"`).
  - Values: the corresponding relative filenames from this module.
- Uses:
  - ETL metadata and inventory reporting.
  - Validation or tooling to:
    - Enumerate expected inputs.
    - Compare against actual on-disk files.
    - Track versions/hashes by logical name.

### 2.4 Assumptions & Failure Modes

- Assumes:
  - `Config.csv_root` / `effective_csv_root` is the authoritative root directory.
  - Callers pass one of the declared constants as `relative_name`.
- Failure handling:
  - This module does **not** check for file existence.
  - Missing/invalid files are handled by loader modules (which log warnings and skip).
- Impact:
  - All ETL modules share a single mapping from logical source → filename → path.
  - This supports reproducible lineage from DB records back to specific CSV inputs.

---

## 3. Observability & Lineage Impact

### 3.1 Logging

- Use of `log_structured` across ETL modules ensures:
  - Every key operation (load start/end, dry-run, validation, schema drift) includes:
    - Operation name (`etl_step_start`, `Loaded players`, etc.).
    - Context fields (e.g. `table`, `rows`, `mode`, `etl_run_id`).
- This enables:
  - Tracing ETL runs end-to-end.
  - Correlating issues (validation failures, drift) with specific runs and inputs.

### 3.2 Paths

- `etl/paths.py` and `Config.effective_csv_root` together:
  - Define a deterministic mapping from:
    - Logical source id → relative filename → absolute filesystem location.
  - This mapping is:
    - Centralized.
    - Static (code-defined).
    - Compatible with inventory and expectations tooling.

---

## 4. Summary for Track 1 Audit

- `etl/logging_utils.py`:
  - Provides consistent, low-friction, structured logging.
  - Does not alter ETL semantics; only observability.
  - Honors pre-configured logging to avoid conflicts.

- `etl/paths.py`:
  - Central registry of ETL CSV filenames.
  - `resolve_csv_path` binds these to `Config`-driven roots.
  - `all_known_csvs` supports inventory/lineage reporting.

Together, these utilities:

- Improve traceability (who/what/when for ETL steps).
- Provide a clear, auditable contract for input locations.
- Operate entirely within the “no runtime behavior change / no schema change” constraints, serving as infrastructure for diagnostics and lineage rather than business logic.
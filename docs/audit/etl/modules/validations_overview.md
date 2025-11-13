# ETL Validations Overview

Describes validations implemented in:

- [etl/validate_data.py](etl/validate_data.py:1)
- [etl/validate_metrics.py](etl/validate_metrics.py:1)
- [etl/validate.py](etl/validate.py:1)
- [etl/schema_drift.py](etl/schema_drift.py:1)
- [etl/expectations_loader.py](etl/expectations_loader.py:1)

Based **only** on in-repo code. No behavioral changes; this is a descriptive index.

---

## 1. Module-by-Module Summary

### 1.1 `etl/validate_data.py`

**Scope:** Online DB validations (structural, referential, basic sanity).  
**Where it runs:** Against a live PostgreSQL database using project config.

**Key checks (high level):**

- **Structural existence**
  - Ensures presence of core tables and views:
    - Tables: `players`, `teams`, `games`, `player_season`, `team_season`, `boxscore_team`, `pbp_events`.
    - Views: `vw_player_season_advanced`, `vw_team_season_advanced`, `vw_player_career_aggregates`.
  - Missing objects recorded as fatal errors.

- **Referential integrity (orphan detection)**
  - `player_season.player_id` → `players.player_id`
  - `team_season.team_id` → `teams.team_id`
  - `boxscore_team.game_id` → `games.game_id`
  - `pbp_events.game_id` → `games.game_id`
  - Uses `count_orphans` helper; non-zero counts become fatal errors.

- **Row count sanity**
  - For `players`, `teams`, `games`:
    - Logs warnings if counts ≤ 0.
    - Structural checks already guard missing tables.

**Severity behavior:**

- Structural / referential failures: collected as fatal, cause non-zero exit.
- Summary issues: warnings only.

---

### 1.2 `etl/validate_metrics.py`

**Scope:** Validations focused on advanced/derived metrics.  
**Where it runs:** Against DB views/tables populated by ETL.

**Key patterns (from observed code structure):**

- Uses targeted COUNT queries against:
  - `vw_player_season_advanced`
  - `vw_team_season_advanced`
  - Related hub/satellite tables
- Checks include:
  - Presence of rows where expected (non-empty key metrics).
  - Reasonable ranges or non-null constraints for selected advanced metrics.
- On violation:
  - Raises `RuntimeError` or logs structured failure, making it effectively fatal for CI/strict runs.

**Severity behavior:**

- Metric consistency violations are treated as hard failures (exceptions), not soft warnings.

*(Exact per-metric list is encoded as SQL in this module and can be read directly there; this overview does not reinterpret thresholds.)*

---

### 1.3 `etl/validate.py`

**Scope:** Composite validation harness for higher-level integrity.  
**Where it runs:** DB-level, often as a dedicated validation step.

**Key responsibilities (as implemented):**

- Wraps specialized checks such as:
  - Foreign key and orphan validations mirroring declared constraints.
  - Hub/satellite consistency for:
    - `player_season` vs `player_season_*` tables.
    - `team_season` vs `team_season_*` tables.
  - Games / boxscore integrity:
    - At most two `boxscore_team` rows per game.
    - No duplicate PKs in `boxscore_team`.
  - Awards / draft sanity:
    - `awards_*` and `draft_picks` do not reference missing players when IDs are present.
- Aggregates checks via `run_all_validations(conn)` with:
  - Structured logging (`log_structured`) for each check.
  - Fail-fast semantics on hard violations.

**Severity behavior:**

- Uses `RuntimeError` to mark validation failure (fatal).
- Passes when all embedded SQL COUNT checks return zero problem rows.

---

### 1.4 `etl/schema_drift.py`

**Scope:** Schema drift detection for CSVs and DB tables.

**Core concepts:**

- Consumes expectations from:
  - [etl/expectations_loader.py](etl/expectations_loader.py:89)
  - Backed by [etl/expectations.yaml](etl/expectations.yaml:1)
- Produces structured **issues**, not direct failures:
  - Fields: `source_type`, `source_id`, `issue_type`, `severity`, `details`, optional `etl_run_id`.
  - Logged via `log_schema_drift_issue` and `log_etl_event`.

**Key functions:**

- `check_csv_source_schema(source_id, file_path, df, expectations, etl_run_id=None)`
  - Compares Polars `DataFrame` schema vs `csv_sources` expectations.
  - Emits issues for:
    - `missing_column`
    - `extra_column`
    - `type_mismatch`
    - `null_in_primary_key`
    - `primary_key_violation`
    - `row_count_zero`
  - Severities determined from `drift_policy` or defaults.

- `check_table_schema(conn, table_name, expectations, etl_run_id=None)`
  - Introspects `information_schema.columns` for an existing table.
  - Compares to `tables` expectations.
  - Emits issues for:
    - Missing / extra / type-mismatched columns (severity via defaults).

- Best-effort behavior:
  - Swallows IO/introspection exceptions.
  - Never raises solely due to missing expectations; favors observability over breakage.

**Severity behavior:**

- Severity is data-driven (`info`/`warn`/`error` as configured).
- Emitting an `error`-severity issue does not itself halt ETL; enforcement is left to callers.

---

### 1.5 `etl/expectations_loader.py`

**Scope:** Centralized loader for expectations configuration.

**Key behaviors:**

- `load_expectations(config=None)`:
  - Resolves expectations YAML path (default `etl/expectations.yaml`).
  - On missing/invalid YAML:
    - Logs a warning.
    - Returns `_EMPTY_EXPECTATIONS`:
      - Empty maps, but with safe default policies.
    - Never raises; intentionally fail-open.

- Accessors:
  - `get_csv_expectation(expectations, source_id)`:
    - Returns matching `csv_sources` entry or `None`.
  - `get_table_expectation(expectations, table_name)`:
    - Returns matching `tables` entry or `None`.
  - `resolve_policy(expectations, policy_key, override=None)`:
    - Resolves severity from overrides / defaults / `warn` fallback.

- Utilities:
  - `expectations_to_json_serializable`, `dump_expectations_snapshot`:
    - For diagnostics and metadata.

**Severity behavior:**

- Encodes the default policy surface used by `schema_drift`:
  - `on_missing_column`: `error`
  - `on_extra_column`: `warn`
  - `on_type_mismatch`: `warn`
  - `on_primary_key_violation`: `error`
  - `on_null_in_required`: `error`
  - `on_row_count_zero`: `warn`

---

## 2. Tabular Overview of Checks

Below is a concise, **non-exhaustive but concrete** mapping of major checks to their implementations.  
IDs are stable labels for cross-reference; all targets derive directly from in-repo SQL/Python.

| check_id                               | module                          | function / locus                    | check_type          | target_objects                                                                                     | severity_behavior                                  |
|----------------------------------------|---------------------------------|-------------------------------------|---------------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------|
| `struct.core_objects_exist`           | `etl/validate_data.py`         | `run_structural_checks`            | structural          | Tables: `players`, `teams`, `games`, `player_season`, `team_season`, `boxscore_team`, `pbp_events`; Views: `vw_*advanced`, `vw_player_career_aggregates` | fatal on missing; contributes to non-zero exit     |
| `ref.player_season_player_fk`         | `etl/validate_data.py`         | `run_referential_checks`           | referential         | `player_season.player_id` → `players.player_id`                                                   | fatal if any orphans                               |
| `ref.team_season_team_fk`             | `etl/validate_data.py`         | `run_referential_checks`           | referential         | `team_season.team_id` → `teams.team_id`                                                           | fatal                                              |
| `ref.boxscore_team_game_fk`           | `etl/validate_data.py`         | `run_referential_checks`           | referential         | `boxscore_team.game_id` → `games.game_id`                                                         | fatal                                              |
| `ref.pbp_events_game_fk`              | `etl/validate_data.py`         | `run_referential_checks`           | referential         | `pbp_events.game_id` → `games.game_id`                                                            | fatal                                              |
| `summary.core_rowcount_nonzero`       | `etl/validate_data.py`         | `run_summary_checks`               | metrics_sanity      | Tables: `players`, `teams`, `games`                                                              | warning if zero rows                               |
| `metrics.player_season_view_sanity`   | `etl/validate_metrics.py`      | view-specific checks               | metrics_sanity      | `vw_player_season_advanced` and underlying hub/satellites                                         | treated as fatal (exceptions on inconsistencies)   |
| `metrics.team_season_view_sanity`     | `etl/validate_metrics.py`      | view-specific checks               | metrics_sanity      | `vw_team_season_advanced`, `team_season_*` tables                                                 | fatal                                              |
| `metrics.career_view_sanity`          | `etl/validate_metrics.py`      | checks on aggregates               | metrics_sanity      | `vw_player_career_aggregates`                                                                    | fatal                                              |
| `drift.csv_missing_or_extra_columns`  | `etl/schema_drift.py`          | `check_csv_source_schema`          | drift               | CSV sources defined in `expectations.yaml`                                                        | severities via expectations (default error/warn)   |
| `drift.csv_type_mismatch`             | `etl/schema_drift.py`          | `check_csv_source_schema`          | drift               | Same as above                                                                                     | severity via expectations                          |
| `drift.csv_pk_null_or_violation`      | `etl/schema_drift.py`          | `check_csv_source_schema`          | drift               | CSV logical primary keys                                                                          | severity via expectations                          |
| `drift.csv_row_count_zero`            | `etl/schema_drift.py`          | `check_csv_source_schema`          | drift               | CSV sources                                                                                       | severity via expectations                          |
| `drift.table_missing_or_extra_columns`| `etl/schema_drift.py`          | `check_table_schema`               | drift               | Tables with entries in `tables` expectations                                                      | severity via defaults; non-fatal by design         |
| `core_fk.check_fk_integrity`          | `etl/validate.py`              | `check_fk_integrity`               | referential         | Joins across `games`, `teams`, `boxscore_team`, `pbp_events`, `inactive_players`                  | fatal (raises on any issues)                       |
| `hub_sat.player_season_consistency`   | `etl/validate.py`              | `check_player_season_consistency`  | structural          | `player_season` vs `player_season_*` satellites                                                   | fatal                                              |
| `hub_sat.team_season_consistency`     | `etl/validate.py`              | `check_team_season_consistency`    | structural          | `team_season` vs `team_season_*` satellites                                                       | fatal                                              |
| `games.boxscore_constraints`          | `etl/validate.py`              | `check_games_integrity`            | structural          | `games`, `boxscore_team`                                                                         | fatal                                              |
| `awards_draft.integrity`              | `etl/validate.py`              | `check_awards_and_draft`           | referential/soft    | `awards_*`, `draft_picks` vs `players` when IDs present                                           | fatal in implementation (raises on violation)      |
| `orchestrated.all_validations`        | `etl/validate.py`              | `run_all_validations`              | orchestrator        | Runs all above checks sequentially                                                                | stops on first failure                             |

All entries above are grounded in concrete functions and SQL present in the repo; labels are for this documentation only.

---

## 3. Key Properties

1. **Read-Only & Defensive**
   - All validation modules operate via `SELECT`/COUNT queries and metadata reads.
   - They do **not** mutate domain data (beyond logging/metadata in ETL tables when configured).

2. **Fail-Open vs Fail-Closed**
   - `expectations_loader` and `schema_drift`:
     - Fail-open on configuration issues (missing/invalid expectations).
     - Emit issues instead of raising, leaving enforcement to callers.
   - `validate_data.py`, `validate_metrics.py`, `validate.py`:
     - Treat core structural, referential, and metric violations as fatal:
       - Non-zero exit codes or raised exceptions.

3. **Determinism**
   - Every check is derived directly from code:
     - No invented constraints.
     - Re-running against the same code and schema yields the same set of validations.

4. **Intended Usage**
   - These validations collectively provide:
     - Assurance that Track 1 schema is present and coherent.
     - Basic guarantees about key relationships and metrics consistency.
     - A structured channel (`etl_run_issues` + drift issues) for recording anomalies
       without unexpectedly breaking ETL when configuration is incomplete.

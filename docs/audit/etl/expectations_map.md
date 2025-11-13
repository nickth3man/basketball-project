# Expectations Map

Structured mapping of expectations defined in:

- [etl/expectations.yaml](etl/expectations.yaml:1)
- [etl/expectations_loader.py](etl/expectations_loader.py:1)
- Context from:
  - [.rooroo/audit/db/schema_catalog.md](.rooroo/audit/db/schema_catalog.md:1)
  - [.rooroo/audit/etl/modules/validations_overview.md](.rooroo/audit/etl/modules/validations_overview.md:1)

This artifact is purely descriptive of the current repo configuration.  
No behaviors or schemas are changed.

---

## 1. Defaults

Derived from `defaults` in [etl/expectations.yaml](etl/expectations.yaml:3-11) and mirrored in
[etl/expectations_loader.py](etl/expectations_loader.py:36-50).

- `on_missing_column: error`
- `on_extra_column: warn`
- `on_type_mismatch: warn`
- `on_primary_key_violation: error`
- `on_null_in_required: error`
- `on_row_count_zero: warn`
- `hash_algorithm: sha256`

These act as global policies unless overridden per source/table.

---

## 2. CSV Sources Expectations

From `csv_sources` in [etl/expectations.yaml](etl/expectations.yaml:12-156).

### 2.1 `players`

- `source_id`: `players`
- `path_pattern`: `players/*.csv`
- `required`: `true`
- `schema`:
  - Columns:
    - `player_id (int, not null)`
    - `slug (text, nullable)`
    - `full_name (text, nullable)`
  - `primary_key`: `[player_id]`
- `drift_policy`: `{}` (uses global defaults)

**Intended mapping (by code & schema):**

- Loader usage: player-dimension loaders (e.g. [etl/load_dimensions.py](etl/load_dimensions.py:1) — see lineage artifact).
- Target table: `players`.

### 2.2 `teams`

- `source_id`: `teams`
- `path_pattern`: `teams/*.csv`
- `required`: `true`
- `schema`:
  - Columns:
    - `team_id (int, not null)`
    - `team_abbrev (text, not null)`
  - `primary_key`: `[team_id]`
- `drift_policy`: `{}`

**Target:** `teams`.

### 2.3 `seasons`

- `source_id`: `seasons`
- `path_pattern`: `seasons/*.csv`
- `required`: `true`
- `schema`:
  - Columns:
    - `season_id (int, not null)`
    - `season_end_year (int, not null)`
    - `lg (text, nullable)`
  - `primary_key`: `[season_id]`
- `drift_policy`: `{}`

**Target:** `seasons`.

### 2.4 `games`

- `source_id`: `games`
- `path_pattern`: `games/*.csv`
- `required`: `true`
- `schema`:
  - Columns include:
    - `game_id (text, not null)`
    - `season_end_year (int, nullable)`
    - `lg (text, nullable)`
    - `game_date_est (date, nullable)`
    - `home_team_abbrev (text, nullable)`
    - `away_team_abbrev (text, nullable)`
  - `primary_key`: `[game_id]`
- `drift_policy`: `{}`

**Target:** `games`.

### 2.5 `boxscores`

- `source_id`: `boxscores`
- `path_pattern`: `boxscores/*.csv`
- `required`: `false`
- `schema`:
  - Columns:
    - `game_id (text, not null)`
    - `team_abbrev (text, not null)`
  - `primary_key`: `[game_id, team_abbrev]`
- `drift_policy`: `{}`

**Target (by design):** contributes to `boxscore_team` (and possibly `boxscore_player`), as wired in loaders.

### 2.6 `pbp_events`

- `source_id`: `pbp_events`
- `path_pattern`: `pbp/*.csv`
- `required`: `false`
- `schema`:
  - Columns:
    - `game_id (text, not null)`
    - `eventnum (int, not null)`
  - `primary_key`: `[game_id, eventnum]`
- `drift_policy`: `{}`

**Target:** `pbp_events`.

### 2.7 `awards`

- `source_id`: `awards`
- `path_pattern`: `awards/*.csv`
- `required`: `false`
- `schema`:
  - Columns:
    - `season_end_year (int, nullable)`
    - `lg (text, nullable)`
    - `player (text, nullable)`
  - `primary_key`: `[]` (none)
- `drift_policy`: `{}`

**Targets (conceptual, per docs):** `awards_*` tables.

### 2.8 `draft`

- `source_id`: `draft`
- `path_pattern`: `draft/*.csv`
- `required`: `false`
- `schema`:
  - Columns:
    - `season_end_year (int, nullable)`
    - `lg (text, nullable)`
    - `player (text, nullable)`
  - `primary_key`: `[]`
- `drift_policy`: `{}`

**Target (conceptual, per docs):** `draft_picks`.

---

## 3. Table Expectations

From `tables` in [etl/expectations.yaml](etl/expectations.yaml:157-284).  
Each entry is consumed via `get_table_expectation` in
[etl/expectations_loader.py](etl/expectations_loader.py:120-123) and enforced by
[etl/schema_drift.py](etl/schema_drift.py:361-383).

### 3.1 `players`

- `expected_columns` (subset):
  - `player_id (bigint, not null)`
  - `slug (text, nullable)`
  - `full_name (text, nullable)`
- `primary_key`: `[player_id]`
- `quality_expectations`:
  - `min_rows: 1`

**Alignment:** Matches core `players` table in migrations.

### 3.2 `teams`

- `expected_columns`:
  - `team_id (bigint, not null)`
  - `team_abbrev (text, not null)`
- `primary_key`: `[team_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.3 `seasons`

- `expected_columns`:
  - `season_id (bigint, not null)`
  - `season_end_year (int, not null)`
  - `lg (text, nullable)`
- `primary_key`: `[season_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.4 `games`

- `expected_columns` (subset):
  - `game_id (text, not null)`
  - `season_id (bigint, nullable)`
  - `season_end_year (int, nullable)`
  - `lg (text, nullable)`
  - `home_team_id (bigint, nullable)`
  - `away_team_id (bigint, nullable)`
- `primary_key`: `[game_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.5 `boxscore_team`

- `expected_columns` (subset):
  - `game_id (text, not null)`
  - `team_id (bigint, not null)`
- `primary_key`: `[game_id, team_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.6 `pbp_events`

- `expected_columns` (subset):
  - `game_id (text, not null)`
  - `eventnum (int, not null)`
- `primary_key`: `[game_id, eventnum]`
- `quality_expectations`:
  - `min_rows: 0`

### 3.7 `player_season`

- `expected_columns` (subset):
  - `seas_id (bigint, not null)`
  - `player_id (bigint, nullable)`
  - `season_id (bigint, nullable)`
  - `season_end_year (int, nullable)`
  - `team_id (bigint, nullable)`
- `primary_key`: `[seas_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.8 `team_season`

- `expected_columns` (subset):
  - `team_season_id (bigint, not null)`
  - `team_id (bigint, nullable)`
  - `season_id (bigint, nullable)`
  - `season_end_year (int, nullable)`
- `primary_key`: `[team_season_id]`
- `quality_expectations`:
  - `min_rows: 1`

### 3.9 `awards_all_star_selections`, `awards_player_shares`,
`awards_end_of_season_teams`, `awards_end_of_season_voting`, `draft_picks`

For each of these:

- `expected_columns`: subsets with `season_id`, `season_end_year`, `player_id` (nullable).
- `primary_key`: `[]` (none).
- `quality_expectations`:
  - `min_rows: 0`

**Note:** These expectations assert existence/shape if tables exist, but:
- Concrete table DDL is not fully visible in the inspected `001` snippet.
- Validation is therefore conditional; `schema_drift` will check only when tables are present.

### 3.10 `inactive_players`

- `expected_columns`:
  - `game_id (text, not null)`
  - `player_id (bigint, not null)`
- `primary_key`: `[game_id, player_id]`
- `quality_expectations`:
  - `min_rows: 0`

**Note:** As above, this is enforced if/when the `inactive_players` table exists.

---

## 4. Integration & Flow

### 4.1 How Expectations Are Loaded

As implemented in [etl/expectations_loader.py](etl/expectations_loader.py:89-135):

- `load_expectations()`:
  - Reads YAML into:
    - `defaults`
    - `csv_sources`
    - `tables`
    - `version`
- On any problem:
  - Returns an `_EMPTY_EXPECTATIONS` object with:
    - No `csv_sources`/`tables`,
    - Safe default policies.
- Callers:
  - `schema_drift.py` uses this to drive severity and presence of checks.
  - Other components may introspect `version` and raw config for metadata only.

### 4.2 How Expectations Drive Checks

- CSV expectations:
  - Used exclusively by `check_csv_source_schema` in
    [etl/schema_drift.py](etl/schema_drift.py:116-331).
  - Only enforced for explicitly configured `source_id`s.

- Table expectations:
  - Used by `check_table_schema` in
    [etl/schema_drift.py](etl/schema_drift.py:361-383).
  - Only enforced for tables listed in `tables` section.

- No module assumes expectations must exist:
  - Missing expectations → no issues, no failures.
  - This is an intentional **fail-open** design.

---

## 5. Determinism & Scope

- This map is fully reconstructible from:
  - [etl/expectations.yaml](etl/expectations.yaml:1-284)
  - [etl/expectations_loader.py](etl/expectations_loader.py:36-135)
  - [etl/schema_drift.py](etl/schema_drift.py:334-383)
- It does **not**:
  - Introduce new rules or thresholds,
  - Guess relationships beyond what is encoded in expectations or schema.

This artifact is intended as a precise reference for subsequent gap analysis:
see [.rooroo/audit/etl/expectations_gaps.md](.rooroo/audit/etl/expectations_gaps.md:1) once generated.
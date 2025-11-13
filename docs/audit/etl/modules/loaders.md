# Loader Modules IO & Invariants Map

_Scope:_ 
- [`etl/load_games_and_boxscores.py`](../../../etl/load_games_and_boxscores.py:1)
- [`etl/load_pbp.py`](../../../etl/load_pbp.py:1)
- [`etl/load_player_seasons.py`](../../../etl/load_player_seasons.py:1)
- [`etl/load_team_seasons.py`](../../../etl/load_team_seasons.py:1)
- [`etl/load_awards_and_draft.py`](../../../etl/load_awards_and_draft.py:1)

This artifact consolidates how each ETL loader consumes inputs, writes to DB tables, enforces keys/FKs, and handles assumptions/failure modes. It is descriptive only and does not change runtime behavior.

---

## 1. Common Patterns Across Loaders

**Inputs**

- CSVs under `Config.effective_csv_root` via [`etl/paths.resolve_csv_path`](../../../etl/paths.py:60).
- Dimension snapshots from DB:
  - `players`, `teams`, `seasons`, sometimes `games`.
- ID resolution helpers from [`etl/id_resolution.py`](../../../etl/id_resolution.py:1).
- Bulk load and truncation helpers from [`etl/db.py`](../../../etl/db.py:1).
- Structured logging from [`etl/logging_utils.py`](../../../etl/logging_utils.py:1).

**Shared Behaviors**

- Missing CSVs:
  - Logged as warnings.
  - Relevant load is skipped (no partial silent behavior).
- COPY semantics:
  - Use `truncate_table` + `copy_from_polars` for deterministic reloads.
  - Required key/FK columns created or NULL-filled before load.
- ID resolution:
  - Prefer strong identifiers (numeric ids) when present.
  - Fall back to deterministic mapping via slugs/names/abbrevs.
  - On unresolved entities, leave nullable FKs as `NULL` unless schema requires otherwise.
- Safety:
  - All direct SQL is limited to `SELECT`, `TRUNCATE`, `DELETE` for controlled targets, or well-scoped `INSERT`.
  - No schema mutations.

---

## 2. `load_games_and_boxscores.py`

### 2.1 `load_games`

**Inputs**

- CSVs (via `resolve_csv_path`):
  - Primary: `GAMES_CSV` (`games.csv`)
  - Fallback: `GAME_SUMMARY_CSV` (`gamesummary.csv`)
- DB dimensions:
  - `teams(team_id, team_abbrev)`
  - `seasons(season_id, season_end_year, lg)`
- Config:
  - `Config.etl_mode`, `etl_mode_params` (seasons / date ranges)
  - `dry_run` flag

**Outputs**

- Table: `games`
- Key:
  - PK: `game_id`
- Core columns populated or ensured:
  - `game_id`
  - `season_id`, `season_end_year`, `lg`
  - `game_date_est`, `game_time_est`
  - `home_team_id`, `away_team_id`
  - `home_team_abbrev`, `away_team_abbrev`
  - `home_pts`, `away_pts`
  - `attendance`, `arena`
  - `is_playoffs`, `is_neutral_site`
  - `data_source`

**Key Logic & FKs**

- Canonicalization:
  - Renames multiple vendor-style columns into a unified schema (e.g. `GAME_ID` → `game_id`).
  - Fills `lg` with `"NBA"` if missing.
- Season resolution:
  - Uses `resolve_season_id(year, lg, season_lu)` to derive `season_id`.
- Team resolution:
  - Uses `resolve_team_id_from_abbrev(abbrev, season, team_lu)` for `home_team_id` / `away_team_id`.
- Missing columns:
  - Any required column absent in source is added as `NULL` to maintain a stable schema.

**Modes & Failure Modes**

- `mode="full"`:
  - `TRUNCATE games CASCADE` then bulk insert all rows.
- Incremental modes:
  - Filter dataframe (`_slice_by_mode_games`) on `season_end_year` or `game_date_est`.
  - Issue targeted `DELETE FROM games WHERE ...` before reloading slice.
- `dry_run=True`:
  - Logs intended row counts and exits; no writes.
- If no suitable CSV:
  - Logs warning, does not modify `games`.

---

### 2.2 `load_boxscore_team`

**Inputs**

- `LINE_SCORE_CSV` (`linescore.csv`)
- Optionally `OTHER_STATS_CSV` (`other_stats.csv`) (currently read, not joined in core path)
- DB:
  - `games(game_id, home_team_id, away_team_id)`
  - `teams(team_id, team_abbrev)`

**Outputs**

- Table: `boxscore_team`
- Grain:
  - One row per `(game_id, team_id)`
- Core columns:
  - At minimum: `game_id`, `team_id`, `pts`
  - Additional box score stats when available.

**Key Logic & FKs**

- Normalizes stats columns (FG, FGA, etc.) when present.
- Resolves `team_id`:
  - From `team_abbrev` via `TeamLookup.by_abbrev` (season-agnostic).
- Filters:
  - Keep only rows where `game_id` is in `GameLookup.by_game_id` (must exist in `games`).
  - Drop any rows missing `game_id` or `team_id` before load.
- Incremental:
  - For incremental modes, deletes existing `boxscore_team` rows for affected `game_id`s, then reloads subset.

**Failure Modes**

- Missing `linescore.csv`:
  - Logs warning; no changes to `boxscore_team`.
- After filtering, if no rows remain:
  - Logs info; skips load.

---

### 2.3 `load_games_and_boxscores`

**Role**

- Orchestrator:
  - Logs start/end with `etl_run_id`/`etl_run_step_id` (metadata only).
  - Invokes `load_games` then `load_boxscore_team` with consistent mode/dry-run options.
- No additional persistence logic beyond child functions.

---

## 3. `load_pbp.py`

### 3.1 `load_pbp_events`

**Inputs**

- CSV:
  - `PBP_CSV` (`play_by_play.csv`)
- DB dimensions:
  - `games(game_id)`
  - `players(player_id, slug, full_name, first_name, last_name)`
  - `teams(team_id, team_abbrev)`

**Outputs**

- Table: `pbp_events`
- Grain:
  - One row per `(game_id, eventnum)`

**Key Logic & FKs**

- Required columns:
  - `game_id`, `eventnum` required; if missing, loader aborts with warning.
- Filtering:
  - Keep only rows whose `game_id` exists in `games` (`GameLookup`).
- Clock:
  - Derives `clk_remaining` from `clk` (`MM:SS` → total seconds); best-effort.
- Teams:
  - `team_id`, `opponent_team_id` from `team_abbrev` / `opp_team_abbrev` using `TeamLookup.by_abbrev`.
- Players:
  - `player*_id` resolved via `resolve_player_id_from_name` using:
    - Raw numeric IDs where parseable.
    - Fallback to names.
- Descriptions:
  - If no `description`, concatenates `home_desc` / `away_desc`.
- Score:
  - If `score` column present, splits into `home_score` / `away_score`.
- Column normalization:
  - Ensures presence of:
    - `game_id`, `eventnum`, `period`, `clk`, `clk_remaining`, `event_type`,
      `option1`, `option2`, `option3`, `team_id`, `opponent_team_id`,
      `player1_id`, `player2_id`, `player3_id`,
      `description`, `score`, `home_score`, `away_score`
    - Missing columns initialized as `NULL`.

**Constraints & Invariants**

- Uniqueness:
  - Sorts by `(game_id, eventnum)` and keeps first row per key (deduplication).
- Load:
  - `TRUNCATE pbp_events`, then COPY full normalized dataset.
- Failure Modes:
  - Missing file → warning, skip.
  - No rows after filtering to known games → info, skip.
  - Malformed clock/score → nulls; loader continues.

---

## 4. `load_player_seasons.py`

### 4.1 `load_player_season_hub`

**Inputs**

- CSV:
  - `PLAYER_SEASON_INFO_CSV` (`playerseasoninfo.csv`)
- DB:
  - `players`, `teams`, `seasons` (dimension snapshots)

**Outputs**

- Table: `player_season`
- Grain:
  - One row per `seas_id` (from CSV)

**Key Logic & FKs**

- Normalization:
  - Renames and standardizes:
    - `seas_id`, `player_id`, `season` → `season_end_year`, `tm` → `team_abbrev`, etc.
- Flags:
  - `is_total`:
    - `team_abbrev == "TOT"`.
  - `is_league_average`:
    - `team_abbrev` text match `"league average"`.
  - `is_playoffs`:
    - Default `False`.
- Season FK:
  - `season_id` via `resolve_season_id(season_end_year, lg, season_lu)`.
- Team FK:
  - For non-TOT / non-league-average rows:
    - `team_id` via `resolve_team_id_from_abbrev(team_abbrev, season_end_year, team_lu)`.
  - For TOT / league-average:
    - `team_id = NULL` (explicit invariant).
- Required columns:
  - `seas_id`, `player_id`, `season_id`, `season_end_year`, `team_id`,
    `team_abbrev`, `lg`, `age`, `position`, `experience`,
    `is_total`, `is_league_average`, `is_playoffs`
  - Missing columns are added as `NULL`.

**Load Semantics**

- `TRUNCATE player_season CASCADE`
- COPY only normalized required columns.

---

### 4.2 Satellites

All satellites depend on existing hub rows.

**Shared helpers**

- `_load_hub_seas_ids`:
  - Reads all `seas_id` from `player_season`.
- `_filter_satellite(df, hub_seas_ids)`:
  - Keeps only rows with `seas_id` in hub set.

**Per-table behavior**

- `load_player_season_per_game`
  - Input: `PLAYER_PER_GAME_CSV`
  - Target: `player_season_per_game`
  - Process:
    - Filter to hub `seas_id`.
    - `TRUNCATE` then COPY all remaining columns.
- `load_player_season_totals`
  - Input: `PLAYER_TOTALS_CSV`
  - Target: `player_season_totals`
  - Same hub filter and load pattern.
- `load_player_season_per36`
  - Input: `PLAYER_PER36_CSV`
  - Target: `player_season_per36`
- `load_player_season_per100`
  - Input: `PLAYER_PER100_CSV`
  - Target: `player_season_per100`
- `load_player_season_advanced`
  - Input: `PLAYER_ADVANCED_CSV`
  - Target: `player_season_advanced`

**Invariants**

- Strict 1:1:
  - Satellites only for `seas_id` present in hub.
- Missing/mismatched:
  - Missing CSV → warning + skip.
  - No rows after filtering → info + skip, no table changes.

---

### 4.3 `load_all_player_seasons`

- Calls hub then all satellites in order.
- Assumes consistent schema and referential integrity as enforced by hub filter.

---

## 5. `load_team_seasons.py`

### 5.1 `load_team_season_hub`

**Inputs**

- CSV:
  - `TEAM_TOTALS_CSV` (`teamstats.csv`)
- DB:
  - `teams`, `seasons`

**Outputs**

- Table: `team_season`
- Grain:
  - Surrogate `team_season_id` (DB-generated) per `(team, season, flags)` combination.

**Key Logic & FKs**

- Normalization:
  - Map `season` → `season_end_year`; `tm` → `team_abbrev`.
- Flags:
  - `is_league_average` from `team_abbrev == 'League Average'` (case-insensitive).
  - `is_playoffs` default `False`.
- `season_id`:
  - via `resolve_season_id`.
- `team_id`:
  - via `resolve_team_id_from_abbrev` unless league-average (then `NULL`).
- Hub columns:
  - `team_id`, `season_id`, `season_end_year`, `lg`,
    `is_playoffs`, `is_league_average`, `team_abbrev`

**Construction Strategy**

1. `TRUNCATE team_season CASCADE`.
2. Build `hubs` = distinct combinations of hub columns.
3. Write `hubs` into temp table `tmp_team_season_hub`.
4. Insert distinct hubs into `team_season` and `RETURNING`:
   - `(team_id, season_id, season_end_year, is_playoffs, is_league_average, team_season_id)`.
5. Build mapping `(team_id, season_id, season_end_year, flags)` → `team_season_id`.
6. Attach `team_season_id` back to the in-memory `df`.
7. Persist `(season_end_year, team_abbrev, team_season_id)` into temp `tmp_team_season_map`
   for satellite loaders.

**Invariants**

- Unique `team_season_id` per logical key.
- League-average rows:
  - `team_id = NULL`, `is_league_average = TRUE`.

---

### 5.2 Satellites

**Shared helper**

- `_load_team_season_id_lookup`:
  - Reads `(season_end_year, team_abbrev, team_season_id)` from `tmp_team_season_map`.
- `_attach_team_season_id(df, lookup, season_col, team_abbrev_col)`:
  - Adds `team_season_id` via `(season, team_abbrev)` key; drops rows with unresolved IDs.

**Loader wrapper**

- `_load_team_season_satellite(config, conn, csv_name, table_name)`
  - Reads CSV.
  - Resolves `team_season_id`.
  - If no valid rows: logs and skips.
  - Else: `TRUNCATE table_name` and COPY.

**Satellites**

- `load_team_season_satellites` orchestrates:
  - `team_season_totals`, `team_season_per_game`, `team_season_per100`,
    `team_season_opponent_totals`, `team_season_opponent_per_game`,
    `team_season_opponent_per100`.

**Invariants**

- Satellites only loaded for `(season, team)` combinations that exist in hub.
- Rows without resolvable mapping are dropped (protects FK integrity).

---

### 5.3 `load_all_team_seasons`

- Orchestrates `load_team_season_hub` then satellites.
- Relies on temp map lifetime within same DB session.

---

## 6. `load_awards_and_draft.py`

### 6.1 Shared Concepts

**Inputs**

- CSVs:
  - `AWARDS_ALL_STAR_CSV`
  - `AWARDS_PLAYER_SHARES_CSV`
  - `AWARDS_END_OF_SEASON_TEAMS_CSV`
  - `AWARDS_END_OF_SEASON_VOTING_CSV`
  - `DRAFT_PICKS_CSV`
- DB:
  - Dimensions `players`, `teams`, `seasons`.

**Lookups**

- `_build_dimension_lookups`:
  - Builds `PlayerLookup`, `TeamLookup`, `SeasonLookup`.
- Helper resolvers:
  - `_resolve_player`, `_resolve_team`, `_resolve_season`.

**Resolution Rules**

- Prefer numeric IDs from CSV if parseable.
- Otherwise:
  - Resolve via name/abbrev/season using id_resolution.
- On unresolved:
  - Leave FKs `NULL` unless table constraints demand otherwise.
- Missing CSV:
  - Log and skip; table untouched.

---

### 6.2 Awards Loaders

1. `load_awards_all_star`
   - Target: `awards_all_star_selections`
   - Ensures:
     - `season_end_year`, `lg` → `season_id`
     - Player via `_resolve_player`
   - Required minimal columns:
     - `season_id`, `season_end_year`, `player_id`
   - Process:
     - `TRUNCATE` then COPY normalized subset.

2. `load_awards_player_shares`
   - Target: `awards_player_shares`
   - Similar mapping for `season_id` and `player_id`.
   - Keeps measure columns intact.
   - `TRUNCATE` then COPY.

3. `load_awards_end_of_season_teams`
   - Target: `awards_end_of_season_teams`
   - Resolves `season_id`, `player_id`.
   - `TRUNCATE` then COPY.

4. `load_awards_end_of_season_voting`
   - Target: `awards_end_of_season_voting`
   - Same resolution flow.
   - `TRUNCATE` then COPY.

---

### 6.3 `load_draft_picks`

- Target: `draft_picks`
- Mapping:
  - `season` → `season_end_year`
  - `lg` → `lg`
  - `player` → `player_name`
  - `player_id` → `player_id_raw`
  - `team` → `team_abbrev`
- Resolutions:
  - `season_id` via `_resolve_season`.
  - `player_id` via `_resolve_player`.
  - `team_id` via `_resolve_team` (team abbrev + season).
- Load:
  - `TRUNCATE draft_picks`
  - COPY full frame including resolved IDs.

**Invariants**

- Where IDs cannot be resolved:
  - FKs remain `NULL`; rows are preserved unless DB constraints reject them.
- Emphasis is on:
  - Deterministic, best-effort linkage.
  - No arbitrary row drops solely due to lookup gaps.

---

### 6.4 `load_all_awards_and_draft`

- Orchestrator:
  - Sequentially invokes all awards/draft loaders.
  - No extra logic; relies on per-loader contracts.

---

## 7. Summary: Cross-Loader Invariants

1. **Hub → Satellite Discipline**
   - Player and team season satellites are strictly keyed to existing hub rows.
   - Temporary maps (for team_season) and hub `seas_id` sets enforce consistency.

2. **ID Resolution**
   - Centralized in [`etl/id_resolution.py`](../../../etl/id_resolution.py:1).
   - Strong identifiers prioritized; fallbacks are deterministic and non-fuzzy.

3. **Foreign Keys**
   - Upstream loaders:
     - Populate FKs where resolvable.
     - Avoid inserting clearly invalid references (e.g., filter PBP by known games).
   - Remaining validation:
     - Handled by [`etl/validate_data.py`](../../../etl/validate_data.py:1) and related modules.

4. **Failure & Missing Data Handling**
   - Missing inputs:
     - Log + skip; no silent partial loads.
   - Incremental modes:
     - Conservative delete+reload of targeted slices.
   - Dry-run:
     - Read + log only; no writes.

5. **Runtime Behavior Guarantees (Track 1 Constraint)**
   - All behavior described reflects existing code:
     - No schema modifications.
     - No changes to contracts or control flow.
   - This artifact is an audit map consumable by downstream analysis and validation tasks.
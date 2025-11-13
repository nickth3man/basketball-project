# Migrations Map (Track 1)

Chronological, descriptive summary of structural changes from:

- [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:1)
- [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:1)
- [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:1)
- Supporting reference: [db/schema.sql](db/schema.sql:1)

This map is derived solely from committed SQL. It introduces no new behavior.

---

## 1. Chronological Summary

### 1. `001_initial_schema.sql` — Core Warehouse Schema

**Role:** Establishes the canonical Phase 1 schema for core entities and fact-style tables.

**Key Objects (structural):**

- **Core Dimensions**
  - `players`  
    - PK: `player_id`.  
    - Attributes: identity, names, bio, physicals, activity flags.
  - `player_aliases`  
    - PK: `player_alias_id`; FK to `players(player_id)`.  
    - Supports alternate names/slugs.
  - `teams`  
    - PK: `team_id`; unique `team_abbrev`.
  - `team_history`  
    - PK: `team_history_id`; FK to `teams(team_id)`; season-specific naming/location.
  - `team_abbrev_mappings`  
    - PK: `mapping_id`; optional FK to `teams(team_id)`; normalizes raw abbreviations.
  - `seasons`  
    - PK: `season_id`; unique `(season_end_year, COALESCE(lg, 'NBA'))`.

- **Games & Box Scores**
  - `games`  
    - PK: `game_id`.  
    - Links to `seasons` and `teams` for home/away; BRIN index on `game_date_est`.
  - `boxscore_team`  
    - PK: `(game_id, team_id)`; FKs into `games`, `teams`; BRIN index on `game_id`.
  - `boxscore_player`  
    - PK: `(game_id, player_id, team_id)`; FKs into `games`, `players`, `teams`.

- **Play-by-Play**
  - `pbp_events`  
    - PK: `(game_id, eventnum)`; references `games`, `players`, `teams` where available; BRIN index on `game_id`.

- **Player-Season Hub & Satellites**
  - `player_season`  
    - PK: `seas_id`; links to `players`, `teams`, `seasons`; flags for TOT, league-average, playoffs.
  - `player_season_per_game`, `player_season_totals`,
    `player_season_per36`, `player_season_per100`, `player_season_advanced`  
    - PK: `seas_id`; each FK to `player_season(seas_id)`; store granular and advanced stats.

- **Team-Season Hub & Satellites**
  - `team_season`  
    - PK: `team_season_id`; links to `teams`, `seasons`; uniqueness index for `(team_id, season_end_year, is_playoffs)`.
  - `team_season_totals`, `team_season_per_game`  
    - PK: `team_season_id`; FK to `team_season(team_season_id)`.
  - Other satellites referenced in docs/views (`team_season_per100`,
    `team_season_opponent_totals`, etc.) are conceptually part of this layer; concrete DDL
    must be confirmed from the full file contents in this repo.

**Impact Areas:**

- **Core entities:** players, teams, seasons.
- **Game facts:** games, boxscore_team, boxscore_player, pbp_events.
- **Seasonal analytics grain:** player_season hub + satellites, team_season hub + satellites.
- **Downstream:** forms the basis assumed by ETL loaders and API queries.

**Change Character:** Additive baseline (first migration); no destructive ops.

---

### 2. `002_advanced_views.sql` — Analytical Views

**Role:** Adds derived views on top of the existing `player_season` and `team_season` structures.
No base tables are created or dropped.

**Key Objects (structural):**

- `vw_player_season_advanced`
  - Joins:
    - `player_season` (`ps`)
    - `players` (`p`)
    - `player_season_totals` (`pst`)
    - `player_season_per_game` (`pspg`)
    - `player_season_advanced` (`psa`)
  - Exposes:
    - Player identity, season/team context, usage flags.
    - Per-game box score stats.
    - Shooting percentages (FG%, 3P%, FT%, TS%, eFG%).
    - Advanced metrics (PER, WS, WS/48, BPM, OBPM, DBPM).

- `vw_team_season_advanced`
  - Joins:
    - `team_season` (`ts`)
    - `teams` (`t`)
    - `team_season_totals` (`tst`)
    - `team_season_opponent_totals` (`topt`)
  - Exposes:
    - Margin of victory, ORtg, DRtg, NRtg derived from totals and opponent data.
  - Assumes opponent metrics tables exist with required columns (see file note).

- `vw_player_career_aggregates`
  - Joins:
    - `player_season` (`ps`)
    - `players` (`p`)
    - `player_season_totals` (`pst`)
  - Exposes:
    - Aggregated counting stats and TS% at career level.

**Impact Areas:**

- **Analytics views:** Provide read-only, query-ready surfaces for:
  - Player-season advanced metrics.
  - Team-season advanced metrics.
  - Player career totals.
- **ETL/Validation:** Consumed by metrics validation
  - [etl/validate_metrics.py](etl/validate_metrics.py:169-285) checks values in these views.
- **API/Consumers:** Potentially consumed by read paths; no schema mutations.

**Change Character:** Purely additive views; safe to apply after `001`.

---

### 3. `003_etl_metadata.sql` — ETL Metadata & Observability

**Role:** Introduces standardized ETL run tracking tables.
Mirrored in [db/schema.sql](db/schema.sql:15-60) for one-shot bootstrap.

**Key Objects (structural):**

- `etl_runs`
  - PK: `etl_run_id BIGSERIAL`.
  - Tracks:
    - `job_name`, `mode`, `params`, `status`,
    - `started_at`, `finished_at`, `message`,
    - `created_by`, `expectations_version`.

- `etl_run_steps`
  - PK: `etl_run_step_id BIGSERIAL`.
  - FK: `etl_run_id` → `etl_runs(etl_run_id)` ON DELETE CASCADE.
  - Tracks:
    - `step_name`, `loader_module`, `status`,
    - timings, row counts, `input_files`, `output_tables`, `error_message`.

- `etl_run_issues`
  - PK: `etl_run_issue_id BIGSERIAL`.
  - FK: `etl_run_id` → `etl_runs(etl_run_id)` ON DELETE CASCADE.
  - Tracks:
    - `source_type`, `source_id`, `issue_type`,
    - `severity`, `details`, `step_name`, `created_at`.

**Impact Areas:**

- **ETL metadata & observability:**
  - Used by ETL and validation tooling for:
    - Run bookkeeping,
    - Drift/issues logging,
    - Non-invasive monitoring.
- **No impact** on logical fact/dimension schemas.

**Change Character:** Additive-only; no modifications to existing tables or views.

---

## 2. Highlights by Concern

### 2.1 Core Entities & Facts

- Defined in `001`:
  - Players, teams, seasons.
  - Games, boxscore_team, boxscore_player.
  - PBP events.
  - Player-season hub and satellites.
  - Team-season hub and satellites (plus referenced opponent variants).
- Subsequent migrations do **not** alter these core table structures destructively.

### 2.2 Analytics Views

- Introduced exclusively in `002`:
  - `vw_player_season_advanced`
  - `vw_team_season_advanced`
  - `vw_player_career_aggregates`
- These:
  - Depend on existing hub/satellite tables.
  - Are referenced by validation logic for metrics sanity checks.

### 2.3 ETL Metadata & Validation Support

- Introduced exclusively in `003`:
  - `etl_runs`, `etl_run_steps`, `etl_run_issues`.
- Align with:
  - Expectations and schema drift utilities:
    - [etl/expectations_loader.py](etl/expectations_loader.py:89-147)
    - [etl/schema_drift.py](etl/schema_drift.py:334-371)
  - General ETL/validation reporting (no changes to domain data paths).

---

## 3. Usage Notes

1. **Additive Evolution**
   - All visible migrations are additive:
     - `001` establishes schema.
     - `002` adds views.
     - `003` adds metadata tables.
   - No `DROP TABLE` or destructive `ALTER` against core entities in these files.

2. **Alignment with `db/schema.sql`**
   - [db/schema.sql](db/schema.sql:1) is documented as a convenience snapshot:
     - It explicitly mirrors `003` ETL metadata tables.
     - Comments indicate prior schema is assumed defined above; actual canonical
       evolution remains `001` → `002` → `003`.

3. **Implications for API / Tools / ETL**
   - ETL loaders and validators assume:
     - The `001` tables exist with their declared keys.
     - The `002` views are present for advanced/metrics checks.
     - The `003` metadata tables are available for run/issue tracking.
   - This migrations map can be used to:
     - Verify environment setup sequences.
     - Confirm no unexpected behavioral changes are introduced by audit artifacts.

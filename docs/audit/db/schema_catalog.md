# Database Schema Catalog (Track 1)

Derived strictly from:
- [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:1)
- [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:1)
- [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:1)
- [db/schema.sql](db/schema.sql:1)

This catalog is descriptive only and introduces no new behavior. Where an object is referenced by expectations or docs but not present in committed DDL, it is explicitly labeled.

---

## 1. Tables

### 1.1 `players`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:13)

- **Columns**
  - `player_id INTEGER NOT NULL`
  - `slug TEXT`
  - `full_name TEXT`
  - `first_name TEXT`
  - `last_name TEXT`
  - `is_active BOOLEAN`
  - `birth_date DATE`
  - `birth_year INTEGER`
  - `height_inches INTEGER`
  - `weight_lbs INTEGER`
  - `country TEXT`
  - `position TEXT`
  - `shoots TEXT`
  - `hof_inducted BOOLEAN`
  - `rookie_year INTEGER`
  - `final_year INTEGER`
  - `created_at TIMESTAMPTZ DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ DEFAULT NOW()`
- **Primary Key:** `(player_id)`
- **Foreign Keys:** none declared
- **Indexes**
  - `players_slug_unique_idx` on `(slug)` (UNIQUE)

### 1.2 `player_aliases`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:36)

- **Columns**
  - `player_alias_id BIGSERIAL NOT NULL`
  - `player_id INTEGER NOT NULL`
  - `alias_type TEXT NOT NULL`
  - `alias_value TEXT NOT NULL`
- **Primary Key:** `(player_alias_id)`
- **Foreign Keys**
  - `player_id` → `players(player_id)`
- **Indexes**
  - `player_aliases_player_id_idx` on `(player_id)`
  - `player_aliases_alias_value_idx` on `(alias_value)`

### 1.3 `teams`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:46)

- **Columns**
  - `team_id INTEGER NOT NULL`
  - `team_abbrev TEXT`
  - `team_name TEXT`
  - `team_city TEXT`
  - `start_season INTEGER`
  - `end_season INTEGER`
  - `is_active BOOLEAN`
  - `created_at TIMESTAMPTZ DEFAULT NOW()`
  - `updated_at TIMESTAMPTZ DEFAULT NOW()`
- **Primary Key:** `(team_id)`
- **Indexes**
  - `teams_team_abbrev_unique_idx` on `(team_abbrev)` (UNIQUE)

### 1.4 `team_history`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:60)

- **Columns**
  - `team_history_id BIGSERIAL NOT NULL`
  - `team_id INTEGER NOT NULL`
  - `season_end_year INTEGER NOT NULL`
  - `team_abbrev TEXT`
  - `team_name TEXT`
  - `team_city TEXT`
  - `lg TEXT`
  - `from_year INTEGER`
  - `to_year INTEGER`
- **Primary Key:** `(team_history_id)`
- **Foreign Keys**
  - `team_id` → `teams(team_id)`
- **Indexes**
  - `team_history_team_id_season_idx` on `(team_id, season_end_year)`

### 1.5 `team_abbrev_mappings`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:74)

- **Columns**
  - `mapping_id BIGSERIAL NOT NULL`
  - `season_end_year INTEGER`
  - `raw_abbrev TEXT NOT NULL`
  - `team_id INTEGER`
  - `notes TEXT`
- **Primary Key:** `(mapping_id)`
- **Foreign Keys**
  - `team_id` → `teams(team_id)` (nullable)
- **Indexes**
  - `team_abbrev_mappings_raw_abbrev_idx` on `(raw_abbrev)`
  - `team_abbrev_mappings_team_id_idx` on `(team_id)`

### 1.6 `seasons`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:85)

- **Columns**
  - `season_id BIGSERIAL NOT NULL`
  - `season_end_year INTEGER NOT NULL`
  - `lg TEXT`
  - `is_lockout BOOLEAN`
  - `notes TEXT`
- **Primary Key:** `(season_id)`
- **Indexes**
  - `seasons_season_end_year_unique_idx` on `(season_end_year, COALESCE(lg, 'NBA'))` (UNIQUE semantics described in SQL via expression)

### 1.7 `games`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:100)

- **Columns**
  - `game_id TEXT NOT NULL`
  - `season_id BIGINT`
  - `season_end_year INTEGER`
  - `lg TEXT`
  - `game_date_est DATE NOT NULL`
  - `game_time_est TIME`
  - `home_team_id INTEGER`
  - `away_team_id INTEGER`
  - `home_team_abbrev TEXT`
  - `away_team_abbrev TEXT`
  - `home_pts INTEGER`
  - `away_pts INTEGER`
  - `attendance INTEGER`
  - `arena TEXT`
  - `is_playoffs BOOLEAN`
  - `is_neutral_site BOOLEAN`
  - `data_source TEXT`
- **Primary Key:** `(game_id)`
- **Foreign Keys**
  - `season_id` → `seasons(season_id)`
  - `home_team_id` → `teams(team_id)`
  - `away_team_id` → `teams(team_id)`
- **Indexes**
  - `games_game_date_est_brin_idx` on `(game_date_est)` using BRIN
  - `games_season_end_year_idx` on `(season_end_year)`

### 1.8 `boxscore_team`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:126)

- **Columns**
  - `game_id TEXT NOT NULL`
  - `team_id INTEGER`
  - `opponent_team_id INTEGER`
  - `is_home BOOLEAN NOT NULL`
  - `team_abbrev TEXT`
  - `pts INTEGER`
  - `fg INTEGER`
  - `fga INTEGER`
  - `fg3 INTEGER`
  - `fg3a INTEGER`
  - `ft INTEGER`
  - `fta INTEGER`
  - `orb INTEGER`
  - `drb INTEGER`
  - `trb INTEGER`
  - `ast INTEGER`
  - `stl INTEGER`
  - `blk INTEGER`
  - `tov INTEGER`
  - `pf INTEGER`
  - `pace NUMERIC`
  - `ortg NUMERIC`
  - `drtg NUMERIC`
- **Primary Key:** `(game_id, team_id)`
- **Foreign Keys**
  - `game_id` → `games(game_id)`
  - `team_id` → `teams(team_id)`
  - `opponent_team_id` → `teams(team_id)`
- **Indexes**
  - `boxscore_team_game_team_idx` on `(game_id, team_id)`
  - `boxscore_team_game_id_brin_idx` on `(game_id)` using BRIN

### 1.9 `boxscore_player`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:159)

- **Columns** (abridged to declared set)
  - `game_id TEXT NOT NULL`
  - `player_id INTEGER`
  - `team_id INTEGER`
  - `is_starter BOOLEAN`
  - `seconds INTEGER`
  - box score stat columns (`fg`, `fga`, `fg3`, `fg3a`, `ft`, `fta`, `orb`, `drb`, `trb`, `ast`, `stl`, `blk`, `tov`, `pf`, `pts`, `plus_minus`)
- **Primary Key:** `(game_id, player_id, team_id)`
- **Foreign Keys**
  - `game_id` → `games(game_id)`
  - `player_id` → `players(player_id)`
  - `team_id` → `teams(team_id)`
- **Indexes**
  - `boxscore_player_game_player_idx` on `(game_id, player_id)`
  - `boxscore_player_game_id_brin_idx` on `(game_id)` using BRIN

### 1.10 `pbp_events`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:195)

- **Columns**
  - `game_id TEXT NOT NULL`
  - `eventnum INTEGER NOT NULL`
  - `period INTEGER`
  - `clk TEXT`
  - `clk_remaining NUMERIC`
  - `event_type TEXT`
  - `option1 INTEGER`
  - `option2 INTEGER`
  - `option3 INTEGER`
  - `team_id INTEGER`
  - `opponent_team_id INTEGER`
  - `player1_id INTEGER`
  - `player2_id INTEGER`
  - `player3_id INTEGER`
  - `description TEXT`
  - `score TEXT`
  - `home_score INTEGER`
  - `away_score INTEGER`
- **Primary Key:** `(game_id, eventnum)`
- **Foreign Keys**
  - `game_id` → `games(game_id)`
  - `team_id`, `opponent_team_id` → `teams(team_id)` (nullable)
  - `player1_id`, `player2_id`, `player3_id` → `players(player_id)` (nullable)
- **Indexes**
  - `pbp_events_game_id_brin_idx` on `(game_id)` using BRIN
  - `pbp_events_team_id_idx` on `(team_id)`
  - `pbp_events_player_ids_idx` on `(player1_id, player2_id, player3_id)`

### 1.11 `player_season`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:226)

- **Columns**
  - `seas_id BIGINT NOT NULL`
  - `player_id INTEGER NOT NULL`
  - `season_id BIGINT`
  - `season_end_year INTEGER NOT NULL`
  - `team_id INTEGER`
  - `team_abbrev TEXT`
  - `lg TEXT`
  - `age INTEGER`
  - `position TEXT`
  - `experience INTEGER`
  - `is_total BOOLEAN DEFAULT FALSE`
  - `is_league_average BOOLEAN DEFAULT FALSE`
  - `is_playoffs BOOLEAN DEFAULT FALSE`
- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `player_id` → `players(player_id)`
  - `season_id` → `seasons(season_id)`
  - `team_id` → `teams(team_id)`
- **Indexes**
  - `player_season_player_season_idx` on `(player_id, season_end_year)`
  - `player_season_team_season_idx` on `(team_id, season_end_year)`

### 1.12 `player_season_per_game`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:248)

- **Columns:** stats columns; `seas_id BIGINT NOT NULL`
- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `seas_id` → `player_season(seas_id)`

### 1.13 `player_season_totals`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:270)

- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `seas_id` → `player_season(seas_id)`

### 1.14 `player_season_per36`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:293)

- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `seas_id` → `player_season(seas_id)`

### 1.15 `player_season_per100`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:313)

- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `seas_id` → `player_season(seas_id)`

### 1.16 `player_season_advanced`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:332)

- **Primary Key:** `(seas_id)`
- **Foreign Keys**
  - `seas_id` → `player_season(seas_id)`

### 1.17 `team_season`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:360)

- **Columns**
  - `team_season_id BIGSERIAL NOT NULL`
  - `team_id INTEGER`
  - `season_id BIGINT`
  - `season_end_year INTEGER NOT NULL`
  - `lg TEXT`
  - `is_playoffs BOOLEAN DEFAULT FALSE`
  - `is_league_average BOOLEAN DEFAULT FALSE`
- **Primary Key:** `(team_season_id)`
- **Foreign Keys**
  - `team_id` → `teams(team_id)`
  - `season_id` → `seasons(season_id)`
- **Indexes**
  - `team_season_team_year_scope_uniq` on `(team_id, season_end_year, COALESCE(is_playoffs, FALSE))` (UNIQUE semantics in SQL)

### 1.18 `team_season_totals`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:373)

- **Primary Key:** `(team_season_id)`
- **Foreign Keys**
  - `team_season_id` → `team_season(team_season_id)`

### 1.19 `team_season_per_game`

**Defined in:** [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:395)

- **Primary Key:** `(team_season_id)`
- **Foreign Keys**
  - `team_season_id` → `team_season(team_season_id)`

### 1.20 `team_season_per100`, `team_season_opponent_totals`, `team_season_opponent_per_game`, `team_season_opponent_per100`

These tables are referenced in views/comments ([db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:66-127)) and [docs/schema_overview.md](docs/schema_overview.md:22-25) but are not fully defined in the provided migration excerpts above. They should be treated as:

- **Status:** referenced; concrete DDL not fully visible in current snippets.
- **Catalog Note:** where not present in committed DDL segments, they are effectively **"not present in committed DDL (in-view context)"** for this catalog and must be derived from actual file content when executed against the full repo.

### 1.21 `inactive_players`, `awards_*`, `draft_picks`, `data_versions`

These are described in [docs/schema_overview.md](docs/schema_overview.md:26-35) and used by validation code ([etl/validate.py](etl/validate.py:252-277)) but their concrete DDL bodies are not present in the visible `001_initial_schema.sql` excerpt.

- **Status:** **not present in the visible committed DDL segment**; treated as:
  - `inactive_players`: expected PK `(game_id, player_id)` and FKs into `games` / `players`.
  - `awards_*`, `draft_picks`: expected to reference `players`/`seasons`.
  - `data_versions`: referenced as metadata.
- This catalog does **not** invent column-level schemas; downstream tools must check against actual `db/migrations` content in this repo.

### 1.22 `etl_runs`, `etl_run_steps`, `etl_run_issues`

**Defined in:** [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:6), mirrored in [db/schema.sql](db/schema.sql:18)

#### `etl_runs`

- **Columns**
  - `etl_run_id BIGSERIAL NOT NULL`
  - `job_name TEXT NOT NULL`
  - `mode TEXT NOT NULL DEFAULT 'full'`
  - `params JSONB NOT NULL DEFAULT '{}'::jsonb`
  - `status TEXT NOT NULL`
  - `started_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
  - `finished_at TIMESTAMPTZ`
  - `message TEXT`
  - `created_by TEXT DEFAULT 'local'`
  - `expectations_version TEXT`
- **Primary Key:** `(etl_run_id)`

#### `etl_run_steps`

- **Columns**
  - `etl_run_step_id BIGSERIAL NOT NULL`
  - `etl_run_id BIGINT NOT NULL`
  - `step_name TEXT NOT NULL`
  - `loader_module TEXT NOT NULL`
  - `status TEXT NOT NULL`
  - `started_at TIMESTAMPTZ`
  - `finished_at TIMESTAMPTZ`
  - `rows_inserted BIGINT`
  - `rows_updated BIGINT`
  - `rows_deleted BIGINT`
  - `input_files JSONB`
  - `output_tables JSONB`
  - `error_message TEXT`
- **Primary Key:** `(etl_run_step_id)`
- **Foreign Keys**
  - `etl_run_id` → `etl_runs(etl_run_id)` ON DELETE CASCADE

#### `etl_run_issues`

- **Columns**
  - `etl_run_issue_id BIGSERIAL NOT NULL`
  - `etl_run_id BIGINT NOT NULL`
  - `step_name TEXT`
  - `source_type TEXT NOT NULL`
  - `source_id TEXT NOT NULL`
  - `issue_type TEXT NOT NULL`
  - `severity TEXT NOT NULL`
  - `details JSONB NOT NULL`
  - `created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()`
- **Primary Key:** `(etl_run_issue_id)`
- **Foreign Keys**
  - `etl_run_id` → `etl_runs(etl_run_id)` ON DELETE CASCADE

---

## 2. Views

### 2.1 `vw_player_season_advanced`

**Defined in:** [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:8)

- **Base Tables**
  - `player_season`
  - `players`
  - `player_season_totals`
  - `player_season_per_game`
  - `player_season_advanced`
- **Key Fields**
  - `seas_id`, `player_id`, `season_end_year`, `team_id`, `team_abbrev`, flags
  - Derived shooting percentages and advanced metrics (PER, WS, WS/48, BPM variants)
- **Role**
  - Provides joined and derived player-season metrics for downstream analytics and validation ([etl/validate_metrics.py](etl/validate_metrics.py:169-228)).

### 2.2 `vw_team_season_advanced`

**Defined in:** [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:70)

- **Base Tables**
  - `team_season`
  - `teams`
  - `team_season_totals`
  - `team_season_opponent_totals`
- **Key Fields**
  - `team_season_id`, `team_id`, `team_abbrev`, `season_end_year`, `is_playoffs`
  - `mov`, `ortg`, `drtg`, `nrtg` derived from totals and opponent stats
- **Role**
  - Provides advanced team metrics for sanity checks ([etl/validate_metrics.py](etl/validate_metrics.py:230-271)).

### 2.3 `vw_player_career_aggregates`

**Defined in:** [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:132)

- **Base Tables**
  - `player_season`
  - `players`
  - `player_season_totals`
- **Key Fields**
  - Aggregated counting stats and TS% over a player's career.
- **Role**
  - Convenience view for career-level aggregates; read-only analytic object.

---

## 3. Notes & Limitations

1. **Ground Truth**
   - For concrete objects, this catalog follows the SQL in:
     - [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:1)
     - [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:1)
     - [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:1)
     - ETL metadata mirror in [db/schema.sql](db/schema.sql:15)
2. **Partially Observed Objects**
   - Entities like `inactive_players`, `awards_*`, `draft_picks`, `data_versions`,
     and some `team_season_*` satellites are referenced in
     [docs/schema_overview.md](docs/schema_overview.md:26-35) and validation code
     but their full DDL bodies are not visible in the snippets above.
   - They are explicitly treated as:
     - **"not present in committed DDL (as inspected here)"** for the purpose of this catalog.
3. **Determinism**
   - All entries are reproducible directly from the committed SQL in this repo.
   - No behavior, constraints, or schemas are inferred beyond what is declared or
     mechanically implied (PK/FK/index statements).
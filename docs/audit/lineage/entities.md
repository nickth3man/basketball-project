# Entity-Centric Lineage

Derived strictly from:

- CSV inventory: [docs/phase_0_csv_inventory.json](docs/phase_0_csv_inventory.json:1)
- Loaders:
  - [etl/load_dimensions.py](etl/load_dimensions.py:1)
  - [etl/load_games_and_boxscores.py](etl/load_games_and_boxscores.py:1)
  - [etl/load_pbp.py](etl/load_pbp.py:1)
  - [etl/load_player_seasons.py](etl/load_player_seasons.py:1)
  - [etl/load_team_seasons.py](etl/load_team_seasons.py:1)
  - [etl/load_awards_and_draft.py](etl/load_awards_and_draft.py:1)
  - [etl/load_inactive.py](etl/load_inactive.py:1)
  - [etl/load_metadata.py](etl/load_metadata.py:1)
- Schema:
  - [.rooroo/audit/db/schema_catalog.md](.rooroo/audit/db/schema_catalog.md:1)
- CSV-to-DB lineage:
  - [.rooroo/audit/lineage/csv_to_db.md](.rooroo/audit/lineage/csv_to_db.md:1)
- Validations:
  - [.rooroo/audit/etl/modules/validations_overview.md](.rooroo/audit/etl/modules/validations_overview.md:1)

This is a **read-only narrative graph**: sources → ETL modules → tables/views → (where visible) usage.  
No new behavior or assumptions are introduced.

Format per entity:

- `sources` — concrete CSVs / inputs as wired in code.
- `etl` — loader functions and key transformations.
- `db` — target tables/views.
- `usage` — only when explicitly visible in code/docs; otherwise labeled as not observable.

---

## 1. Players

**Sources (examples from inventory and loaders)**

- `csv_files/player.csv`
- `csv_files/playerdirectory.csv`
- `csv_files/common_player_info.csv`
- Other player-related CSVs referenced via [etl/paths.py](etl/paths.py:1) (see csv_to_db lineage).

**ETL**

- [etl/load_dimensions.py](etl/load_dimensions.py:1)
  - `load_players`
    - Reads core player CSVs.
    - Normalizes IDs and attributes.
    - Inserts/updates `players`.
  - `load_player_aliases`
    - Consumes slug/name variants.
    - Populates `player_aliases`.

**DB Targets**

- `players`
- `player_aliases`

**Usage (observable)**

- Referenced by:
  - `games`, `boxscore_player`, `pbp_events`, `player_season`, awards/draft tables.
  - Advanced views:
    - `vw_player_season_advanced`
    - `vw_player_career_aggregates`
- Validated by:
  - Structural/FK checks in `validate_data.py` and `validate.py`.
- **Downstream API/metrics usage beyond this schema:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 2. Teams

**Sources**

- Team master and mapping CSVs (per [docs/phase_0_csv_inventory.json](docs/phase_0_csv_inventory.json:39-103) and [etl/paths.py](etl/paths.py:1)).

**ETL**

- [etl/load_dimensions.py](etl/load_dimensions.py:1)
  - `load_teams` → `teams`
  - `load_team_history` → `team_history`
  - `load_team_abbrev_mappings` → `team_abbrev_mappings`

**DB Targets**

- `teams`
- `team_history`
- `team_abbrev_mappings`

**Usage**

- `teams` used as FK target in `games`, `boxscore_team`, `boxscore_player`, `pbp_events`, `team_season`.
- `team_history` / `team_abbrev_mappings` support ID resolution.
- Validations:
  - Core existence and FK coverage in `validate_data.py` / `validate.py`.
- **Additional consumer logic (APIs, UIs):** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 3. Games & Boxscores

**Sources**

- Game and boxscore CSVs (games schedule, line scores, etc.) wired via:
  - [etl/load_games_and_boxscores.py](etl/load_games_and_boxscores.py:1)
  - [etl/paths.py](etl/paths.py:1)

**ETL**

- `load_games_and_boxscores` (and helpers)
  - Reads game-level CSVs.
  - Populates:
    - `games`
    - `boxscore_team`
  - Player-level boxscores handled where implemented (`boxscore_player`).

**DB Targets**

- `games`
- `boxscore_team`
- `boxscore_player`

**Usage**

- FKs into `players`, `teams`, `seasons`.
- Upstream for:
  - `pbp_events`
  - Player/team season derivations.
- Validation:
  - Structural + referential checks in `validate_data.py` and `validate.py`.
- **Analytic/endpoint details:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 4. Play-by-Play (PBP)

**Sources**

- PBP CSVs listed in inventory and resolved via [etl/paths.py](etl/paths.py:1).

**ETL**

- [etl/load_pbp.py](etl/load_pbp.py:1)
  - `load_pbp_events`
    - Normalizes events.
    - Ensures uniqueness on `(game_id, eventnum)`.
    - Writes into `pbp_events`.

**DB Targets**

- `pbp_events`

**Usage**

- Tied to:
  - `games` (FK), `teams`, `players`.
- Validation:
  - FK checks in `validate_data.py` / `validate.py`.
- **Higher-level consumption (e.g., APIs, derived metrics):** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 5. Player Seasons

**Sources**

- Player season CSVs:
  - Hub: season identifiers and context.
  - Satellites: per-game, totals, per36, per100, advanced stats.
  - Resolved via [etl/paths.py](etl/paths.py:1) and inventory.

**ETL**

- [etl/load_player_seasons.py](etl/load_player_seasons.py:1)
  - `load_player_season_hub`
    - Builds `player_season` hub from season info CSVs.
  - `load_player_season_per_game`
  - `load_player_season_totals`
  - `load_player_season_per36`
  - `load_player_season_per100`
  - `load_player_season_advanced`
    - Each:
      - Filters to existing hub `seas_id` via `_load_hub_seas_ids` / `_filter_satellite`.
      - Truncates and reloads corresponding satellite.

**DB Targets**

- `player_season`
- `player_season_per_game`
- `player_season_totals`
- `player_season_per36`
- `player_season_per100`
- `player_season_advanced`

**Usage**

- Basis for:
  - `vw_player_season_advanced`
  - `vw_player_career_aggregates`
- Validations:
  - Hub/satellite consistency in `validate.py`.
  - Metrics integrity in `validate_metrics.py`.
- **Further downstream usage (APIs, tools):** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 6. Team Seasons

**Sources**

- Team season CSVs (standings, team stats, opponent stats) as wired in:
  - [etl/load_team_seasons.py](etl/load_team_seasons.py:1)
  - [etl/paths.py](etl/paths.py:1)

**ETL**

- `load_team_season_hub`
  - Builds `team_season`.
- Satellite loaders:
  - Populate `team_season_totals`, `team_season_per_game`, and related tables.
  - Use hub IDs/keys for referential integrity.

**DB Targets**

- `team_season`
- `team_season_totals`
- `team_season_per_game`
- Additional satellites where defined in repo migrations.

**Usage**

- Inputs to:
  - `vw_team_season_advanced`
- Validations:
  - Hub/satellite and metrics checks in `validate.py` and `validate_metrics.py`.
- **Other joins/consumers:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 7. Awards & Draft

**Sources**

- Awards CSVs (MVP, All-NBA, etc.).
- Draft CSVs.
  - As documented in [docs/phase_0_csv_inventory.json](docs/phase_0_csv_inventory.json:1).

**ETL**

- [etl/load_awards_and_draft.py](etl/load_awards_and_draft.py:1)
  - Dedicated functions load:
    - Awards CSVs → `awards_*` tables.
    - Draft CSVs → `draft_picks`.

**DB Targets**

- `awards_*` (several tables, see loader code)
- `draft_picks`

**Usage**

- Validations:
  - `validate.py` checks award/draft references against `players` where IDs/keys are present.
- **Further usage (metrics/features) not explicitly coded here:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 8. Inactive Players

**Sources**

- Inactive status CSVs (as referenced by [etl/load_inactive.py](etl/load_inactive.py:1)).

**ETL**

- `load_inactive_players`
  - Loads rows indicating inactive players per game.

**DB Targets**

- `inactive_players`

**Usage**

- Participates in integrity checks in `validate.py` where defined.
- **Other uses (UI, tools) not directly visible:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 9. ETL Metadata

**Sources**

- Runtime processes:
  - Orchestration scripts,
  - Validation/ETL modules.

**ETL**

- [etl/load_metadata.py](etl/load_metadata.py:1) and logging utilities
  - Insert into:
    - `etl_runs`
    - `etl_run_steps`
    - `etl_run_issues`

**DB Targets**

- `etl_runs`
- `etl_run_steps`
- `etl_run_issues`

**Usage**

- Consumed by:
  - Logging, monitoring, schema drift reporting.
- No strong expectations coverage (see expectations_gaps).
- **External observability consumers:** `usage_out_of_scope_or_not_observable_in_repo`.

---

## 10. Summary & Limitations

1. **End-to-End Shape**
   - For each core entity (players, teams, games, pbp, player_season, team_season, awards, draft, inactive, ETL metadata), this artifact traces:
     - Source CSVs → ETL loader functions → DB tables/views.
   - Where views (e.g., `vw_player_season_advanced`) depend on multiple tables, they are treated as downstream analytic surfaces of their respective hubs/satellites.

2. **No Hidden Assumptions**
   - All links are backed by:
     - Concrete loader imports,
     - Calls to `copy_from_polars` / `INSERT` into specific tables,
     - Declared schema relationships.
   - When the repo does not show a consumer:
     - We mark `usage_out_of_scope_or_not_observable_in_repo` rather than speculating.

3. **Determinism**
   - Recomputable solely from this repository’s SQL, Python ETL code, and docs.
   - Safe input for subsequent refactor/validation tasks without altering runtime behavior.
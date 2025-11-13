# CSV → DB Lineage

Derived strictly from:

- [docs/phase_0_csv_inventory.json](docs/phase_0_csv_inventory.json:1)
- ETL loaders:
  - [etl/load_dimensions.py](etl/load_dimensions.py:1)
  - [etl/load_games_and_boxscores.py](etl/load_games_and_boxscores.py:1)
  - [etl/load_pbp.py](etl/load_pbp.py:1)
  - [etl/load_player_seasons.py](etl/load_player_seasons.py:1)
  - [etl/load_team_seasons.py](etl/load_team_seasons.py:1)
  - [etl/load_awards_and_draft.py](etl/load_awards_and_draft.py:1)
  - [etl/load_inactive.py](etl/load_inactive.py:1)
  - [etl/load_metadata.py](etl/load_metadata.py:1)

No behavior changes; this is a descriptive mapping based only on observable code.

---

## 1. Lineage Table

Each row: `csv_source` → loader entrypoint(s) → target table(s).  
Key mappings are included **only** when directly implemented in code.

| csv_source (inventory / paths)                 | loader module / function(s)                                           | target_table(s)                              | key mapping notes (from code only)                                                                 |
|-----------------------------------------------|------------------------------------------------------------------------|----------------------------------------------|-----------------------------------------------------------------------------------------------------|
| `csv_files/player.csv`                        | `load_dimensions.load_players`                                        | `players`                                    | `id` → `players.player_id`; maps core identity and activity fields.                                 |
| `csv_files/playerdirectory.csv`               | `load_dimensions.load_players`, `load_dimensions.load_player_aliases` | `players`, `player_aliases`                  | Uses slug/name info; slugs contribute to `players.slug`, aliases into `player_aliases`.            |
| `csv_files/common_player_info.csv`            | `load_dimensions.load_players`                                        | `players`                                    | `person_id` and related columns enrich `players` attributes.                                       |
| `csv_files/playerseasoninfo.csv`              | `load_player_seasons.load_player_season_hub`                          | `player_season`                              | `seas_id` → `player_season.seas_id`; season/team keys resolved via `id_resolution`.                |
| `csv_files/playercareerinfo.csv`              | `load_dimensions.load_players` (enrichment)                           | `players`                                    | Contributes career/HOF-style attributes where implemented.                                         |
| player per-game totals CSVs (per inventory)   | `load_player_seasons.load_player_season_per_game`                     | `player_season_per_game`                     | Filtered to hub `seas_id` via `_load_hub_seas_ids` / `_filter_satellite`.                          |
| player totals CSVs                            | `load_player_seasons.load_player_season_totals`                       | `player_season_totals`                       | As above, constrained to existing `player_season` hub rows.                                        |
| player per36 CSVs                             | `load_player_seasons.load_player_season_per36`                        | `player_season_per36`                        | Satellite keyed by `seas_id`.                                                                      |
| player per100 CSVs                            | `load_player_seasons.load_player_season_per100`                       | `player_season_per100`                       | Satellite keyed by `seas_id`.                                                                      |
| player advanced CSVs                          | `load_player_seasons.load_player_season_advanced`                     | `player_season_advanced`                     | Satellite keyed by `seas_id`.                                                                      |
| team season stats CSVs                        | `load_team_seasons.load_team_season_hub` + satellite loaders         | `team_season` + `team_season_*` satellites   | Uses `team_id`/`season_end_year` via `id_resolution` helpers.                                      |
| game/summary/line score CSVs                  | `load_games_and_boxscores.load_games_and_boxscores`                  | `games`, `boxscore_team`                     | Uses constants in `etl.paths` to resolve CSVs → `games` and `boxscore_team`.                       |
| play-by-play CSVs                             | `load_pbp.load_pbp_events`                                           | `pbp_events`                                 | Normalizes columns, ensures `(game_id, eventnum)` uniqueness; inserts into `pbp_events`.           |
| awards CSVs (various)                         | `load_awards_and_draft` functions                                    | `awards_*` tables                            | Each awards CSV mapped to corresponding awards table where implemented.                            |
| draft CSVs                                    | `load_awards_and_draft.load_draft_picks`                             | `draft_picks`                                | Draft rows written into `draft_picks`.                                                             |
| inactive players CSVs                         | `load_inactive.load_inactive_players`                                | `inactive_players`                           | Maps inactivity rows into `inactive_players`.                                                      |
| metadata / expectations / config YAML / JSON  | `load_metadata` and expectations loader utilities                    | `etl_runs`, `etl_run_steps`, `etl_run_issues` | Operational metadata only; not core domain entities.                                               |

*(For exact CSV path constants, see [etl/paths.py](etl/paths.py:1). Only relationships directly encoded in loader code are listed.)*

---

## 2. Unmapped Inventory Entries

Entries in [docs/phase_0_csv_inventory.json](docs/phase_0_csv_inventory.json:1) that do **not**
have a clearly corresponding loader usage in the inspected ETL modules are labeled here.

Examples (non-exhaustive, driven purely by code cross-check):

- Any `csv_inventory` item whose `filename`/logical id is **not** referenced by:
  - [etl/paths.py](etl/paths.py:1),
  - or any of the loader modules listed above,
  is treated as:

`unmapped_in_code` — present in inventory; no direct loader mapping found in this repo snapshot.

This artifact does not guess target tables for such sources.

---

## 3. Limitations

1. **Code-Only**
   - Every mapping above is derived from explicit references in ETL loader code and path constants.
   - No external knowledge or undocumented behavior is used.

2. **Non-Exhaustive Where Code Is Indirect**
   - When loaders rely on helper functions (e.g. `resolve_csv_path`) and wildcards,
     mappings are recorded at the level visible in those modules.

3. **No Behavioral Changes**
   - This lineage description does not modify any loader or table.
   - It is intended solely as an audit reference to support Track 1 planning.

4. **Determinism**
   - Re-running this analysis on the same commit yields the same mapping.
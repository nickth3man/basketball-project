# Schema vs Docs Inconsistencies

Comparison between:

- Ground truth DDL:
  - [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:1)
  - [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:1)
  - [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:1)
- Narrative docs:
  - [docs/schema_overview.md](docs/schema_overview.md:1)
- Supporting catalog:
  - [.rooroo/audit/db/schema_catalog.md](.rooroo/audit/db/schema_catalog.md:1)

Methodology:

- Treat `001` + `002` + `003` as authoritative for existing DB objects.
- Use `schema_overview.md` as descriptive documentation.
- Only record divergences that are directly observable.
- Mark partial detail gaps as "partially documented", not errors.
- Do not fabricate structures not present in repo SQL.

---

## 1. Entity-Level Consistency Table

Status codes:

- `match` — Docs and DDL align at the described level.
- `doc-missing` — Exists in DDL; not (or barely) described in docs.
- `extra-in-docs` — Described in docs; not found in inspected DDL.
- `partial` — Both exist; docs omit some structural details or group multiple tables conceptually.

| Aspect / Entity                    | Migrations / DDL                                                                 | schema_overview.md                                                        | Status        |
|------------------------------------|----------------------------------------------------------------------------------|---------------------------------------------------------------------------|---------------|
| `players`                          | Concrete table with PK `player_id` and rich attributes.                          | Described as core dimension keyed by `player_id`.                         | match         |
| `player_aliases`                   | Concrete table FK→`players`.                                                     | Mentioned as aliases keyed back to `players`.                             | match         |
| `teams`                            | Concrete table with PK `team_id`.                                                | Described as canonical team dimension.                                    | match         |
| `team_history`                     | Concrete table FK→`teams`.                                                       | Described as tracking season-specific changes.                            | match         |
| `team_abbrev_mappings`            | Concrete table FK→`teams` (nullable).                                            | Described as normalization mapping.                                       | match         |
| `seasons`                          | Concrete table with PK `season_id`.                                              | Described as canonical season dimension.                                  | match         |
| `games`                            | Concrete table with PK `game_id`, FKs to `seasons` & `teams`.                    | Described; usage and keys align.                                          | match         |
| `boxscore_team`                    | Concrete table with PK `(game_id, team_id)`.                                     | Described; one row per (game, team).                                      | match         |
| `boxscore_player`                  | Concrete table with PK `(game_id, player_id, team_id)`.                          | Described; granular player box scores.                                    | match         |
| `pbp_events`                       | Concrete table with PK `(game_id, eventnum)`.                                    | Described consistently as PBP fact.                                       | match         |
| `player_season`                    | Concrete hub table with PK `seas_id` and flags.                                  | Described as central hub with same semantics.                             | match         |
| `player_season_*` satellites       | Multiple tables PK/FK on `seas_id`.                                              | Described collectively as satellites 1:1 with hub.                        | partial       |
| `team_season`                      | Concrete hub table with PK `team_season_id`.                                     | Described as central team-season hub.                                     | match         |
| `team_season_*` satellites         | Some declared (`team_season_totals`, `team_season_per_game`); others referenced. | Docs list multiple satellites including opponent variants.                | partial       |
| `inactive_players`                 | **Not found** in visible `001` DDL excerpt.                                      | Described as table tracking (`game_id`, `player_id`).                     | extra-in-docs |
| `awards_*`                         | Mentioned in docs; DDL not visible in inspected excerpt.                         | Described as several awards tables referencing players/seasons.           | extra-in-docs |
| `draft_picks`                      | Mentioned in docs; DDL not visible in inspected excerpt.                         | Described as draft selections table.                                      | extra-in-docs |
| `data_versions`                    | Mentioned in docs; DDL not visible in inspected excerpt.                         | Described as recording source versions.                                   | extra-in-docs |
| `etl_runs`, `etl_run_steps`, `etl_run_issues` | Defined in `003` and mirrored in `schema.sql`.                           | Mention `etl_runs`; other metadata tables implied but not detailed.       | partial       |
| `vw_player_season_advanced`        | Defined in `002`.                                                                 | Not explicitly named, but aligns with advanced metrics narrative.         | doc-missing   |
| `vw_team_season_advanced`          | Defined in `002`.                                                                 | Not explicitly named, conceptually aligned with team advanced metrics.    | doc-missing   |
| `vw_player_career_aggregates`      | Defined in `002`.                                                                 | Not called out; career summary conceptually compatible.                   | doc-missing   |

Notes on key rows:

- **Satellites (`player_season_*`, `team_season_*`)**  
  Docs intentionally describe them as families; DDL contains concrete tables. This is recorded as `partial`, not a defect.

- **Awards / Draft / Inactive / Data Versions**  
  They are explicitly documented but their DDL is not visible in the inspected portion of `001`. Since the analysis must avoid speculation:
  - They are marked `extra-in-docs` relative to the inspected DDL snapshot.
  - This does **not** assert they are missing from the repo; only that their definitions are not confirmed here.

- **Advanced Views**  
  Present in DDL (`002`) and used by validation code, but not enumerated in `schema_overview.md`. Marked as `doc-missing`.

---

## 2. Documented, Not Fully Backed by Observed DDL

The following items are described in [docs/schema_overview.md](docs/schema_overview.md:26-35) but do not have fully confirmed definitions in the inspected `001`/`002`/`003` snippets:

1. `inactive_players`
2. `awards_all_star_selections`
3. `awards_player_shares`
4. `awards_end_of_season_teams`
5. `awards_end_of_season_voting`
6. `draft_picks`
7. `data_versions`
8. Some `team_season_*` opponent/per100 satellites

For this audit:

- They are treated as **"documented conceptually; DDL not verified in this snapshot"**.
- No synthetic schemas are introduced.
- Downstream checks should consult the full `db/migrations` files in this repo if present.

---

## 3. DDL Objects Missing or Under-Documented in Docs

Objects present in migrations but under-specified or absent in `schema_overview.md`:

1. **Advanced Views**
   - `vw_player_season_advanced`
   - `vw_team_season_advanced`
   - `vw_player_career_aggregates`
   - Used by [etl/validate_metrics.py](etl/validate_metrics.py:169-285).
   - **Status:** `doc-missing` — should be mentioned as official analytic surfaces.

2. **ETL Metadata Tables**
   - `etl_runs`, `etl_run_steps`, `etl_run_issues`
   - Central to observability and schema drift reporting.
   - `schema_overview.md` mentions `etl_runs` and "metadata" but not all three tables.
   - **Status:** `partial` — concepts documented, full structures not.

---

## 4. Explicit Limitations

1. **Scope of Inspection**
   - This artifact is based strictly on:
     - [db/migrations/001_initial_schema.sql](db/migrations/001_initial_schema.sql:1),
     - [db/migrations/002_advanced_views.sql](db/migrations/002_advanced_views.sql:1),
     - [db/migrations/003_etl_metadata.sql](db/migrations/003_etl_metadata.sql:1),
     - [docs/schema_overview.md](docs/schema_overview.md:1),
     - and the derived catalog in [.rooroo/audit/db/schema_catalog.md](.rooroo/audit/db/schema_catalog.md:1).
   - If additional DDL for awards/draft/inactive/etc. exists elsewhere in this repo, it should be incorporated by re-running this comparison against those files.

2. **No Fabricated Mismatches**
   - Items are only marked where there is direct, observable evidence:
     - A documented table not present in inspected DDL segments → `extra-in-docs`.
     - A DDL object missing in docs → `doc-missing`.
     - Different levels of detail → `partial`.

3. **Determinism**
   - Re-running this process against the same repo state yields the same table.
   - No external assumptions or speculative schemas are introduced.
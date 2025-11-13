# API Models vs DB Schema Alignment

_Source files:_
- [`api/models.py`](api/models.py:1)
- [`api/models_v2.py`](api/models_v2.py:1)
- [`db/schema.sql`](db/schema.sql:1) (as checked in; currently contains only ETL metadata tables)

**Scope constraint:** This artifact uses only concrete sources in this repo. Where DB tables/columns for business entities (players, teams, games, etc.) are not present in `db/schema.sql`, fields are marked as `unknown` with rationale rather than inferred.

At time of analysis, `db/schema.sql` defines only ETL metadata tables:

- `etl_runs`
- `etl_run_steps`
- `etl_run_issues`

No canonical tables for `players`, `teams`, `seasons`, `games`, box scores, or metrics exist in this file. Those are assumed to be defined "above" per comments, but not present in the committed snippet, so they are treated as **unavailable** for this Track 2 mapping.

---

## 1. v1 DTOs (`api/models.py`) vs DB Schema

### 1.1 `Player`

```text
class Player(BaseModel):
    player_id: int
    slug: Optional[str]
    full_name: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    is_active: Optional[bool]
    hof_inducted: Optional[bool]
    rookie_year: Optional[int]
    final_year: Optional[int]
```

| DTO Field     | DB Table | DB Column | Status   | Rationale                                                                 |
|--------------|----------|-----------|----------|---------------------------------------------------------------------------|
| `player_id`  | unknown  | unknown   | unknown  | `players` table not present in `schema.sql`.                             |
| `slug`       | unknown  | unknown   | unknown  | No concrete schema for player slug.                                      |
| `full_name`  | unknown  | unknown   | unknown  |                                                                           |
| `first_name` | unknown  | unknown   | unknown  |                                                                           |
| `last_name`  | unknown  | unknown   | unknown  |                                                                           |
| `is_active`  | unknown  | unknown   | unknown  |                                                                           |
| `hof_inducted` | unknown| unknown   | unknown  |                                                                           |
| `rookie_year`| unknown  | unknown   | unknown  |                                                                           |
| `final_year` | unknown  | unknown   | unknown  |                                                                           |

**Note:** Alignment with an expected `players` table cannot be verified from current `schema.sql`.

---

### 1.2 `Team`

```text
class Team(BaseModel):
    team_id: int
    team_abbrev: Optional[str]
    team_name: Optional[str]
    team_city: Optional[str]
    is_active: Optional[bool]
    start_season: Optional[int]
    end_season: Optional[int]
```

| DTO Field       | DB Table | DB Column | Status   | Rationale                                        |
|----------------|----------|-----------|----------|--------------------------------------------------|
| all fields     | unknown  | unknown   | unknown  | No `teams` table definition in `schema.sql`.     |

---

### 1.3 `Season`

```text
class Season(BaseModel):
    season_id: int
    season_end_year: int
    lg: Optional[str]
    is_lockout: Optional[bool]
```

| DTO Field        | DB Table | DB Column | Status   | Rationale                                      |
|-----------------|----------|-----------|----------|------------------------------------------------|
| all fields      | unknown  | unknown   | unknown  | No seasons table in `schema.sql`.              |

---

### 1.4 `Game`

```text
class Game(BaseModel):
    game_id: str
    season_end_year: Optional[int]
    game_date_est: str
    home_team_id: Optional[int]
    away_team_id: Optional[int]
    home_pts: Optional[int]
    away_pts: Optional[int]
    is_playoffs: Optional[bool]
```

| DTO Field       | DB Table | DB Column | Status   | Rationale                                      |
|----------------|----------|-----------|----------|------------------------------------------------|
| all fields     | unknown  | unknown   | unknown  | No `games` table definition in `schema.sql`.   |

---

### 1.5 `PlayerSeasonSummary`

```text
class PlayerSeasonSummary(BaseModel):
    seas_id: int
    player_id: int
    season_end_year: int
    team_id: Optional[int]
    team_abbrev: Optional[str]
    is_total: Optional[bool]
    is_playoffs: Optional[bool]
    g: Optional[int]
    pts_per_g: Optional[float]
    trb_per_g: Optional[float]
    ast_per_g: Optional[float]
```

DTO implies views/tables such as `player_season` / `player_season_per_game`, but these are not in `schema.sql`.

All fields → **`unknown` mapping** (no concrete tables/columns present).

---

### 1.6 `TeamSeasonSummary`

```text
class TeamSeasonSummary(BaseModel):
    team_season_id: int
    team_id: int
    season_end_year: int
    is_playoffs: Optional[bool]
    g: Optional[int]
    pts: Optional[int]
    opp_pts: Optional[int]
```

Assumed derived from `team_season`/`team_season_totals` in routers, but absent in `schema.sql`.

All fields → **`unknown`**.

---

### 1.7 `BoxscoreTeamRow`

```text
class BoxscoreTeamRow(BaseModel):
    game_id: str
    team_id: int
    opponent_team_id: Optional[int]
    is_home: bool
    team_abbrev: Optional[str]
    pts: Optional[int]
```

Routers reference `boxscore_team`, but `schema.sql` does not.

All fields → **`unknown`**.

---

### 1.8 `PbpEventRow`

```text
class PbpEventRow(BaseModel):
    game_id: str
    eventnum: int
    period: Optional[int]
    clk: Optional[str]
    event_type: Optional[str]
    team_id: Optional[int]
    player1_id: Optional[int]
    description: Optional[str]
    home_score: Optional[int]
    away_score: Optional[int]
```

Intended to mirror `pbp_events`, not in `schema.sql`.

All fields → **`unknown`**.

---

### 1.9 Tool DTOs & Derived Rows (v1)

Types such as:

- `PlayerSeasonFinderResponseRow`
- `PlayerGameFinderResponseRow`
- `TeamSeasonFinderResponseRow`
- `TeamGameFinderResponseRow`
- `StreakFinderResponseRow`
- `SpanFinderResponseRow`
- `VersusFinderResponseRow`
- `EventFinderResponseRow`
- `LeaderboardsResponseRow`
- `SplitsResponseRow`

are clearly shaped as **read models** over expected tables/views (box scores, player/team seasons, games). None of those backing tables/views are present in the current `db/schema.sql`, so:

- **All column mappings are `unknown`** from Track 1 artifacts available here.
- This is a schema visibility gap, not necessarily a runtime mismatch.

---

## 2. v2 DTOs (`api/models_v2.py`) vs DB Schema

v2 models define a **normalized query/metrics contract** (filters, metric references, paginated responses). They are **not direct row projections** and do not require 1:1 DB columns. Alignment here is about:

- Whether they assume tables/columns not present in `schema.sql`.
- Whether any fields can be concretely bound to known schema objects (ETL metadata tables).

Given `db/schema.sql` only exposes ETL metadata tables, nearly all v2 fields are:

- Either:
  - Purely in-request / logical (filters, enums, conditions), or
  - Intended to project metrics/aggregations over domain tables that are not visible here.

### 2.1 Shared Value Objects

Examples:

- `MetricAggregationFunctionV2`, `SortDirectionV2`, `GameScopeV2`, `LocationCodeV2`,
  `EntityTypeV2`, `SpanModeV2`, `StreakDirectionV2`
- Filter models: `SeasonFilterV2`, `DateRangeFilterV2`, `GameTypeFilterV2`, `TeamFilterV2`,
  `PlayerFilterV2`, `OpponentFilterV2`, `LocationFilterV2`, `ResultFilterV2`
- `AdvancedConditionV2`, `ConditionGroupV2`
- `MetricRefV2` (aligned with metrics registry)
- `PageSpecV2`, `ToolQueryV2`
- `QueryFiltersEchoV2`, `PaginationMetaV2`, `PaginatedResponseV2`

**DB Alignment:**

- All of the above are **API-level constructs**; they do not directly map to columns.
- Their correctness depends on:
  - `metrics/registry.yaml` and `metrics/registry.py` (for `MetricRefV2`), which are present.
  - Underlying game/boxscore tables (not present in `schema.sql`) for actual query execution.
- Marked as:
  - `n/a (logical)` for direct DB mapping.

---

### 2.2 Streaks / Spans / Leaderboards / Splits / Versus Result Rows

Representative examples:

- `StreaksResultRowV2`
- `SpansResultRowV2`
- `LeaderboardsResultRowV2`
- `SplitsResultRowV2`
- `VersusResultRowV2`

Each is a **result projection** composed of:

- `EntityTypeV2` and IDs (`subject_id`, `entity_id`, etc.).
- Metric IDs and `metrics: Dict[str, float]`.
- Aggregated counts (`games_count`, `rank`, etc.).

**DB Alignment:**

- These rows imply existence of:
  - Fact tables for games and stats.
  - Joins keyed on player/team IDs.
- None of those base tables are defined in current `db/schema.sql`.
- All such fields → **`unknown`** with rationale:
  - "Underlying stat tables not present in committed schema.sql; expected but unverifiable."

---

## 3. ETL Metadata Tables vs API Models

`db/schema.sql` only defines:

- `etl_runs`
- `etl_run_steps`
- `etl_run_issues`

None of the API DTOs (`models.py`, `models_v2.py`) reference those tables directly:

- No DTO named or fielded for `etl_runs`, `etl_run_steps`, or `etl_run_issues`.
- No direct FastAPI responses exposing ETL metadata in v1/v2 models.

**Alignment:**

- **No conflicts identified.**
- **No direct mappings:** ETL metadata is internal and unused by current DTO sets.

---

## 4. Summary Table: DTO Categories

| DTO Category                             | Examples                                             | Expected Backing Tables (not in schema.sql)                             | Status   |
|------------------------------------------|------------------------------------------------------|---------------------------------------------------------------------------|----------|
| Core entities (v1)                       | `Player`, `Team`, `Season`, `Game`                  | `players`, `teams`, `seasons`, `games`                                   | unknown  |
| Summaries & hubs (v1)                    | `PlayerSeasonSummary`, `TeamSeasonSummary`          | `player_season`, `team_season`, etc.                                     | unknown  |
| Box score / PBP rows (v1)                | `BoxscoreTeamRow`, `PbpEventRow`                    | `boxscore_team`, `pbp_events`                                            | unknown  |
| Tool finder/leaderboard rows (v1)        | `*FinderResponseRow`, `LeaderboardsResponseRow`     | Aggregations over boxscore + reference tables                            | unknown  |
| v2 filter/query scaffolding              | `ToolQueryV2`, filters, `MetricRefV2`, pagination   | Logical; validated against registry, not DB columns directly              | n/a      |
| v2 result rows                           | `StreaksResultRowV2`, `SpansResultRowV2`, etc.      | Aggregated views over missing game/metric tables                          | unknown  |
| ETL metadata tables                      | `etl_runs`, `etl_run_steps`, `etl_run_issues`       | Present in `schema.sql`; no DTO usage                                    | n/a      |

---

## 5. Explicit `unknown` Annotations (Non-Speculative)

Per instruction, only truly unmappable fields are marked `unknown`. Here, "unmappable" means:

> There is no concrete table/column definition in `db/schema.sql` matching the DTO's intent.

Examples (all **`unknown`** due to missing schema objects):

- `Player.player_id`, `Team.team_id`, `Game.game_id`, `Season.season_end_year`, etc.
- All box score and PBP fields (`pts`, `trb`, `event_type`, etc.).
- All derived/aggregate fields in finder/leaderboard/streak/span/versus DTOs.

These are **not** flagged as incorrect; they are:

- **Pending alignment** on the Track 1 side:
  - Once the full canonical schema (players/teams/games/boxscores/etc.) is materialized in `db/schema.sql` or an authoritative schema artifact, a second-pass alignment can:
    - Map each DTO field to specific tables/columns.
    - Identify real drifts (naming mismatches, type discrepancies).

---

## 6. Conclusions

1. **No direct contradictions** between `api/models.py` / `api/models_v2.py` and the committed `db/schema.sql`:
   - Primary domain tables simply do not appear in `schema.sql`, so contradictions cannot be proven.
2. **v2 metrics contracts are concretely aligned** with the metrics registry:
   - `MetricRefV2` and related types are backed by [`metrics/registry.py`](metrics/registry.py:1) and [`metrics/registry.yaml`](metrics/registry.yaml:1), not the DB schema file.
3. **ETL metadata schema is orthogonal**:
   - Present in `db/schema.sql`, not represented in DTOs, and does not conflict with API contracts.
4. **Actionable gap (for future work, not speculated here):**
   - To complete Track 1/Track 2 alignment, the canonical definitions of core stat tables must be available (either in `db/schema.sql` or another concrete artifact). Until then, DTO-to-DB mappings for core entities and stats remain `unknown` by construction.
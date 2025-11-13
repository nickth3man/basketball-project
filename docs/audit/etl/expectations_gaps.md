# Expectations Gaps

Uses:

- Schema catalog: [.rooroo/audit/db/schema_catalog.md](.rooroo/audit/db/schema_catalog.md:1)
- Expectations map: [.rooroo/audit/etl/expectations_map.md](.rooroo/audit/etl/expectations_map.md:1)
- Validations overview: [.rooroo/audit/etl/modules/validations_overview.md](.rooroo/audit/etl/modules/validations_overview.md:1)

to highlight coverage gaps. Based solely on in-repo artifacts; no speculative fixes.

---

## 1. Method

For each core table/entity:

1. Check if it has explicit table expectations in [etl/expectations.yaml](etl/expectations.yaml:1).
2. Check if it has explicit CSV expectations (for sources that load into it).
3. Check if it is covered by validation logic:
   - [etl/validate_data.py](etl/validate_data.py:1)
   - [etl/validate_metrics.py](etl/validate_metrics.py:1)
   - [etl/validate.py](etl/validate.py:1)
   - [etl/schema_drift.py](etl/schema_drift.py:1)
4. Label coverage as:
   - `covered_by_expectations` — explicit expectations for the table/source.
   - `covered_by_validations_only` — referenced by validation SQL / FK checks, but no expectations.
   - `uncovered_or_weak` — neither expectations nor clear validation coverage found.

Only directly observable relationships are used.

---

## 2. Gap Inventory

### 2.1 Core Dimensions

#### `players`

- **Expectations:** Yes (CSV `players`, table `players`).
- **Validations:** Yes (structural + referential checks).
- **Status:** `covered_by_expectations`.

#### `teams`

- **Expectations:** Yes (CSV `teams`, table `teams`).
- **Validations:** Yes (FK usage via games/boxscores checks).
- **Status:** `covered_by_expectations`.

#### `seasons`

- **Expectations:** Yes (CSV `seasons`, table `seasons`).
- **Validations:** Yes (used via FKs/joins).
- **Status:** `covered_by_expectations`.

#### `team_history`, `team_abbrev_mappings`

- **Expectations:** No explicit table expectations.
- **Validations:** Indirectly relied upon for ID resolution; no dedicated checks.
- **Status:** `uncovered_or_weak`.

### 2.2 Game & Box Score Facts

#### `games`

- **Expectations:** Yes (CSV `games`, table `games`).
- **Validations:** Strong:
  - Structural presence.
  - Orphan checks from facts.
- **Status:** `covered_by_expectations`.

#### `boxscore_team`

- **Expectations:** Yes (table entry); CSV `boxscores` serves as upstream expectation.
- **Validations:** Present:
  - Structural and referential checks.
- **Status:** `covered_by_expectations`.

#### `boxscore_player`

- **Expectations:** No dedicated table expectations in inspected YAML.
- **Validations:** Mentioned via FK-style checks (player/game linkage) in validation modules.
- **Status:** `covered_by_validations_only`.

### 2.3 Play-by-Play

#### `pbp_events`

- **Expectations:** Yes (CSV `pbp_events`, table `pbp_events`).
- **Validations:** Yes (presence + FK to `games`).
- **Status:** `covered_by_expectations`.

### 2.4 Player-Season Hub & Satellites

#### `player_season`

- **Expectations:** Yes (table expectations defined).
- **Validations:** Yes:
  - Structural presence.
  - Hub/satellite consistency checks.
- **Status:** `covered_by_expectations`.

#### `player_season_per_game`, `player_season_totals`,
`player_season_per36`, `player_season_per100`, `player_season_advanced`

- **Expectations:** No explicit per-table expectations listed in YAML.
- **Validations:** Yes:
  - Hub/satellite integrity checks ensure:
    - 1:1 with `player_season` where expected.
  - Metrics validations read from advanced views that depend on these tables.
- **Status:** `covered_by_validations_only`.

### 2.5 Team-Season Hub & Satellites

#### `team_season`

- **Expectations:** Yes (table expectations).
- **Validations:** Yes:
  - Structural/hub checks.
- **Status:** `covered_by_expectations`.

#### `team_season_totals`, `team_season_per_game`

- **Expectations:** No explicit entries in expectations YAML.
- **Validations:** Yes:
  - Hub/satellite and metrics checks consume them (e.g. in `vw_team_season_advanced`).
- **Status:** `covered_by_validations_only`.

#### `team_season_per100`, `team_season_opponent_totals`,
`team_season_opponent_per_game`, `team_season_opponent_per100`
(if and where present)

- **Expectations:** Not explicitly mapped in YAML.
- **Validations:** Implicit use via advanced views and consistency checks.
- **Status:** `covered_by_validations_only` (structure assumed via views, but no direct expectations).

### 2.6 Awards, Draft, Inactive, Metadata

#### `awards_*` tables

- **Expectations:** Yes:
  - Table expectations with `min_rows: 0`.
- **Validations:** Yes:
  - `validate.py` includes awards/draft integrity checks.
- **Status:** `covered_by_expectations`.

#### `draft_picks`

- **Expectations:** Yes (table entry).
- **Validations:** Yes (paired with awards checks).
- **Status:** `covered_by_expectations`.

#### `inactive_players`

- **Expectations:** Yes (table entry).
- **Validations:** Yes:
  - Referenced in validation checks as a fact table with PK/links.
- **Status:** `covered_by_expectations`.

#### `etl_runs`, `etl_run_steps`, `etl_run_issues`

- **Expectations:** No explicit YAML expectations.
- **Validations:** No strong semantic checks; primarily used as logging targets.
- **Status:** `uncovered_or_weak` (by design; metadata tables).

### 2.7 Views

#### `vw_player_season_advanced`, `vw_team_season_advanced`,
`vw_player_career_aggregates`

- **Expectations:** Not defined in expectations.yaml.
- **Validations:** Yes:
  - `validate_metrics.py` runs metrics checks against these views.
- **Status:** `covered_by_validations_only`.

---

## 3. Summary of Notable Gaps

The following gaps are directly observable and may be relevant for future hardening
(analysis only; no changes are applied here):

1. **Dimension Support Tables:**
   - `team_history`, `team_abbrev_mappings`:
     - No explicit table expectations.
     - Limited or no direct validation coverage.
     - **Label:** `uncovered_or_weak`.

2. **Player/Team Season Satellites:**
   - `player_season_*` and several `team_season_*` satellites:
     - Integrity enforced via hub/satellite validations and advanced view checks.
     - No explicit expectations.yaml coverage.
     - **Label:** `covered_by_validations_only`.

3. **ETL Metadata Tables:**
   - `etl_runs`, `etl_run_steps`, `etl_run_issues`:
     - No expectations or strong invariants encoded in expectations.yaml.
     - Only used operationally.
     - **Label:** `uncovered_or_weak` (acceptable but noteworthy).

4. **Views:**
   - Advanced views are validated by `validate_metrics.py` but:
     - Not represented in expectations.yaml.
     - **Label:** `covered_by_validations_only`.

All labels above are descriptive. Designing or applying fixes is explicitly out of scope.

---

## 4. Determinism & Non-Speculation

- This artifact is generated solely from:
  - The committed expectations configuration,
  - The validation modules,
  - The schema catalog.
- No new constraints are proposed.
- Re-running the analysis on the same repo state produces identical results.
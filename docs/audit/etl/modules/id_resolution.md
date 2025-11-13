# ID Resolution Logic & Invariants

_Source: [`etl/id_resolution.py`](../../../etl/id_resolution.py:1)_

This artifact documents the pure in-memory ID resolution helpers used by the ETL. These functions:

- Do **not** perform any DB I/O.
- Operate on `polars.DataFrame` snapshots prepared by upstream loaders.
- Encode deterministic rules consistent with:
  - [`db/schema.sql`](../../../db/schema.sql)
  - [`docs/schema_overview.md`](../../../docs/schema_overview.md:1)
  - CSV inventory semantics.

---

## 1. Data Structures

All lookups are immutable `@dataclass(frozen=True)` objects keyed by canonical identifiers.

### 1.1 `PlayerLookup`

Fields:

- `by_id: Dict[int, int]`
  - Maps `player_id` → `player_id` (identity mapping; presence check).
- `by_slug: Dict[str, int]`
  - `slug.lower()` → `player_id`.
- `by_full_name: Dict[str, int]`
  - Normalized `"full_name".lower()` → `player_id`.
  - Also includes `"First Last".lower()` when `first_name`/`last_name` present.
- `aliases: Dict[str, int]`
  - Lowercased alias values from alias CSVs → `player_id`.

Construction (`build_player_lookup`):

- Inputs:
  - `players_df` with columns:
    - `player_id`, `slug`, `full_name`, `first_name`, `last_name`.
  - Optional `aliases_df` with:
    - `alias_value`, `player_id`.
- Behavior:
  - Iterates rows defensively; trims strings; skips blanks.
  - Ensures:
    - Direct ID lookup (`by_id`) always succeeds when a row is present.
    - Multiple name keys may point to the same `player_id`.
  - Aliases:
    - Added only when both alias and player_id are non-null.
- Failure modes:
  - Empty/missing columns → corresponding maps partially empty; functions fall back safely.
  - No exceptions raised for content issues; mappings are best-effort.

### 1.2 `TeamLookup`

Fields:

- `by_id: Dict[int, int]`
  - `team_id` → `team_id`.
- `by_season_abbrev: Dict[Tuple[int, str], int]`
  - `(season_end_year, team_abbrev_upper)` → `team_id`.
- `by_abbrev: Dict[str, int]`
  - `team_abbrev_upper` → `team_id` (season-agnostic fallback).

Construction (`build_team_lookup`):

- Inputs:
  - `teams_df`:
    - `team_id`, `team_abbrev`.
  - Optional `team_history_df`:
    - `team_id`, `season_end_year`, `team_abbrev` (or equivalent).
  - Optional `abbrev_map_df`:
    - `season_end_year`, `raw_abbrev`, `team_id`.
- Behavior:
  - Populates:
    - Base abbrev map from `teams_df`.
    - Season-specific map from history data when available.
    - Extended mappings from abbrev map CSV where present.
- Invariants:
  - Season-specific keys take precedence (`by_season_abbrev`).
  - `by_abbrev` can be populated from both base and map data.

### 1.3 `SeasonLookup`

Fields:

- `by_year_lg: Dict[Tuple[int, str], int]`
  - `(season_end_year, lg_normalized)` → `season_id`.

Construction (`build_season_lookup`):

- Inputs:
  - `seasons_df` with:
    - `season_id`, `season_end_year`, `lg`.
- Behavior:
  - Normalizes `lg` to uppercase, defaulting to `"NBA"` when missing.
  - Ensures deterministic mapping for each `(year, lg)`.

### 1.4 `GameLookup`

Fields:

- `by_game_id: Dict[str, str]`
  - `game_id` → `game_id` (presence set).

Construction (`build_game_lookup`):

- Inputs:
  - `games_df` with `game_id`.
- Behavior:
  - Adds trimmed non-empty IDs.

---

## 2. Resolution Functions & Deterministic Order

All resolution helpers are **pure functions** over the lookup dataclasses.

### 2.1 `resolve_player_id_from_name`

Signature:

```python
resolve_player_id_from_name(
    name: str,
    lookup: PlayerLookup,
    slug: Optional[str] = None,
    numeric_id: Optional[int] = None,
) -> Optional[int]
```

Resolution order (strict, deterministic):

1. If `numeric_id` is provided and in `lookup.by_id`:
   - Return `numeric_id`.
2. Else if `slug` is provided:
   - Normalize to lowercase; look up in `by_slug`.
3. Else:
   - Normalize `name` to lowercase; try:
     - `by_full_name[name]`
     - `aliases[name]`
4. If none match:
   - Return `None`.

Implications:

- Strong preference for explicit numeric IDs.
- Slug and name-based matches are fallback mechanisms.
- No fuzzy matching; avoids non-deterministic resolutions.

### 2.2 `resolve_team_id_from_abbrev`

Signature:

```python
resolve_team_id_from_abbrev(
    abbrev: str,
    season_end_year: Optional[int],
    lookup: TeamLookup,
) -> Optional[int]
```

Resolution order:

1. Require non-empty `abbrev`; uppercase it.
2. If `season_end_year` provided:
   - Try `lookup.by_season_abbrev[(season_end_year, abbrev)]`.
3. Fallback:
   - Try `lookup.by_abbrev[abbrev]`.
4. Else:
   - Return `None`.

Implications:

- Season-aware mapping preferred (captures relocations/renames).
- Season-agnostic mapping only when no season-specific entry.

### 2.3 `resolve_season_id`

Signature:

```python
resolve_season_id(
    season_end_year: int,
    lg: Optional[str],
    lookup: SeasonLookup,
) -> Optional[int]
```

Behavior:

- If `season_end_year` is `None`:
  - Return `None`.
- Normalize `lg`:
  - `lg_norm = (lg or "NBA").strip().upper() or "NBA"`.
- Lookup:
  - Return `lookup.by_year_lg.get((season_end_year, lg_norm))`.

Implications:

- Default league is `"NBA"` when unspecified.
- Deterministic handling of league code casing.

### 2.4 `ensure_game_exists`

Signature:

```python
ensure_game_exists(game_id: str, lookup: GameLookup) -> bool
```

- Returns `False` if `game_id` is falsy.
- Else checks membership in `lookup.by_game_id`.

Use:

- Guardrail for loaders to avoid inserting references to unknown games.

---

## 3. Assumptions & Cross-Module Dependencies

### 3.1 Inputs & Contracts

- All lookups assume inputs have already been:
  - Read from authoritative CSVs (per [`etl/paths.py`](../../../etl/paths.py:1)).
  - Loaded into Polars DataFrames with expected columns.
- No direct reliance on:
  - Live DB queries.
  - Application-specific types.

Upstream modules using these helpers:

- [`etl/load_games_and_boxscores.py`](../../../etl/load_games_and_boxscores.py:1)
- [`etl/load_pbp.py`](../../../etl/load_pbp.py:1)
- [`etl/load_player_seasons.py`](../../../etl/load_player_seasons.py:1)
- [`etl/load_team_seasons.py`](../../../etl/load_team_seasons.py:1)
- [`etl/load_awards_and_draft.py`](../../../etl/load_awards_and_draft.py:1)
- [`etl/load_inactive.py`](../../../etl/load_inactive.py:1)

These modules:

- Construct dimension snapshots from DB (players/teams/seasons/games).
- Build lookup objects via `build_*` helpers.
- Call resolution functions to map textual/numeric CSV fields into canonical IDs.

### 3.2 Invariants

- All resolution is **non-mutating**:
  - No changes to DataFrames passed in.
  - No external side effects besides logging in callers.
- Normalization:
  - Trimming whitespace.
  - Case normalization (lowercase for names/slugs, uppercase for team abbrevs, uppercase for leagues).
- Determinism:
  - Given the same lookup inputs, resolutions are repeatable.

### 3.3 Failure Modes & Safety

- Missing or incomplete input columns:
  - Lookups become sparse; resolvers return `None`.
  - Callers decide whether to:
    - Leave FKs null (soft failure).
    - Filter/drop unresolved rows when referential integrity is mandatory.
- Conflicting data (e.g., duplicate keys):
  - `dict.setdefault` patterns mean:
    - First-seen mapping is preserved.
    - Later duplicates are ignored, avoiding noisy, unstable remaps.
- No exceptions on ambiguous matches:
  - Ambiguity is implicitly resolved by “first write wins” in the lookup build phase.
  - This design favors stability over aggressive erroring.

---

## 4. Existing Validations & Hooks

While `etl/id_resolution.py` itself contains no runtime assertions:

- Downstream validations in:
  - [`etl/validate_data.py`](../../../etl/validate_data.py:1)
  - [`etl/validate_metrics.py`](../../../etl/validate_metrics.py:1)
  - Expectations/schema drift tooling
- Indirectly verify that:
  - FKs populated using these helpers align with `db/schema.sql`.
  - Orphan counts are acceptable (or treated as fatal where required).

This separation keeps ID resolution logic:

- Focused and testable in isolation.
- Reliably composed with independent validation harnesses.

---

## 5. Summary for Track 1 Audit

- `etl/id_resolution.py` implements **pure, deterministic** mapping from:
  - CSV / dimension attributes → canonical `player_id`, `team_id`, `season_id`, `game_id`.
- Key properties:
  - No DB writes; no direct queries.
  - Consistent normalization rules for names, slugs, team abbrevs, and leagues.
  - Predictable fallback ordering that prioritizes strongest identifiers (numeric IDs > slugs > names > aliases).
- This module is safe to rely on as the core contract for resolving entity identity across ETL loaders and serves as a critical invariant layer between raw CSV inputs and the relational schema.
# Metrics Registry Catalog

_Source files:_
- [`metrics/registry.yaml`](metrics/registry.yaml:1)
- [`metrics/registry.py`](metrics/registry.py:1)

This catalog documents the concrete metrics defined in the v1 metrics registry and the validated behaviors enforced by the loader. It reflects **only** information present in the repository: no inferred formulas or speculative fields. Semantics are derived from:

- YAML definitions under `metrics.metrics`.
- Validation and normalization logic in `metrics/registry.py` (_enum constraints, allowed aggregations, base table requirements, alias index_).

## 1. Registry-Level Contract

### 1.1 Structure & Versioning

- Root keys:
  - `version: int`
    - Required; non-integer or missing → `RegistryLoadError`.
  - `metrics: dict[str, dict]`
    - Required; non-mapping → `RegistryLoadError`.
- On successful validation:
  - An internal-only `_alias_index: dict[str, str]` is attached by [`_validate_and_normalize`](metrics/registry.py:151), mapping lowercased aliases to canonical metric ids.
  - Callers of `load_registry()` may see `_alias_index`, but public helpers (`get_metric_def`, `resolve_metric_ref`) deliberately filter it from exposed descriptors.

### 1.2 Loading & Error Semantics

Implemented in [`load_registry`](metrics/registry.py:177):

- Loads `metrics/registry.yaml` once, validates, caches result.
- On first failure:
  - Logs `event="metrics_registry_load_failed"`.
  - Stores the underlying exception in `_registry_error`.
  - Raises `RegistryUnavailableError("Metrics registry unavailable")`.
- On subsequent calls after failure:
  - Immediately raises `RegistryUnavailableError` (deterministic failure).
- On success:
  - Logs `event="metrics_registry_loaded"` with `metrics_count`.

**Contractual implication:** Any API depending on `load_registry()` or `get_metric_def()` must treat `RegistryUnavailableError` as a stable 503-style condition (as enforced in [`api/routers/v2_metrics.py`](api/routers/v2_metrics.py:101)).

### 1.3 Metric Validation Rules

For each `metrics[metric_id]`:

1. **Id Consistency** (`_validate_metric_id_consistency`):
   - `metric["id"]` **must equal** the YAML key.
   - Mismatch → `RegistryLoadError`.

2. **Enums** (`_validate_enums`):
   - `entity_type ∈ {"player", "team", "lineup", "game"}`.
   - `level ∈ {"game", "season", "career", "span", "streak"}`.
   - `source ∈ {"column", "expression"}`.
   - Any invalid value → `RegistryLoadError`.

3. **Expression** (`_validate_expression`):
   - `expression` is required, non-empty `str`.
   - If `source == "column"`:
     - `expression` must be a bare identifier (no whitespace); otherwise `RegistryLoadError`.

4. **Allowed Aggregations** (`_validate_allowed_aggregations`):
   - `allowed_aggregations`:
     - Must be a non-empty `list`.
     - Each entry must be a valid `MetricAggregationFunctionV2.value`.
       - Invalid entries → `RegistryLoadError`.

5. **Base Table** (`_validate_base_table`):
   - `base_table`:
     - Required, non-empty `str`.
     - Missing/blank → `RegistryLoadError`.

6. **Aliases** (`_build_alias_index`):
   - If `aliases` present:
     - Must be an iterable of non-empty strings.
     - Stored case-insensitively in `_alias_index`.
     - Duplicate alias across metrics → `RegistryLoadError`.

These rules define the **hard guarantees** for every metric accessible via the registry.

---

## 2. Metric Lookup & Resolution Contracts

### 2.1 `get_metric_def(metric_id: str) -> dict | None`

_Source: [`metrics/registry.py`](metrics/registry.py:242)_

- Requires registry to be loadable; otherwise `RegistryUnavailableError`.
- Resolution order:
  1. Exact id match in `metrics`.
  2. Case-insensitive lookup via `_alias_index`.
- Returns:
  - Metric dict as defined in YAML (plus any normalized structure) if found.
  - `None` if no id/alias match.

**Contract:** API/clients using this helper must handle:
- `RegistryUnavailableError`
- `None` (unknown metric).

### 2.2 `resolve_metric_ref(metric_ref: MetricRefV2) -> dict`

_Source: [`metrics/registry.py`](metrics/registry.py:288)_

- Resolves `MetricRefV2.id` (and optionally `.alias`) via `get_metric_def`.
  - If still missing → `UnknownMetricError("Unknown metric id or alias: ...")`.
- Validates requested `aggregation`:
  - Uses `_normalize_aggregation`; raises `InvalidAggregationError` if aggregation not in `allowed_aggregations`.
- Returns **sanitized descriptor** containing (only if present on source metric):

  - `id`, `name`, `category`, `entity_type`, `level`,
  - `source`, `expression`, `base_table`,
  - `requires`, `unit`, `precision`,
  - `allowed_aggregations`,
  - `filters_hint`,
  - `aliases`,
  - `display`,
  - `constraints`,
  - plus `chosen_aggregation` (normalized or `None`).

**Contract:** Callers must treat this descriptor as the canonical safe view of a metric; internal-only keys are excluded.

---

## 3. Catalog: Player Game-Level Metrics (`boxscore_line`)

The following entries are **directly present** in [`metrics/registry.yaml`](metrics/registry.yaml:19) and validated by `metrics/registry.py`. Only fields explicitly defined are listed.

### 3.1 `pts_pg`

| Field            | Value                       |
|-----------------|-----------------------------|
| `id`            | `pts_pg`                    |
| `name`          | Points                      |
| `category`      | `box_score`                 |
| `entity_type`   | `player`                    |
| `level`         | `game`                      |
| `source`        | `column`                    |
| `expression`    | `pts`                       |
| `base_table`    | `boxscore_line`            |
| `requires`      | `[]`                        |
| `unit`          | `points`                    |
| `precision`     | `0`                         |
| `allowed_aggregations` | `["sum", "avg"]`     |
| `display.short_label` | `PTS`                |
| `display.long_label`  | `Points`             |
| `display.description` | Points scored         |
| `display.format`      | `number`             |
| `constraints.monotonic_non_negative` | `true` |

### 3.2 `ast_pg`

_Structurally analogous to `pts_pg`; different label/unit._

| Field            | Value                       |
|-----------------|-----------------------------|
| `id`            | `ast_pg`                    |
| `name`          | Assists                     |
| `category`      | `box_score`                 |
| `entity_type`   | `player`                    |
| `level`         | `game`                      |
| `source`        | `column`                    |
| `expression`    | `ast`                       |
| `base_table`    | `boxscore_line`            |
| `requires`      | `[]`                        |
| `unit`          | `assists`                   |
| `precision`     | `0`                         |
| `allowed_aggregations` | `["sum", "avg"]`     |
| `display.short_label` | `AST`                |
| `display.long_label`  | `Assists`            |
| `display.description` | Assists recorded      |
| `display.format`      | `number`             |
| `constraints.monotonic_non_negative` | `true` |

### 3.3 `trb_pg`

| Field            | Value                                                             |
|-----------------|-------------------------------------------------------------------|
| `id`            | `trb_pg`                                                          |
| `name`          | Total Rebounds                                                    |
| `category`      | `box_score`                                                       |
| `entity_type`   | `player`                                                          |
| `level`         | `game`                                                            |
| `source`        | `expression`                                                      |
| `expression`    | `COALESCE(orb, 0) + COALESCE(drb, 0)`                             |
| `base_table`    | `boxscore_line`                                                  |
| `requires`      | `["oreb_pg", "dreb_pg"]`                                         |
| `unit`          | `rebounds`                                                        |
| `precision`     | `0`                                                               |
| `allowed_aggregations` | `["sum", "avg"]`                                           |
| `display.short_label` | `TRB`                                                      |
| `display.long_label`  | `Total Rebounds`                                            |
| `display.description` | Total rebounds (offensive + defensive)                      |
| `display.format`      | `number`                                                   |
| `constraints.monotonic_non_negative` | `true`                                       |

### 3.4 `stl_pg`

- Steals; `source=column`, `expression=stl`, same structural pattern as `pts_pg`.
- Constraints: `monotonic_non_negative: true`.

### 3.5 `blk_pg`

- Blocks; `expression=blk`, same structural pattern, non-negative constraint.

### 3.6 `tov_pg`

- Turnovers; `expression=tov`, same structural pattern, non-negative constraint.

### 3.7 `pf_pg`

- Personal Fouls; `expression=pf`, same structural pattern, non-negative constraint.

### 3.8 `fgm_pg`

- Field Goals Made; `expression=fg`, `unit="fgm"`, non-negative.

### 3.9 `fga_pg`

- Field Goals Attempted; `expression=fga`, `unit="fga"`, non-negative.

### 3.10 `fg3m_pg`

- 3P Made; `expression=fg3`, `unit="3pm"`, non-negative.

### 3.11 `fg3a_pg`

- 3P Attempted; `expression=fg3a`, `unit="3pa"`, non-negative.

### 3.12 `ftm_pg`

- Free Throws Made; `expression=ft`, `unit="ftm"`, non-negative.

### 3.13 `fta_pg`

- Free Throws Attempted; `expression=fta`, `unit="fta"`, non-negative.

### 3.14 `oreb_pg`

- Offensive Rebounds; `expression=orb`, `unit="oreb"`, non-negative.

### 3.15 `dreb_pg`

- Defensive Rebounds; `expression=drb`, `unit="dreb"`, non-negative.

Each of these metrics:

- Belongs to category `box_score`.
- Uses `boxscore_line` as `base_table`.
- Supports `["sum", "avg"]` aggregations.
- Is validated for structural consistency by `metrics/registry.py`.

---

## 4. Catalog: Team Game-Level Metrics (`team_boxscore_line`)

### 4.1 `pts_tg`

| Field            | Value                       |
|-----------------|-----------------------------|
| `id`            | `pts_tg`                    |
| `name`          | Team Points                 |
| `category`      | `box_score`                 |
| `entity_type`   | `team`                      |
| `level`         | `game`                      |
| `source`        | `column`                    |
| `expression`    | `pts`                       |
| `base_table`    | `team_boxscore_line`       |
| `requires`      | `[]`                        |
| `unit`          | `points`                    |
| `precision`     | `0`                         |
| `allowed_aggregations` | `["sum", "avg"]`     |
| `display.short_label` | `PTS`                |
| `display.long_label`  | `Team Points`         |
| `display.description` | Team points scored    |
| `display.format`      | `number`             |
| `constraints.monotonic_non_negative` | `true` |

### 4.2 `fgm_tg`

- Team Field Goals Made; `expression=fg`, `base_table=team_boxscore_line`, same aggregation and constraint pattern.

### 4.3 `fga_tg`

- Team Field Goals Attempted; `expression=fga`, same pattern.

_All listed team metrics follow the same structural guarantees enforced by the validator: valid enums, non-empty expression, allowed aggregations, non-empty base_table, and monotonic_non_negative where specified._

---

## 5. Cross-Cutting Invariants for Metrics

Derived strictly from [`metrics/registry.py`](metrics/registry.py:48) and helpers:

1. **Canonical Ids**
   - Every metric has exactly one canonical `id` matching its YAML key.

2. **Entity/Level/Source Constraints**
   - `entity_type`, `level`, `source` must belong to fixed enumerations.
   - Any invalid value prevents the registry from loading at all.

3. **Expression Integrity**
   - All metrics must define `expression`.
   - Column-based metrics must use a single identifier (no spaces), ensuring direct column mapping.

4. **Allowed Aggregations**
   - Only known aggregation function identifiers (per `MetricAggregationFunctionV2`) are permitted.
   - Attempting to use a disallowed aggregation via `resolve_metric_ref` results in `InvalidAggregationError`.

5. **Base Table Binding**
   - Each metric binds to a concrete `base_table`.
   - This forms the contract surface for downstream query builders and v2 tools that rely on registry-driven SQL generation.

6. **Alias Semantics**
   - Aliases, if present:
     - Are case-insensitive.
     - Uniquely map to one canonical metric id.
   - `get_metric_def` and `resolve_metric_ref` fully support alias-based resolution.

7. **Safety of Public Descriptors**
   - Public-facing helpers only expose curated fields.
   - Internal caches/indexes are never leaked via `resolve_metric_ref` responses.

---

## 6. Notes & Confirmed Non-Speculative Scope

- This catalog intentionally:
  - Documents only metrics concretely defined in `metrics/registry.yaml` (partial excerpt shown above).
  - Encodes only behaviors enforced in `metrics/registry.py`.
- It does **not** introduce new metric ids, categories, or shapes.
- Unknown or missing elements elsewhere should be treated as:
  - `unknown` at the point of integration (e.g., if referenced by tools not yet wired),
  - to be resolved by future registry extensions rather than assumed here.
# v2 Metrics Endpoints vs Metrics Registry

_Source files:_
- [`api/routers/v2_metrics.py`](api/routers/v2_metrics.py:1)
- [`metrics/registry.yaml`](metrics/registry.yaml:1)
- [`metrics/registry.py`](metrics/registry.py:1)

This artifact maps the **v2 metrics HTTP surface** to the **metrics registry** implementation and validation rules. It is strictly based on concrete code/definitions in this repo; no speculative metrics, shapes, or behaviors are introduced.

---

## 1. Surfaces Under Comparison

### 1.1 v2 Metrics Endpoints

From [`api/routers/v2_metrics.py`](api/routers/v2_metrics.py:65):

1. `GET /api/v1/metrics`
   - **Handler:** `list_metrics_v2`
   - **Response:** `PaginatedResponseV2[Dict[str, Any]]`
   - **Filters:**
     - `entity_type: EntityTypeV2 | None`
     - `level: str | None`
     - `category: str | None`
     - `page: int (>=1, default=1)`
     - `page_size: int (1..500, default=100)`
   - **Data Source:** `load_registry()` → `registry["metrics"]`.
   - **Per-item shape:** `_metric_summary(metric)`:
     - `id`, `name`, `entity_type`, `level`, `category`, `unit`,
     - `display.{short_label,long_label,format}`.

2. `GET /api/v1/metrics/{metric_id}`
   - **Handler:** `get_metric_v2`
   - **Response:** `Dict[str, Any]`
   - **Data Source:** `get_metric_def(metric_id)`
   - **Per-item shape:** `_sanitize_metric_definition(metric)`:
     - Keys restricted to:
       `id,name,category,entity_type,level,source,expression,base_table,requires,unit,precision,allowed_aggregations,filters_hint,aliases,display,constraints`.

---

### 1.2 Metrics Registry Implementation

From [`metrics/registry.py`](metrics/registry.py:151):

- `load_registry()`:
  - Loads `metrics/registry.yaml`.
  - Validates:
    - `version` present and int.
    - `metrics` is mapping.
    - Per-metric:
      - `id` matches key.
      - `entity_type ∈ {player, team, lineup, game}`.
      - `level ∈ {game, season, career, span, streak}`.
      - `source ∈ {column, expression}`.
      - `expression` non-empty; if `source=column` then bare identifier.
      - `allowed_aggregations` non-empty subset of `MetricAggregationFunctionV2`.
      - `base_table` non-empty string.
    - Aliases:
      - `aliases` iterable of non-empty strings.
      - Unique (case-insensitive) across all metrics.
  - Builds `_alias_index` (internal).
  - On failure: caches error and raises `RegistryUnavailableError` on all calls.

- `get_metric_def(metric_id)`:
  - Uses `load_registry()` (or raises `RegistryUnavailableError`).
  - Exact id match, else alias lookup via `_alias_index`.
  - Returns metric dict or `None`.

- `resolve_metric_ref(metric_ref)`:
  - Uses `get_metric_def`.
  - Validates aggregation against `allowed_aggregations`.
  - Returns sanitized descriptor (superset of `_sanitize_metric_definition` keys plus `chosen_aggregation`).

- Registry content (`metrics/registry.yaml`):
  - Concrete metrics such as:
    - `pts_pg`, `ast_pg`, `trb_pg`, `stl_pg`, `blk_pg`, `tov_pg`, `pf_pg`,
      `fgm_pg`, `fga_pg`, `fg3m_pg`, `fg3a_pg`, `ftm_pg`, `fta_pg`, `oreb_pg`, `dreb_pg`,
      `pts_tg`, `fgm_tg`, `fga_tg`, etc.
  - Each bound to explicit `entity_type`, `level`, `base_table`, `allowed_aggregations`, etc.

---

## 2. Alignment: `GET /metrics` vs Registry

### 2.1 Source & Error Semantics

- Endpoint calls:

  ```python
  registry = load_registry()
  metrics = registry.get("metrics", {})
  ```

- On load failure:
  - Catches `RegistryUnavailableError` and returns:
    - `503 SERVICE_UNAVAILABLE`
    - `detail.code = "metrics_registry_unavailable"`

**Alignment:** Fully consistent with `load_registry` behavior as implemented. No divergence.

### 2.2 Filtering Semantics

`list_metrics_v2` defines:

- `entity_type: Optional[EntityTypeV2]`
  - Filter: `m["entity_type"] == entity_type.value`
  - `EntityTypeV2` must be consistent with registry `entity_type` values (`"player"`, `"team"`, `"lineup"`, `"game"`).
  - This is a **direct contract** on registry values.

- `level: Optional[str]`
  - Filter: `m["level"] == level`
  - `level` must match registry-level enum set enforced by `_validate_enums`.

- `category: Optional[str]`
  - Filter: `m["category"] == category`
  - Registry does not validate category content beyond presence/usage; endpoint relies on exact string equality.

**Result:** For all metrics that pass registry validation:
- Filters in `list_metrics_v2` are **compatible** with stored fields.
- There is no mismatch in expected key names or enum domains.

### 2.3 Returned Fields vs Registry Fields

`_metric_summary` exposes:

- `id`, `name`, `entity_type`, `level`, `category`, `unit`,
- `display.short_label`, `display.long_label`, `display.format`.

These are all:
- Keys present (or optional) in registry entries.
- A strict subset of validated fields (no internal keys).

**Alignment:** Endpoint summary representation is a **safe, contractually sound projection** of registry definitions.

---

## 3. Alignment: `GET /metrics/{metric_id}` vs Registry

### 3.1 Lookup Behavior

- Uses `get_metric_def(metric_id)`:

  - Honors both:
    - Canonical ids, and
    - Case-insensitive aliases from `_alias_index`.

- On `RegistryUnavailableError`:
  - Maps to `503 metrics_registry_unavailable` (same as list endpoint).

- On unknown id/alias:
  - Returns `404` with:
    - `code="metric_not_found"`, message includes requested id.

**Alignment:** Directly consistent with `get_metric_def` semantics.

### 3.2 Sanitized Metric Definition

`_sanitize_metric_definition` picks only:

- `id`, `name`, `category`, `entity_type`, `level`,
- `source`, `expression`, `base_table`, `requires`,
- `unit`, `precision`,
- `allowed_aggregations`,
- `filters_hint`,
- `aliases`,
- `display`,
- `constraints`.

**Alignment:**

- All included keys are allowed/validated by `metrics/registry.py` or explicitly modeled in the YAML.
- Internal keys like `_alias_index` are **not** exposed.
- Shape is consistent with what `resolve_metric_ref` advertises (minus `chosen_aggregation`).

---

## 4. Confirmed Matches & Behavior Contracts

This section summarizes where v2 metrics endpoints and the registry are in **explicit agreement**, based solely on repository code.

1. **Registry as Single Source of Truth**
   - `GET /metrics` and `GET /metrics/{metric_id}` read only from `load_registry()` / `get_metric_def`.
   - No alternate config paths or divergent sources.

2. **Error Handling**
   - `RegistryUnavailableError` → `503 metrics_registry_unavailable` (stable code string).
   - Unknown metric id/alias → `404 metric_not_found`.
   - These codes/messages are hard-coded in [`v2_metrics`](api/routers/v2_metrics.py:101) and follow from registry helpers.

3. **Filtering**
   - `entity_type` filter:
     - Tied to `EntityTypeV2` enum and registry-enforced values.
     - Any new registry `entity_type` outside enum would be **silently excluded** by filter logic (a future risk, but not present in current sources).
   - `level` and `category`:
     - Simple equality filters against the registry fields; behavior is fully determined by YAML content.

4. **Pagination**
   - `GET /metrics`:
     - Computes `total = len(filtered)`.
     - Applies `_normalize_pagination` with clamping behavior:
       - `page < 1` → `1`
       - `page_size < 1` → `DEFAULT_PAGE_SIZE`
       - `page_size > 500` → `500`
     - This is **stricter** than the FastAPI parameter constraints (which already enforce `ge=1`, `le=500`); the extra clamping is redundant but not contradictory.

5. **Schema Exposure**
   - `/metrics` summary view is intentionally minimal and stable.
   - `/metrics/{metric_id}` exposes a full safe definition aligned with registry validation:
     - If a registry entry passes `_validate_*`, it is guaranteed to conform to the fields that `_sanitize_metric_definition` may include.

---

## 5. Gaps / Non-Issues (Based on Concrete Code)

Only gaps noted here are **mechanical or potential**, not speculative new features:

1. **Category Semantics**
   - Registry defines `defaults.categories` metadata and assigns categories like `box_score`, but `metrics/registry.py` does not validate or enrich `category` beyond its presence.
   - `GET /metrics` uses `category` as a raw filter.
   - **Status:** Aligned; no inconsistency, but category vocabulary is effectively free-form.

2. **EntityTypeV2 / Registry entity_type Coupling**
   - A future registry change adding an `entity_type` value not present in `EntityTypeV2` would:
     - Still load (if in allowed set),
     - But such metrics could never be selected via `entity_type` filter.
   - **Status:** No such mismatch is present in current YAML; note this as a compatibility assumption, not a current defect.

3. **Alias Visibility**
   - `GET /metrics`:
     - Does **not** indicate aliases.
   - `GET /metrics/{metric_id}`:
     - Includes `aliases` (if present) via `_sanitize_metric_definition`.
   - This asymmetry is intentional per implementation; not a conflict.

4. **No Direct v2 Tools ↔ Registry Binding Yet**
   - v2 tools routers (`v2_tools_*`) reference registry integration only in TODO comments.
   - This file intentionally **does not** assert any such linkage.

---

## 6. Conclusion

Based solely on:

- [`api/routers/v2_metrics.py`](api/routers/v2_metrics.py:1),
- [`metrics/registry.yaml`](metrics/registry.yaml:1),
- [`metrics/registry.py`](metrics/registry.py:1),

the following is established:

- v2 metrics endpoints are **tightly and correctly bound** to the metrics registry load/lookup behavior.
- All exposed response shapes (`_metric_summary`, `_sanitize_metric_definition`) are subsets of the validated registry schema.
- Error and filtering semantics are consistent with registry contracts.
- No truly unmappable or conflicting fields exist between v2 metrics endpoints and the registry in the current codebase.
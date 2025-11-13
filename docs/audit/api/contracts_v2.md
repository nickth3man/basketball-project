# v2 Routers Contract Table

_Source files:_
- [`api/routers/v2_metrics.py`](api/routers/v2_metrics.py:1)
- [`api/routers/v2_saved_queries.py`](api/routers/v2_saved_queries.py:1)
- [`api/routers/v2_tools_leaderboards.py`](api/routers/v2_tools_leaderboards.py:1)
- [`api/routers/v2_tools_spans.py`](api/routers/v2_tools_spans.py:1)
- [`api/routers/v2_tools_splits.py`](api/routers/v2_tools_splits.py:1)
- [`api/routers/v2_tools_streaks.py`](api/routers/v2_tools_streaks.py:1)
- [`api/routers/v2_tools_versus.py`](api/routers/v2_tools_versus.py:1)

_All endpoints are mounted under `/api/v1` via [`api/main.create_app()`](api/main.py:171). Paths below include the full `/api/v1` prefix. v2 endpoints emphasize structured request models, explicit pagination contracts, normalized filter echo objects, and (for tools) planned integration with the metrics registry. Current implementations for v2 tools are intentionally read-only and, except where noted, placeholder/no-op with deterministic empty results._

---

## 1. Metrics v2 — `v2_metrics`

### `GET /api/v1/metrics`

**Handler:** [`list_metrics_v2`](api/routers/v2_metrics.py:70)  
**Response Model:** `PaginatedResponseV2[Dict[str, Any]]` (metric summaries)

**Query Parameters:**

- `entity_type: EntityTypeV2 | None`
  - Enum-backed, filters metrics by `entity_type` if provided.
- `level: str | None`
  - Filters by `metric["level"]`.
- `category: str | None`
  - Filters by `metric["category"]`.
- `page: int` (default `1`, `ge=1`)
- `page_size: int` (default `100`, `ge=1`, `le=500`)

**Behavior & Invariants:**

- Backed entirely by [`metrics.load_registry()`](metrics/registry.py:1); no DB access.
- On `RegistryUnavailableError`:
  - `503` with:
    - `code="metrics_registry_unavailable"`.
- Filter semantics:
  - Metric included only if all provided filters match (`entity_type`, `level`, `category`).
- Pagination:
  - Uses `_normalize_pagination`:
    - If provided values are invalid (<1 or `page_size > MAX_PAGE_SIZE`), they are clamped to defaults/max, not rejected.
  - `PaginationMetaV2.total` = count of filtered metrics.
- Response `data` entries are metric summaries via `_metric_summary`:
  - Keys: `id`, `name`, `entity_type`, `level`, `category`, `unit`, `display.short_label`, `display.long_label`, `display.format`.
- `filters`:
  - `QueryFiltersEchoV2.normalized` includes `entity_type`, `level`, `category` (normalized enum/value).

**Contracts:**

- Read-only, deterministic for a given registry snapshot.
- Stability expectation: `_metric_summary` defines public surface; internal registry keys not included here remain non-contractual.

---

### `GET /api/v1/metrics/{metric_id}`

**Handler:** [`get_metric_v2`](api/routers/v2_metrics.py:177)  
**Response Model:** `Dict[str, Any]` (sanitized metric definition)

**Path Params:**

- `metric_id: str`
  - May be actual id or alias; resolved via [`get_metric_def`](metrics/registry.py:1).

**Behavior & Invariants:**

- Loads metric definition or raises:
  - `503` `metrics_registry_unavailable` on registry load failure.
  - `404` `metric_not_found` when id/alias missing.
- Response is `_sanitize_metric_definition(metric)`:
  - Only exposes allowed keys:
    - `id`, `name`, `category`, `entity_type`, `level`, `source`, `expression`, `base_table`,
      `requires`, `unit`, `precision`, `allowed_aggregations`, `filters_hint`, `aliases`,
      `display`, `constraints`.
- No writes; pure metadata lookup.

**Contracts:**

- Sanitized schema is the **authoritative public contract** for a single metric.
- Callers must not rely on registry-internal keys that are filtered out.

---

## 2. v2 Saved Queries — `v2_saved_queries`

_Backend: JSON files under `var/saved_queries/*.json`. Persists definitions for v2 analytical tools. All operations scoped to configured `VALID_TOOL_SLUGS`._

### `GET /api/v1/saved-queries`

**Handler:** [`list_saved_queries_v2`](api/routers/v2_saved_queries.py:240)  
**Response Model:** `PaginatedResponseV2[SavedQuerySummaryV2]`

**Query Parameters:**

- `tool: str | None`
  - Optional filter; must be one of the keys in `VALID_TOOL_SLUGS` if provided.
- `page: int` (default `1`, `ge=1`)
- `page_size: int` (default `50`, `ge=1`, `le=500`)

**Behavior & Invariants:**

- If `tool` is set:
  - Validated via `_validate_tool_slug`; invalid → `400` with explicit allowed list.
  - Loads only that tool’s file.
- If `tool` is unset:
  - Iterates all `VALID_TOOL_SLUGS`, treating missing files as empty.
- Summaries:
  - Derived from on-disk `queries` entries via `_summary_from_obj`.
  - Malformed entries are skipped (best-effort robustness).
- Sorting:
  - Newest-first by `(created_at, id)` descending.
- Pagination:
  - Slice over the fully aggregated summaries.
  - `PaginationMetaV2.total` = total matching summaries.
- `filters`:
  - `QueryFiltersEchoV2.normalized = {"tool": tool or None}`.

---

### `GET /api/v1/saved-queries/{query_id}`

**Handler:** [`get_saved_query_v2`](api/routers/v2_saved_queries.py:295)  
**Response Model:** `SavedQueryDetailV2`

**Path Params:**

- `query_id: str`

**Behavior & Invariants:**

- `_find_query_by_id` scans all tool files for `queries[].id`.
- On match:
  - Returns `_detail_from_obj` including full `payload`.
- On miss:
  - `404` with:
    - `code="saved_query_not_found"`.

---

### `POST /api/v1/saved-queries`

**Handler:** [`create_saved_query_v2`](api/routers/v2_saved_queries.py:308)  
**Response Model:** `SavedQueryDetailV2`  
**Status:** `201 Created`

**Request Model:** `SavedQueryCreateRequestV2`

- `name: str` (non-empty)
- `tool: str`
  - Validated against `VALID_TOOL_SLUGS` via `_validate_tool_slug`.
- `description: str | None`
- `payload: Dict[str, Any]` (required, non-empty)

**Behavior & Invariants:**

- Validates:
  - Tool slug; else `400`.
  - Non-empty `payload`; else `422 "payload is required"`.
  - Payload structure:
    - Parsed via specific v2 query models (`LeaderboardsQueryV2`, `SpansQueryV2`, etc.) in `_validate_payload_for_tool`.
    - On validation error → `422` with details from Pydantic.
- Persists:
  - Appends new query with `id` (UUID4), timestamps, and payload.
  - Atomic write via temp file + `os.replace`.
- Response:
  - Mirrors stored object.

---

### `PUT /api/v1/saved-queries/{query_id}`

**Handler:** [`update_saved_query_v2`](api/routers/v2_saved_queries.py:362)  
**Response Model:** `SavedQueryDetailV2`

**Path Params:**

- `query_id: str`

**Request Model:** `SavedQueryUpdateRequestV2`

- `name: str | None`
  - If provided and empty → `422 "name cannot be empty"`.
- `description: Optional[Optional[str]]`
  - Can set `null` explicitly to clear description.
- `payload: Dict[str, Any] | None`
  - If provided and empty → `422`.
  - Validated via `_validate_payload_for_tool` against existing `tool`.

**Behavior & Invariants:**

- Locates existing query via `_find_query_by_id` (404 if missing).
- Applies only provided fields.
- If no changes are applied:
  - Returns current detail as-is.
- On update:
  - Sets `updated_at` to current UTC ISO.
  - Persists via `_save_tool_file`.
- All saved-queries endpoints:
  - Depend on filesystem; failures reading/writing yield `500` with descriptive messages.

---

## 3. v2 Tools — Leaderboards

### `POST /api/v1/tools/leaderboards`

**Handler:** [`leaderboards_v2`](api/routers/v2_tools_leaderboards.py:63)  
**Request Model:** `LeaderboardsQueryV2`  
**Response Model:** `LeaderboardsQueryResponseV2` (aliased `PaginatedResponseV2[LeaderboardsResultRowV2]`)

**Behavior & Invariants:**

- `_validate_query`:
  - `page.page_size <= 500` else `400`.
  - `len(metrics) <= 25` else `400`.
- Current implementation:
  - Does **not** hit the DB.
  - Constructs:
    - `PaginationMetaV2(page, min(page_size, 500), total=0)`.
    - `QueryFiltersEchoV2.normalized = _normalize_filters(query)`:
      - Includes entity/season/game/team/player/location/result filters,
        `min_games`, `min_minutes`, `min_attempts_by_metric`, `primary_metric_id`.
  - Returns empty `data` list with stable pagination/filter echo.

**Contracts:**

- Read-only, structurally validated.
- Explicit TODO notes that future behavior will integrate with metrics registry; current empty-data behavior is part of the temporary contract.

---

### `POST /api/v1/tools/leaderboards/export`

**Handler:** [`export_leaderboards_v2`](api/routers/v2_tools_leaderboards.py:130)  
**Request Model:** `LeaderboardsQueryV2`  
**Response:** `text/csv` via `PlainTextResponse`

**Behavior & Invariants:**

- Reuses `_validate_query`; same 400 conditions.
- Returns:
  - CSV with header row only (no data rows).
  - Headers derived from `_leaderboards_csv_headers()` and aligned with `LeaderboardsResultRowV2`.

---

## 4. v2 Tools — Spans

### `POST /api/v1/tools/spans`

**Handler:** [`spans_v2`](api/routers/v2_tools_spans.py:71)  
**Request Model:** `SpansQueryV2`  
**Response Model:** `SpansQueryResponseV2` (aliased `PaginatedResponseV2[SpansResultRowV2]`)

**Behavior & Invariants:**

- `_validate_query`:
  - If `page` set and `page.page_size > 500` → `400`.
  - `len(metrics) <= 25` else `400`.
  - `len(subject_ids) <= 200` else `400`.
- Pagination:
  - Uses existing `query.page` if provided; otherwise constructs default `PageSpec` via `query.page.__class__` (implementation detail).
  - `PaginationMetaV2` with `total=0` and `page_size` capped at 500.
- `filters`:
  - `QueryFiltersEchoV2.normalized = _normalize_filters(query)`:
    - Includes season/date/game_type/team/player/opponent/location/result filters,
      `subject_type`, `subject_ids`, `span_mode`.
- Returns empty `data` with deterministic echo.

**Contracts:**

- Structural validation only; computation is deferred.

---

## 5. v2 Tools — Splits

### `POST /api/v1/tools/splits`

**Handler:** [`splits_v2`](api/routers/v2_tools_splits.py:71)  
**Request Model:** `SplitsQueryV2`  
**Response Model:** `SplitsQueryResponseV2` (aliased `PaginatedResponseV2[SplitsResultRowV2]`)

**Behavior & Invariants:**

- `_validate_query`:
  - If `page` set and `page.page_size > MAX_PAGE_SIZE` → `400`.
  - `len(metrics) <= MAX_METRICS` else `400`.
  - `len(split_dimensions) <= MAX_SPLIT_DIMENSIONS` else `400`.
- Pagination:
  - Uses `query.page` or constructs via `query.page.__class__` with default values.
  - Caps `page_size` at `MAX_PAGE_SIZE`.
- Filters echo:
  - `QueryFiltersEchoV2.normalized` includes subject, season/date/game_type,
    team/player/opponent/location/result, and `split_dimensions` ids.
- Returns empty `data`, `total=0`.

**Contracts:**

- Enforces explicit resource limits for metrics and dimensions.
- Read-only placeholder over future split aggregations.

---

## 6. v2 Tools — Streaks

### `POST /api/v1/tools/streaks`

**Handler:** [`streaks_v2`](api/routers/v2_tools_streaks.py:75)  
**Request Model:** `StreaksQueryV2`  
**Response Model:** `StreaksQueryResponseV2`

**Behavior & Invariants:**

- `_validate_query`:
  - If `page` set and `page.page_size > 500` → `400`.
  - Metrics:
    - Evaluates `[stat_metric] + metrics`; combined count `<= 25` else `400`.
  - `len(subject_ids) <= 200` else `400`.
- Pagination:
  - Uses provided `PageSpecV2` or default `PageSpecV2()` (page=1, size per model defaults).
  - Caps `page_size` at 500; sets `total=0`.
- Filters echo:
  - Includes season/date, game_type, team/player/opponent/location/result filters,
    `subject_type`, `subject_ids`, `stat_metric`.
- Returns empty `data`.

**Contracts:**

- Defines shape of streak queries/responses and constraint semantics; no DB yet.

---

### `POST /api/v1/tools/streaks/export`

**Handler:** [`export_streaks_v2`](api/routers/v2_tools_streaks.py:135)  
**Request Model:** `StreaksQueryV2`  
**Response:** CSV via `PlainTextResponse`

**Behavior & Invariants:**

- Reuses `_validate_query`.
- Returns header-only CSV with fixed columns from `_streaks_csv_headers()`.

---

## 7. v2 Tools — Versus

### `POST /api/v1/tools/versus`

**Handler:** [`versus_v2`](api/routers/v2_tools_versus.py:72)  
**Request Model:** `VersusQueryV2`  
**Response Model:** `VersusQueryResponseV2` (aliased `PaginatedResponseV2[VersusResultRowV2]`)

**Behavior & Invariants:**

- `_validate_query`:
  - If `page` set and `page.page_size > MAX_PAGE_SIZE` → `400`.
  - `len(metrics) <= MAX_METRICS` else `400`.
  - `len(subject_ids) <= MAX_SUBJECT_IDS` else `400`.
- Pagination:
  - Uses `query.page` or `query.page.__class__` default.
  - Caps `page_size` at `MAX_PAGE_SIZE`; `total=0`.
- Filters echo:
  - `QueryFiltersEchoV2.normalized = _normalize_filters(query)` including:
    - subject selection, season/date/game_type,
      team/player/opponent/location/result filters,
      `versus_*` ids,
      `split_by_opponent`.
- Returns empty `data` result.

**Contracts:**

- Defines normalized versus query surface and enforcement of resource bounds.
- Placeholder; no aggregation yet.

---

## 8. Cross-Cutting v2 Contracts

Across all v2 routers in this file set:

- **Versioning & Scope**
  - All endpoints live under existing `/api/v1` prefix but expose **v2-style** contracts via:
    - `PaginatedResponseV2`, `PaginationMetaV2`, `QueryFiltersEchoV2`.
    - Dedicated v2 query/response models per tool.

- **Read-only Semantics**
  - All current implementations are read-only.
  - v2 tools endpoints intentionally return empty result sets while still:
    - Enforcing validation,
    - Emitting stable pagination metadata,
    - Returning normalized filter echoes as introspection aid.

- **Validation & Limits**
  - Each tool defines hard limits (page size, metrics count, subject id counts, split dimensions).
  - Violations yield `400` with clear messages; these limits are part of the contract.

- **Filters Echo**
  - All v2 tools and metrics listing endpoints emit `QueryFiltersEchoV2.normalized`.
  - The normalized object is JSON-serializable and structured as the canonical record of interpreted inputs.

- **Error Handling**
  - Metrics registry integration is the only v2 surface that returns `503` on backend unavailability.
  - Saved queries and filesystem operations surface `500` with clear diagnostic messages on IO/JSON failures.
  - Not-found conditions:
    - `saved_query_not_found` for missing saved queries.
    - `metric_not_found` for unknown metric ids.
  - All other v2 tools surfaces currently treat empty results as valid (no 404).

- **Future Evolution Notes (Non-speculative constraints)**
  - `TODO` comments in v2 tools routers describe planned integration with the metrics registry and ETL metadata.
  - Until implemented, clients must treat:
    - Structural validation +
    - Empty `data` with stable `filters`/`pagination`
    as the authoritative behavior.
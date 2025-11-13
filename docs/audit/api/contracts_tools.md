# Tools Routers Contract Table

_Source files:_
- [`api/routers/tools_event_finder.py`](api/routers/tools_event_finder.py:1)
- [`api/routers/tools_leaderboards.py`](api/routers/tools_leaderboards.py:1)
- [`api/routers/tools_player_finder.py`](api/routers/tools_player_finder.py:1)
- [`api/routers/tools_span.py`](api/routers/tools_span.py:1)
- [`api/routers/tools_splits.py`](api/routers/tools_splits.py:1)
- [`api/routers/tools_streaks.py`](api/routers/tools_streaks.py:1)
- [`api/routers/tools_team_finder.py`](api/routers/tools_team_finder.py:1)
- [`api/routers/tools_versus.py`](api/routers/tools_versus.py:1)

_All endpoints are mounted under `/api/v1` via [`api/main.create_app()`](api/main.py:171). Paths below include the full `/api/v1` prefix. All are read-only analytical tools operating over precomputed tables, with pagination and validation handled per-endpoint._

---

## 1. Event Finder — `tools_event_finder`

### `POST /api/v1/tools/event-finder`

**Handler:** [`event_finder`](api/routers/tools_event_finder.py:41)  
**Request Model:** `EventFinderRequest`  
**Response Model:** `PaginatedResponse[EventFinderResponseRow]`  
**Error Model:** `ErrorResponse` for 400.

**Behavior:**

- Body-driven pagination:
  - `page >= 1`, `page_size >= 1` required.
  - On violation → `400` `"page and page_size must be positive"`.
- Filters (all optional, exact/IN semantics):
  - `game_ids: List[str]` → `pbp_events.game_id IN (...)`
  - `event_types: List[str]` → `event_type IN (...)`
  - `player_ids: List[int]` → `player1_id IN (...)`
  - `team_ids: List[int]` → `team_id IN (...)`
- Query:
  - Selects from `pbp_events`.
  - Ordered by `(game_id, eventnum)` for deterministic results.
- Response:
  - `data`: events as `EventFinderResponseRow`.
  - `pagination`: `PaginationMeta`.
  - `filters`: `FiltersEcho` echoing applied filters.

**Contracts & Invariants:**

- No fuzzy search; only exact/IN lists.
- Empty result set is valid; no 404.
- Stable ordering and pagination over filtered set.

---

## 2. Leaderboards — `tools_leaderboards`

### `POST /api/v1/tools/leaderboards`

**Handler:** [`leaderboards`](api/routers/tools_leaderboards.py:205)  
**Request Model:** `LeaderboardsRequest`  
**Response Model:** `PaginatedResponse[LeaderboardsResponseRow]`  
**Error Model:** `ErrorResponse` for 400.

**Supported `(scope, stat)` combinations:**

Per `_get_scope_stat`:

- `("player_season", "pts")`
- `("player_career", "pts")`
- `("team_season", "pts")`
- `("single_game", "pts")`

Any other combination:

- → `400` `"Unsupported scope/stat combination"`.

**Common validation:**

- `page >= 1`, `page_size >= 1` else:
  - `400` `"page and page_size must be positive"`.

**Filters (subset applied depending on scope, via `filters: List[Any]`):**

- `season_end_year: int | None`
- `is_playoffs: bool | None`

**Behavior (high level):**

- Constructs scope-specific SELECT over join of core tables (e.g., `player_season`, `player_season_totals`, `players`, `games`).
- Computes:
  - `subject_id`: player or team identifier.
  - `label`: human-readable label (name/abbrev).
  - `stat`: points (season, career, team season, or single-game).
  - Optional `season_end_year` or `game_id` depending on scope.
- Applies pagination over ordered leaderboards (descending by `stat` or equivalent).
- Response `filters.raw` echoes `scope`, `stat`, and recognized filter inputs.

**Contracts & Invariants:**

- Only documented scope/stat combos are guaranteed.
- 400 for unsupported combos is stable.
- Data is read-only and derived from base stat tables.

---

## 3. Player Finder — `tools_player_finder`

### `POST /api/v1/tools/player-season-finder`

**Handler:** [`player_season_finder`](api/routers/tools_player_finder.py:80)  
**Request Model:** `PlayerSeasonFinderRequest`  
**Response Model:** `PaginatedResponse[PlayerSeasonFinderResponseRow]`  
**Error Model:** 400 for bad pagination.

**Behavior:**

- Requires `page >= 1`, `page_size >= 1`.
- Filters:
  - `player_ids: List[int]`
  - `from_season: int | None`
  - `to_season: int | None`
  - `is_playoffs: bool | None`
- Always enforces `is_total IS TRUE`.
- Joins `player_season` with `player_season_per_game`.
- Ordered by `(season_end_year, player_id, seas_id)`.
- Returns seasons as `PlayerSeasonFinderResponseRow` plus pagination and `FiltersEcho`.

### `POST /api/v1/tools/player-game-finder`

**Handler:** [`player_game_finder`](api/routers/tools_player_finder.py:159)  
**Request Model:** `PlayerGameFinderRequest`  
**Response Model:** `PaginatedResponse[PlayerGameFinderResponseRow]`.

**Behavior:**

- `page >= 1`, `page_size >= 1` enforced.
- Filters:
  - `player_ids`
  - `from_season`, `to_season`
  - `is_playoffs`
- Joins `boxscore_player` with `games`.
- Ordered by:
  - `season_end_year DESC` (newest first),
  - then `game_id`, `player_id`.
- Returns game-level lines for requested players.

**Contracts:**

- Both endpoints are POST with JSON bodies (no query params).
- On invalid pagination → 400 with stable message.
- Empty result sets allowed.

---

## 4. Span Finder — `tools_span`

### `POST /api/v1/tools/span-finder`

**Handler:** [`span_finder`](api/routers/tools_span.py:54)  
**Request Model:** `SpanFinderRequest`  
**Response Model:** `PaginatedResponse[SpanFinderResponseRow]`  
**Error Model:** 400.

**Validation:**

- `page >= 1`, `page_size >= 1` else 400.
- Exactly one of `player_id`, `team_id` must be set:
  - If both or neither → 400 `"Exactly one of player_id or team_id is required"`.
- `span_length >= 1` else 400 `"span_length must be >= 1"`.

**Behavior:**

- Subject:
  - Player: uses `boxscore_player`.
  - Team: uses `boxscore_team`.
- Builds ordered sequence per subject:
  - `(game_date_est, game_id)` order.
- Computes rolling window of length `span_length` over `pts`.
- Keeps only full windows.
- Orders spans by:
  - `value` (sum pts) DESC,
  - then `subject_id`, `start_game_id`, `end_game_id`.
- Response:
  - `SpanFinderResponseRow`:
    - `subject_id`, `start_game_id`, `end_game_id`,
    - `span_length`, `stat="pts"`, `value`.
  - `filters.raw` includes `span_length` and chosen subject.

**Contracts:**

- Deterministic ordering for identical inputs.
- No mutations; pure analytical over boxscore/games tables.

---

## 5. Splits — `tools_splits`

### `POST /api/v1/tools/splits`

**Handler:** [`splits`](api/routers/tools_splits.py:59)  
**Request Model:** `SplitsRequest`  
**Response Model:** `PaginatedResponse[SplitsResponseRow]`  
**Error Model:** 400.

**Validation:**

- `page >= 1`, `page_size >= 1` else 400.
- `subject_type` must be `"player"` or `"team"`:
  - Else 400 `"Unsupported subject_type"`.
- `split_type` must be `"home_away"` or `"versus_opponent"`:
  - Else 400 `"Unsupported split_type"`.

**Behavior:**

- Uses `boxscore_player` or `boxscore_team` joined to `games`.
- Base filters:
  - `subject_id` (player_id or team_id) from request.
- Split dimensions:
  - `home_away`:
    - `split_key` = `"home"`, `"away"`, or `"unknown"` from `is_home`.
  - `versus_opponent`:
    - `split_key` = `opponent_team_id` as string, or `"unknown"`.
- Aggregations:
  - `g`: count of games.
  - `pts_per_g`: average points.
- Ordering:
  - `g DESC`, then `split_key`.

**Contracts:**

- Response `SplitsResponseRow` contains:
  - `subject_id`, `split_key`, `g`, `pts_per_g`.
- `filters.raw` echoes subject/split inputs.
- No side effects; read-only.

---

## 6. Streak Finder — `tools_streaks`

### `POST /api/v1/tools/streak-finder`

**Handler:** [`streak_finder`](api/routers/tools_streaks.py:55)  
**Request Model:** `StreakFinderRequest`  
**Response Model:** `PaginatedResponse[StreakFinderResponseRow]`  
**Error Model:** 400.

**Validation:**

- `page >= 1`, `page_size >= 1`.
- Exactly one of `player_id` or `team_id` must be set:
  - Else 400 `"Exactly one of player_id or team_id is required"`.

**Behavior:**

- If `player_id`:
  - Metric: `pts >= 20` per game.
  - From `boxscore_player` + `games`.
- If `team_id`:
  - Metric: win (`pts > opponent_pts`) from `boxscore_team` + `games`.
- Uses window functions to:
  - Segment consecutive `metric_hit == 1` runs.
  - Compute streaks as `(start_game_id, end_game_id, length)`.
- Applies `min_length` filter via `HAVING`.
- Orders by:
  - `length DESC`,
  - then `start_game_id`.

**Contracts:**

- `StreakFinderResponseRow`:
  - `subject_id`, `start_game_id`, `end_game_id`,
  - `length`, `stat` (`"pts_ge_20"` or `"wins"`), `value=length`.
- `filters.raw` includes `min_length` and subject identifiers.
- Read-only; deterministic for same inputs.

---

## 7. Team Finder — `tools_team_finder`

### `POST /api/v1/tools/team-season-finder`

**Handler:** [`team_season_finder`](api/routers/tools_team_finder.py:77)  
**Request Model:** `TeamSeasonFinderRequest`  
**Response Model:** `PaginatedResponse[TeamSeasonFinderResponseRow]`.

**Behavior:**

- `page >= 1`, `page_size >= 1`.
- Filters:
  - `team_ids`, `from_season`, `to_season`, `is_playoffs`.
- Joins `team_season` with `team_season_totals`.
- Ordered by `(season_end_year, team_id, team_season_id)`.
- Response rows include season totals per team-season.

### `POST /api/v1/tools/team-game-finder`

**Handler:** [`team_game_finder`](api/routers/tools_team_finder.py:159)  
**Request Model:** `TeamGameFinderRequest`  
**Response Model:** `PaginatedResponse[TeamGameFinderResponseRow]`.

**Behavior:**

- `page >= 1`, `page_size >= 1`.
- Filters:
  - `team_ids`, `from_season`, `to_season`, `is_playoffs`.
- Uses `boxscore_team` + `games` (with self-join) to compute `opp_pts`.
- Ordering:
  - `season_end_year DESC`,
  - then `game_id`, `team_id`.
- Response rows:
  - `game_id`, `team_id`, `is_home`, `pts`, `opp_pts`.

**Contracts (both endpoints):**

- 400 on invalid pagination with stable message.
- Empty result allowed.
- `filters.raw` echoes request filters.

---

## 8. Versus Finder — `tools_versus`

### `POST /api/v1/tools/versus-finder`

**Handler:** [`versus_finder`](api/routers/tools_versus.py:57)  
**Request Model:** `VersusFinderRequest`  
**Response Model:** `PaginatedResponse[VersusFinderResponseRow]`  
**Error Model:** 400.

**Validation:**

- `page >= 1`, `page_size >= 1`.
- Exactly one of `player_id`, `team_id` required:
  - Else 400 `"Exactly one of player_id or team_id is required"`.

**Behavior:**

- Subject:
  - Player: `boxscore_player`.
  - Team: `boxscore_team`.
- Optional filter:
  - `opponent_ids` to restrict opponents.
- Aggregation:
  - Group by `(subject_id, opponent_id)`:
    - `g`: games played.
    - `pts_per_g`: average points vs opponent.
- Ordering:
  - `g DESC`, then `opponent_id`.

**Contracts:**

- Response entries:
  - `subject_id`, `opponent_id`, `g`, `pts_per_g`.
- `filters.raw` mirrors subject/opponent inputs.
- No writes; pure aggregation.

---

## 9. Cross-Cutting Tools Router Contracts

Across all `tools_*` routers:

- **HTTP Methods:**
  - All are `POST` except none; all documented above use POST with structured JSON bodies.
- **Pagination:**
  - Tools implement their **own** `page` / `page_size` validation (not shared `get_pagination`).
  - Common rule: `page >= 1`, `page_size >= 1`; violations → 400 with consistent message.
- **Error Semantics:**
  - Use `HTTPException` with:
    - `400` for invalid inputs / argument combinations.
    - Some specify `responses={400: {"model": ErrorResponse}}` to standardize payload.
  - No 404s; absence of matches returns empty `data`.
- **Filters Echo:**
  - All tools return `FiltersEcho(raw=...)` describing the effective filters/inputs.
- **Read-Only:**
  - All tools only perform SELECT-style queries; there are no state mutations.
- **Determinism:**
  - Each endpoint defines explicit `ORDER BY` to ensure stable pagination semantics.
- **Auth / Middleware:**
  - Subject to global middleware from [`api/main.py`](api/main.py:72):
    - API key auth (if enabled).
    - Rate limiting.
    - Logging & metrics.
    - Global error handlers for 422 / 500.

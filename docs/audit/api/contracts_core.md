# Core Routers Contract Table

_Source files:_
- [`api/routers/core_games.py`](api/routers/core_games.py:1)
- [`api/routers/core_pbp.py`](api/routers/core_pbp.py:1)
- [`api/routers/core_players.py`](api/routers/core_players.py:1)
- [`api/routers/core_seasons.py`](api/routers/core_seasons.py:1)
- [`api/routers/core_teams.py`](api/routers/core_teams.py:1)

_All endpoints are mounted under `/api/v1` in [`api/main.create_app()`](api/main.py:171). Paths below are relative to that prefix (except where `game_id`/`player_id`/`team_id`/`season` are path params). Error schemas reference [`ErrorResponse`](api/models.py:1) where applicable._

---

## 1. `core_games` Router — `tags=["games"]`

### 1.1 `GET /games`

**Summary:** Paginated listing of games with rich filtering.

- **Method & Path:** `GET /api/v1/games`
- **Handler:** [`list_games`](api/routers/core_games.py:50)
- **Response:**
  - `200 OK`: `PaginatedResponse[Game]`
    - `data`: list of `Game`
    - `pagination`: `PaginationMeta`
    - `filters`: `FiltersEcho` with applied filters.
- **Query Parameters:**
  - `game_ids: str | None`
    - Comma-separated `game_id` values.
    - Parsed via [`parse_comma_ints`](api/deps.py:66) but currently only echoed; filter behavior is effectively unspecified in code.
  - `season: int | None`
    - Filter by `season_end_year`.
  - `from_date: str | None`
    - `game_date_est >= from_date` (YYYY-MM-DD expected).
  - `to_date: str | None`
    - `game_date_est <= to_date`.
  - `is_playoffs: bool | None`
    - Filter by `is_playoffs` exact match.
  - `team_id: int | None`
    - If set, join `boxscore_team` and require participation.
  - `opponent_id: int | None`
    - If set, require `opponent_team_id` match.
- **Behavior & Invariants:**
  - Pagination via `get_pagination` → validated `page`/`page_size`.
  - Count via subquery; data ordered by `(game_date_est, game_id)`.
  - `filters.raw` echoes client-supplied filter inputs.
  - On DB errors, generic 500 from global handlers.

### 1.2 `GET /games/{game_id}`

**Summary:** Fetch a single game by ID.

- **Method & Path:** `GET /api/v1/games/{game_id}`
- **Handler:** [`get_game`](api/routers/core_games.py:166)
- **Path Params:**
  - `game_id: str`
- **Responses:**
  - `200 OK`: `Game`
  - `404 Not Found`: `ErrorResponse` with `"Game not found"`.
- **Behavior & Invariants:**
  - Selects from `games` table by exact `game_id`, limit 1.
  - Stable 404 semantics when missing.

### 1.3 `GET /games/{game_id}/boxscore-team`

**Summary:** Team-level boxscore rows for a game.

- **Method & Path:** `GET /api/v1/games/{game_id}/boxscore-team`
- **Handler:** [`get_boxscore_team`](api/routers/core_games.py:201)
- **Path Params:**
  - `game_id: str`
- **Response:**
  - `200 OK`: `List[BoxscoreTeamRow]`
- **Behavior & Invariants:**
  - Reads from `boxscore_team` for given `game_id`.
  - Ordered with home team first, then by `team_id`.
  - Returns empty list if no rows; no 404.

---

## 2. `core_pbp` Router — `tags=["pbp"]`

### 2.1 `GET /games/{game_id}/pbp`

**Summary:** Paginated play-by-play for a single game.

- **Method & Path:** `GET /api/v1/games/{game_id}/pbp`
- **Handler:** [`get_game_pbp`](api/routers/core_pbp.py:44)
- **Path Params:**
  - `game_id: str`
- **Query Parameters:**
  - `period: int | None`
    - Filter by `period`.
  - `event_type: str | None`
    - Filter by exact `event_type`.
  - `team_id: int | None`
    - Filter by `team_id` on event.
  - `player_id: int | None`
    - Filter where `player1_id == player_id`.
- **Response:**
  - `200 OK`: `PaginatedResponse[PbpEventRow]`
    - `filters.raw` always includes `"game_id"` plus provided filters.
- **Behavior & Invariants:**
  - Pagination via `get_pagination`.
  - Filters applied via `AND` conjunction.
  - Ordered by `eventnum`.
  - No explicit 404; empty page if no events for `game_id`.

---

## 3. `core_players` Router — `tags=["players"]`

### 3.1 `GET /players`

**Summary:** Paginated player directory with search and flags.

- **Method & Path:** `GET /api/v1/players`
- **Handler:** [`list_players`](api/routers/core_players.py:31)
- **Query Parameters:**
  - `player_ids: str | None`
    - Documented but not used in query logic; only echoed.
  - `q: str | None`
    - Free-text search over names (implemented within `build_players_query`).
  - `is_active: str | None`
    - Parsed via [`parse_bool`](api/db.py:151) to bool/None.
  - `hof: str | None`
    - Parsed via `parse_bool` for Hall-of-Fame filter.
  - `from_season: int | None`, `to_season: int | None`
    - Used as season filter window.
- **Response:**
  - `200 OK`: `PaginatedResponse[Player]`
    - `filters.raw` echoes all query parameters.
- **Behavior & Invariants:**
  - Uses shared query builders from [`api.db`](api/db.py:248).
  - 400 on invalid boolean strings (`parse_bool`).
  - No explicit 404; empty result set is valid.

### 3.2 `GET /players/{player_id}`

**Summary:** Single player lookup.

- **Method & Path:** `GET /api/v1/players/{player_id}`
- **Handler:** [`get_player`](api/routers/core_players.py:109)
- **Path Params:**
  - `player_id: int`
- **Responses:**
  - `200 OK`: `Player`
  - `404 Not Found`: `ErrorResponse` `"Player not found"`.
- **Behavior & Invariants:**
  - Exact match on `players.player_id`, limit 1.

### 3.3 `GET /players/{player_id}/seasons`

**Summary:** Paginated seasons for a given player.

- **Method & Path:** `GET /api/v1/players/{player_id}/seasons`
- **Handler:** [`get_player_seasons`](api/routers/core_players.py:130)
- **Path Params:**
  - `player_id: int`
- **Response:**
  - `200 OK`: `PaginatedResponse[PlayerSeasonSummary]`
    - `filters.raw = {"player_id": player_id}`.
- **Behavior & Invariants:**
  - Joins `player_season` and `player_season_per_game`.
  - Ordered by `(season_end_year, seas_id)`.
  - Empty list is valid if no seasons.

---

## 4. `core_seasons` Router — `tags=["seasons"]`

### 4.1 `GET /seasons`

**Summary:** Paginated list of seasons with filters.

- **Method & Path:** `GET /api/v1/seasons`
- **Handler:** [`list_seasons`](api/routers/core_seasons.py:31)
- **Query Parameters:**
  - `from_season: int | None`
    - `season_end_year >= from_season`.
  - `to_season: int | None`
    - `season_end_year <= to_season`.
  - `lg: str | None`
    - Filter by league code.
- **Response:**
  - `200 OK`: `PaginatedResponse[Season]`
    - `filters.raw` echoes applied filters.
- **Behavior & Invariants:**
  - Uses `get_pagination`.
  - Ordered by `season_end_year`.
  - Empty page is valid.

### 4.2 `GET /seasons/{season}`

**Summary:** Fetch season by its end year.

- **Method & Path:** `GET /api/v1/seasons/{season}`
- **Handler:** [`get_season`](api/routers/core_seasons.py:98)
- **Path Params:**
  - `season: int`
- **Responses:**
  - `200 OK`: `Season`
  - `404 Not Found`: `ErrorResponse` `"Season not found"`.
- **Behavior & Invariants:**
  - Exact match on `season_end_year`, limit 1.

---

## 5. `core_teams` Router — `tags=["teams"]`

### 5.1 `GET /teams`

**Summary:** Paginated directory of teams/franchises.

- **Method & Path:** `GET /api/v1/teams`
- **Handler:** [`list_teams`](api/routers/core_teams.py:74)
- **Query Parameters:**
  - `team_ids: str | None`
    - Comma-separated IDs; parsed via `parse_comma_ints` and applied as `IN` if present.
  - `q: str | None`
    - Case-insensitive search over `team_name`, `team_city`, `team_abbrev`.
  - `is_active: bool | None`
    - Filter by active status.
- **Response:**
  - `200 OK`: `PaginatedResponse[Team]`
    - `filters.raw` echoes applied filters.
- **Behavior & Invariants:**
  - Uses `get_pagination`.
  - Filters composed into `WHERE` conditions with `AND`.
  - Ordered by `(team_name, team_id)`.

### 5.2 `GET /teams/{team_id}`

**Summary:** Fetch single team record.

- **Method & Path:** `GET /api/v1/teams/{team_id}`
- **Handler:** [`get_team`](api/routers/core_teams.py:160)
- **Path Params:**
  - `team_id: int`
- **Responses:**
  - `200 OK`: `Team`
  - `404 Not Found`: `ErrorResponse` `"Team not found"`.
- **Behavior & Invariants:**
  - Exact match on `teams.team_id`, limit 1.

### 5.3 `GET /teams/{team_id}/seasons`

**Summary:** Paginated team-season summaries.

- **Method & Path:** `GET /api/v1/teams/{team_id}/seasons`
- **Handler:** [`get_team_seasons`](api/routers/core_teams.py:194)
- **Path Params:**
  - `team_id: int`
- **Response:**
  - `200 OK`: `PaginatedResponse[TeamSeasonSummary]`
    - `filters.raw = {"team_id": team_id}`.
- **Behavior & Invariants:**
  - Joins `team_season`, `team_season_totals`, `team_season_opponent_totals`.
  - Ordered by `(season_end_year, team_season_id)`.
  - Empty list if team has no seasons.

---

## 6. Cross-Cutting Core Router Contracts

Across all core routers:

- Pagination:
  - Implemented via `Depends(get_pagination)` where used.
  - Enforces global `page` and `page_size` constraints from [`ApiSettings`](api/config.py:9).
- Errors:
  - 404s use `ErrorResponse` with stable `"* not found"` messages.
  - Validation and unexpected errors normalized via global handlers in [`api/main.py`](api/main.py:84).
- DB Access:
  - All use `Depends(get_db)` from [`api.deps`](api/deps.py:14) (or `api.db` in `core_players`), which guarantees:
    - One async session per request.
    - 500 error if session acquisition fails.
- Response Models:
  - Explicit `response_model` specified for all documented endpoints.
  - No side-effecting operations (all core routes are read-only).
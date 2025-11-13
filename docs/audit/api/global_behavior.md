# API Global Behavior — App Bootstrap & DB Integration

_Source files:_
- [`api/main.create_app()`](api/main.py:46)
- [`api/config.ApiSettings`](api/config.py:9)
- [`api/config.get_settings()`](api/config.py:32)
- [`api/db`](api/db.py:1)
- [`api/deps`](api/deps.py:1)

## 1. Application Construction

### 1.1 Factory Pattern

The FastAPI application is constructed exclusively via [`create_app()`](api/main.py:46):

- Creates a `FastAPI` instance with:
  - `title="Local Basketball Stats API"`
  - `version="0.1.0"`
- No global mutable state beyond SQLAlchemy async engine / session factory in [`api/db`](api/db.py:36).

**Implication:**  
All runtime wiring is deterministic and repeatable across processes when `create_app()` is used (e.g., via `uvicorn` factory target `"api.main:create_app"`).

### 1.2 Settings Loading

Settings are provided by [`ApiSettings`](api/config.py:9) via [`get_settings()`](api/config.py:32):

- Constructed from environment variables with prefix `API_` (case-insensitive).
- Key fields:
  - `pg_dsn`:
    - Default: `postgresql+asyncpg://postgres:postgres@localhost:5432/basketball`
    - Used as the sole source for DB connection string.
  - `page_size_default`, `page_size_max`:
    - Govern pagination constraints enforced in [`api/deps.get_pagination`](api/deps.py:29).

At app startup:

- [`get_settings()`](api/config.py:32) is invoked inside [`create_app()`](api/main.py:63) for:
  - Early validation of configuration.
  - Priming of the LRU cache (one `ApiSettings` instance per process).

**Contract:**

- Missing or invalid env configuration surfaces as settings construction errors during app startup (not lazily on first request).
- All components depending on `get_settings()` observe a consistent, cached configuration object.

## 2. Database Lifecycle & Access

### 2.1 Engine and Session Factory

Defined in [`api/db`](api/db.py:34):

- Uses the cached [`get_settings()`](api/config.py:32) to obtain `pg_dsn`.
- Constructs a global async engine via `create_async_engine` with:
  - `pool_size=10`
  - `max_overflow=5`
  - `pool_timeout=30`
  - `pool_pre_ping=True`
- Defines `AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`.

**Behavioral Guarantees:**

- A single engine per process is created at import time.
- Connection pooling is process-local; no cross-process shared state.
- `pool_pre_ping=True` reduces the risk of broken connections causing request failures.

### 2.2 DB Session Dependency

Primary DB session provider for routers is [`api.deps.get_db`](api/deps.py:14):

- Wraps the async generator [`api.db.get_db`](api/db.py:127) to present a single `AsyncSession` instance via `async for` / `yield`.
- On normal usage:
  - Each request that depends on `get_db` receives an independent `AsyncSession`.
  - Session is always closed in `finally` of [`api.db.get_db`](api/db.py:130).
- If iteration unexpectedly completes without yielding:
  - Raises `HTTPException(500, "Database session acquisition failed")`.

**Contract for Routers:**

- Routers must import `get_db` from `api.deps`, not directly from `api.db`.
- Callers can assume:
  - A valid `AsyncSession` when dependency injection succeeds.
  - 500 error if a DB session cannot be acquired (no partial/undefined state).

### 2.3 Pagination Behavior

Two layers:

1. [`api.deps.get_pagination`](api/deps.py:29):

   - Enforced for HTTP query parameters:
     - `page >= 1` (400 if violated).
     - `page_size`:
       - Defaults to `settings.page_size_default`.
       - Must be between `1` and `settings.page_size_max` (400 otherwise).

2. [`api.db.build_pagination_query`](api/db.py:291):

   - Encapsulates limit/offset calculation given validated `(page, page_size)`.

**Contract:**

- Public HTTP endpoints relying on `get_pagination` expose predictable, validated pagination.
- Internals that use `build_pagination_query` are expected to feed it already-validated pagination values.

## 3. Global Middleware & Cross-Cutting Behavior

Middleware is registered inside [`create_app()`](api/main.py:72):

1. **Auth Middleware Wrapper**

   ```python
   @app.middleware("http")
   async def auth_check(request, call_next):
       return await auth_middleware(request, call_next)
   ```

   - Delegates to [`api.middleware.auth.auth_middleware`](api/middleware/auth.py:1).
   - Implements API key–based authorization (enabled/disabled based on configuration/env — see that module).
   - If unauthorized, requests are rejected before reaching routers.

2. **Rate Limit Middleware Wrapper**

   ```python
   @app.middleware("http")
   async def rate_limit_check(request, call_next):
       return await rate_limit_middleware(request, call_next)
   ```

   - Delegates to [`api.middleware.rate_limit.rate_limit_middleware`](api/middleware/rate_limit.py:1).
   - Provides in-memory rate limiting (nominally 100 req/min per IP).
   - On limit breach, responds with appropriate error without invoking route handlers.

3. **Request/Response Logging & Metrics**

   [`log_requests`](api/main.py:121):

   - Executed for every request after auth/rate limit middleware.
   - Captures:
     - `path`, `method`, `client_ip`, `user_agent`, `x-request-id` (or generated surrogate).
   - Logs:
     - A `"request"` event before calling `call_next`.
     - A `"response"` event after completion (or upon exception).
   - Measures latency and emits structured log fields via [`log_api_event`](api/logging_utils.py:1).
   - Calls [`record_request`](api/metrics_local.py:1) with `(path, duration_ms)`:
     - Wrapped in `try/except` to guarantee:
       - **Metrics failures never affect HTTP responses.**

**Middleware Ordering (Effective):**

1. `auth_check`
2. `rate_limit_check`
3. `log_requests`
4. Route handler

(Exact FastAPI execution order depends on declaration order; all three are registered in `create_app()` before router inclusion.)

## 4. Global Exception Handling

Registered in [`create_app()`](api/main.py:84):

1. **Validation Errors**

   - `@app.exception_handler(RequestValidationError)`
   - Logs an event `request_validation_error` at WARNING level using `log_api_event`.
   - Returns:
     - `422 Unprocessable Entity`
     - Body: [`ErrorResponse`](api/models.py:1)-shaped with generic `"Invalid request"` detail.

2. **Generic Exceptions**

   - `@app.exception_handler(Exception)`
   - Logs:
     - Exception details (`exc_type`, `path`, `method`) via `logger.exception`.
   - Returns:
     - `500 Internal Server Error`
     - Body: generic `"Internal server error"` via [`ErrorResponse`](api/models.py:1).

**Contract:**

- Internal errors are **not** leaked; clients see stable, minimal error payloads.
- Validation errors always yield a 422 with a generic message (no Pydantic-internal structure exposed).

## 5. Router Mounting & URL Namespace

Within [`create_app()`](api/main.py:171):

- `API_V1 = "/api/v1"`
- `API_V2 = "/api/v2"`

Routers:

- **Core Routers** (mounted under `/api/v1`):
  - `core_players`, `core_teams`, `core_seasons`, `core_games`, `core_pbp`
- **Tools Routers** (mounted under `/api/v1`):
  - `tools_player_finder`, `tools_team_finder`, `tools_streaks`,
    `tools_span`, `tools_versus`, `tools_event_finder`,
    `tools_leaderboards`, `tools_splits`
- **Stats Routers** (mounted under `/api/v1`):
  - `stats_player_seasons`, `stats_team_seasons`
- **v2 Routers** (mounted under `/api/v2`):
  - `v2_tools_streaks`, `v2_tools_spans`, `v2_tools_leaderboards`,
    `v2_tools_splits`, `v2_tools_versus`,
    `v2_metrics`, `v2_saved_queries`
- **Health**
  - `health.router` included as-is; responsible for `/api/v1/health/*`.
  - Additional legacy endpoint:
    - `GET /health` returns `{"status": "ok"}` without DB check.

**Contracts:**

- All first-class JSON APIs are namespaced under `/api/v1` or `/api/v2`, except:
  - `/health` as a lightweight legacy endpoint.
- Routers are expected to:
  - Use `api.deps` for DB and parsing helpers.
  - Respect pagination and validation contracts defined above.

## 6. Behavioral Invariants & Non-Goals

### 6.1 Invariants

- **No metrics or logging failure affects request success.**
- **Auth and rate limit checks run before business logic** when enabled.
- **DB access per request is bounded:**
  - One `AsyncSession` dependency per request scope.
  - Session closed reliably after use.
- **Error payloads are normalized** via `ErrorResponse` for:
  - Validation errors (422).
  - Unexpected exceptions (500).

### 6.2 Non-Goals / Out-of-Scope

- No automatic DB health checks at app startup (beyond engine creation).
- No distributed rate limiting or multi-process coordination in current implementation.
- No runtime feature toggles beyond environment-driven settings via `ApiSettings`.

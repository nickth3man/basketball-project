# Middleware Contracts & Cross-Cutting Behavior

_Source files:_
- [`api/middleware/auth.py`](api/middleware/auth.py:1)
- [`api/middleware/rate_limit.py`](api/middleware/rate_limit.py:1)
- [`api/logging_utils.py`](api/logging_utils.py:1)
- Integration points in [`api/main.create_app()`](api/main.py:46)

This document catalogs authentication, rate limiting, and logging middleware behavior, including error semantics and invariants. It is descriptive only; no runtime behavior is altered.

---

## 1. Authentication Middleware (`auth_middleware`)

**Location:** [`api/middleware/auth.py`](api/middleware/auth.py:1)  
**Registered via:** wrapper in [`api/main.create_app()`](api/main.py:72) as a `@app.middleware("http")` layer.

### 1.1 Inputs & Configuration

- Environment:
  - `API_KEY`:
    - If **unset**: auth is effectively disabled (local/dev mode).
    - If **set**: enforced for most routes.
- Request:
  - `Authorization` header
    - Expected format: `Bearer <API_KEY>`.
  - `path`: used for health endpoint bypass.

### 1.2 Behavior

1. Resolve `api_key = get_api_key()`:
   - [`get_api_key()`](api/middleware/auth.py:17) reads `API_KEY` from environment.
2. If `api_key is None`:
   - **Bypass authentication for all requests**.
   - Call `call_next(request)` directly.
3. If `api_key` is set:
   - If `request.url.path` is `/health` or `/api/v1/health`:
     - **Bypass auth** (health endpoints are always open).
   - Else:
     - Read `Authorization` header:
       - If missing:
         - `401 Unauthorized`
         - `WWW-Authenticate: Bearer`
         - Body: `{"detail": "Missing Authorization header"}`
       - If malformed (not `Bearer <token>`):
         - `401 Unauthorized`
         - `WWW-Authenticate: Bearer`
         - Body: `{"detail": "Invalid Authorization header format"}`
       - If token does not match `API_KEY`:
         - `401 Unauthorized`
         - `WWW-Authenticate: Bearer`
         - Body: `{"detail": "Invalid API key"}`
       - If valid:
         - Request passes through to `call_next(request)`.

### 1.3 Contract & Invariants

- When `API_KEY` is configured:
  - All non-health endpoints require correct `Authorization: Bearer <API_KEY>`.
- Health endpoints (`/health`, `/api/v1/health`) are always unauthenticated.
- Error responses:
  - Use FastAPI `HTTPException` with stable `detail` messages as above.
  - Do not leak secrets or configuration values.
- When `API_KEY` is not set:
  - API runs in open mode with **no** auth enforcement (explicitly allowed for local dev).

---

## 2. Rate Limit Middleware (`rate_limit_middleware`)

**Location:** [`api/middleware/rate_limit.py`](api/middleware/rate_limit.py:1)  
**Registered via:** wrapper in [`api/main.create_app()`](api/main.py:77).

### 2.1 Configuration

- In-memory only; process-local:
  - `RATE_LIMIT_REQUESTS = 100`
  - `RATE_LIMIT_WINDOW = 60` seconds
- Store:
  - `_rate_limit_store: dict[str, list[float]]`
  - Keyed by `client_ip`.

### 2.2 Behavior

1. Bypass:
   - If `request.url.path` is `/health` or `/api/v1/health`:
     - Skip rate limiting.
2. Identify client:
   - `client_ip = request.client.host` if available, else `"unknown"`.
3. Sliding window maintenance:
   - Drop timestamps older than `now - RATE_LIMIT_WINDOW`.
4. Enforcement:
   - If remaining count `>= RATE_LIMIT_REQUESTS`:
     - Raise `HTTPException`:
       - `429 Too Many Requests`
       - `detail`: `"Rate limit exceeded: 100 requests per 60s"`
       - Header: `Retry-After: "60"`.
   - Else:
     - Append current timestamp and call `call_next(request)`.

### 2.3 Contract & Invariants

- Per-process, per-IP limit: 100 requests / 60 seconds (best-effort).
- No coordination across processes or hosts.
- Health endpoints are never rate-limited.
- On limit breach:
  - Response is deterministic:
    - 429 status
    - Fixed message and `Retry-After` header.
- Uses in-memory store; potential eviction and behavior reset on process restart is expected.

---

## 3. Logging & Observability (`logging_utils`)

**Location:** [`api/logging_utils.py`](api/logging_utils.py:1)  
**Used by:** [`api.main`](api/main.py:43) and any module importing `get_logger` / `log_api_event`.

### 3.1 Root Logger Configuration

- Performed lazily by [`get_logger`](api/logging_utils.py:64) via `_configure_root_logger`:
  - If any handlers already attached to root:
    - **No changes made** (assumes host configured logging).
  - Else:
    - Reads `API_LOG_LEVEL` (default `INFO`).
    - Attaches a single `StreamHandler` to stdout.
    - Applies `JsonFormatter` to emit JSON logs with:
      - `level`
      - `logger`
      - `message`
      - Optional fields when present: `event`, `request_id`, `method`, `path`,
        `client_ip`, `user_agent`, `status_code`, `duration_ms`.

**Contract:**

- Idempotent configuration; safe to call many times.
- Structured logs are stable and machine-parseable.

### 3.2 `log_api_event` Semantics

[`log_api_event`](api/logging_utils.py:74):

- Inputs:
  - `logger`: a `logging.Logger` (e.g., from `get_logger(__name__)`).
  - `event`: event name string.
  - `level`: log level (default `INFO`).
  - `**fields`: arbitrary key/value metadata.
- Behavior:
  - If logger not enabled for `level`: no-op.
  - Filters out sensitive keys (case-insensitive match on):
    - `password`, `passwd`, `authorization`, `auth_header`,
      `token`, `access_token`, `id_token`, `refresh_token`, `secret`.
  - Logs at given level with:
    - `event` plus remaining `safe_fields` via `extra`.
- Failure handling:
  - Any exception while logging is swallowed; **logging must never break request handling**.

### 3.3 Cross-Cutting Guarantees

- Centralized, JSON-structured logging for:
  - Requests/responses (via [`api.main.log_requests`](api/main.py:121)).
  - Validation errors (via `RequestValidationError` handler).
  - Unhandled exceptions.
- Explicit safety: secrets and tokens are excluded from logs by default logic.

---

## 4. Combined Middleware & Error Semantics

Effective order in [`create_app()`](api/main.py:72):

1. `auth_check` → [`auth_middleware`](api/middleware/auth.py:22)
2. `rate_limit_check` → [`rate_limit_middleware`](api/middleware/rate_limit.py:25)
3. `log_requests` (structured logging & metrics)
4. Route handler
5. Exception handlers for:
   - `RequestValidationError` → 422 with generic error body.
   - Any other `Exception` → 500 with generic error body.

### 4.1 Interaction Rules

- Health endpoints:
  - Bypass both auth and rate limit.
  - Still go through logging and exception handlers.
- With `API_KEY` configured:
  - Unauthorized requests are rejected **before** rate limit and business logic.
- On rate limit breach:
  - 429 emitted; no route handler execution.
- Logging:
  - Applied for successful and failed requests.
  - Never alters HTTP status codes or bodies.

### 4.2 Stable Contracts

- Auth, rate limiting, and logging are **purely cross-cutting**:
  - Do not modify successful response schemas.
  - Only enforce access control, traffic shaping, and observability.
- Error responses from these layers use:
  - Standard HTTP status codes (401, 429).
  - Deterministic `detail` messages and headers.
- No middleware behavior depends on request body shape or response schema.

# ETL DB Session & Connection Semantics

_Source: [`etl/db.py`](../../../etl/db.py:1)_

This document captures how ETL code acquires connections, performs bulk loads, and manages transactions, with emphasis on safety, invariants, and non-invasive behavior.

---

## 1. Responsibilities & Scope

`etl/db.py` provides:

1. A simple **psycopg3 connection pool** and helpers:
   - `get_connection`, `release_connection`
   - `execute`, `fetchall_dicts`
   - `truncate_table`
2. **Bulk load utilities** built on PostgreSQL `COPY`:
   - `copy_from_polars`
   - `copy_from_records`
3. An (unused/incomplete) `DatabaseConnection` class and async helpers.
4. Convenience helpers for:
   - Checking table existence
   - Copying query results to Polars

Key properties:

- Single, centralized module for ETL DB interactions.
- No implicit schema changes.
- No behavioral overrides of application-level connection handling.
- Bulk-loading semantics are explicit and opt-in.

---

## 2. Inputs

### 2.1 Configuration

All connection behavior depends on `Config` from [`etl/config.py`](../../../etl/config.py:1):

- `Config.pg_dsn`:
  - Used as `conninfo` for the psycopg connection pool.
- No additional DSN-specific envs are read directly in this module; they must flow through `Config`.

### 2.2 Callers

- ETL loaders call:
  - `get_connection(config: Config) -> Connection`
  - `truncate_table(conn, table_name, cascade=False)`
  - `copy_from_polars(df, table_name, conn, columns=None)`
  - `copy_from_records(...)` (fallback when Polars is not used)
- Validation and other tooling may call:
  - `fetchall_dicts(conn, sql, params=None)`

---

## 3. Connection Lifecycle & Pooling

### 3.1 Global Pool

```python
_pool: Optional[psycopg_pool.ConnectionPool] = None
```

- `get_connection(config: Config) -> Connection`:
  - Lazily initializes `_pool` if `None`:

    ```python
    _pool = psycopg_pool.ConnectionPool(
        conninfo=config.pg_dsn,
        min_size=1,
        max_size=5,
        kwargs={"autocommit": False},
    )
    ```

  - Returns `_pool.getconn()`.
  - **Autocommit is disabled**; callers control transactions.

- `release_connection(conn: Connection) -> None`:
  - If `_pool` exists:
    - Calls `_pool.putconn(conn)`.
  - If `_pool` is `None`, the function is effectively a no-op.

**Semantics & Invariants:**

- A small shared pool (1–5) is used for ETL steps to avoid reconnect overhead.
- Connections are standard psycopg3 connections:
  - No implicit transaction boundaries beyond PostgreSQL defaults (explicitly managed by callers).
- Callers are responsible for:
  - `commit` / `rollback`
  - Returning connections via `release_connection`

**Failure Modes:**

- Invalid `pg_dsn`:
  - Pool creation or `getconn()` will raise psycopg errors at runtime.
- Not calling `release_connection`:
  - Can exhaust pool; considered a caller bug, not hidden by this module.

---

## 4. Execution & Utility Helpers

### 4.1 `fetchall_dicts(conn, sql, params=None) -> List[dict]`

- Uses `dict_row` factory.
- Returns all rows as list of dicts.
- Read-only; no schema assumptions beyond the query itself.

### 4.2 `execute(conn, sql, params=None) -> None`

- Thin wrapper around `cur.execute(sql, params or ())`.
- Caller is responsible for:
  - Providing safe SQL (this helper does not inject quoting).
  - Transaction control.

### 4.3 `truncate_table(conn, table_name, cascade=False)`

- Generates:

  ```sql
  TRUNCATE TABLE "table_name"[ CASCADE];
  ```

- Uses simple string interpolation with double quotes around `table_name`.
- Intended for internal ETL use with trusted identifiers.
- Behavior:
  - Clears table contents (and dependent tables if `cascade=True`).
  - Must be paired with correct reload logic in callers.

**Note:** This helper assumes `table_name` is a valid identifier; it is not meant for untrusted input.

---

## 5. Bulk Load Semantics

### 5.1 `copy_from_polars(df, table_name, conn, columns=None)`

Purpose:

- Efficient COPY-based ingestion from a `polars.DataFrame` into a PostgreSQL table.

Behavior:

1. If `df.is_empty()`:
   - Logs a structured info message:
     - `copy_from_polars: no rows for table=<table>; skipping`
   - Returns **without writing**.

2. Column handling:
   - If `columns` provided:
     - Build list `cols = list(columns)`.
   - Else:
     - `cols = list(df.columns)`.

3. Validations:
   - Computes `missing = [c for c in cols if c not in df.columns]`.
   - If any missing:
     - Raises `ValueError`:
       - `"DataFrame missing required columns for COPY into {table_name}: {missing}"`.
     - This is an **early, explicit failure** to catch schema mismatches.

4. Data preparation:
   - `df_to_write = df.select(cols)`.
   - Writes CSV to in-memory `io.StringIO` with header.

5. COPY execution:
   - Builds:

     ```sql
     COPY {table_name} ("col1","col2",...)
     FROM STDIN WITH (FORMAT csv, HEADER true)
     ```

   - Executes via `cur.copy_expert(sql, file_like)`.

**Invariants:**

- Ensures column alignment with target table in a controlled way.
- Skips on empty frames instead of performing empty COPY.
- Leaves transaction outcome (commit/rollback) to the caller.

### 5.2 `copy_from_records(rows, table_name, columns, conn, batch_size=50_000)`

- Fallback for iterables of tuples/lists.

Key points:

- Assembles CSV chunks in memory:
  - Joins row values with commas.
  - Uses empty string for `None`.
- Streams chunks into a `COPY` command:

  ```sql
  COPY {table_name} ("col1","col2",...)
  FROM STDIN WITH (FORMAT csv, HEADER false)
  ```

- `batch_size` controls how frequently buffered data is flushed.

**Invariants & Risks:**

- Assumes values do not contain unescaped commas/newlines; suitable for controlled ETL use.
- Like `copy_from_polars`, caller is responsible for:
  - Correct `columns` ordering.
  - Transaction boundaries.

---

## 6. `DatabaseConnection` Class & Async Helpers

`DatabaseConnection` and related async functions are present but effectively **non-functional / unused** in current ETL flows:

- `DatabaseConnection.__init__(config: Config)`:
  - Stores config; does not open connection immediately.

- `get_connection(self) -> Connection`:
  - Contains a `pass` where connection init should be.
  - Returns `self._connection` as-is.
  - As written, cannot be relied on for real connections.

- Async methods (`transaction`, `copy_from_polars`, `bulk_insert`, `execute_query`, `close`) and factories:
  - Conceptually wrap COPY/queries with logging and error handling.
  - Depend on `self.get_connection()` being implemented.
  - Not wired into existing ETL modules.
  - Presence is **non-breaking** so long as they are not used.

Global instance helpers:

- `_db_instance: Optional[DatabaseConnection] = None`
- `DatabaseConnection.get_instance(...)`
- `get_db_connection()`, `close_db_connection()`

These form a **stubbed abstraction** and should be treated as experimental; the canonical path for ETL remains the synchronous pool functions described above.

---

## 7. Table/Metadata Helpers

Two additional async utilities exist:

- `copy_table_to_polars(query: str, conn: Connection) -> pl.DataFrame`
  - Executes `query`, builds a `polars.DataFrame`.
  - Returns empty DataFrame if no rows.
  - Marked `async` but uses sync cursor; effectively synchronous.
- `table_exists(conn: Connection, table_name: str) -> bool`
  - Checks `information_schema.tables` for existence.
  - Also declared `async` but implemented synchronously.

These are helper-style functions; any mismatch between `async` signature and sync usage is a code-style concern, not used in core ETL paths.

---

## 8. Assumptions, Invariants & Failure Modes

### 8.1 Assumptions

- `Config.pg_dsn` is valid and points at the ETL target database.
- Callers:
  - Use only trusted table/column names with these helpers.
  - Manage transactions explicitly (commit/rollback).
  - Ensure `release_connection` is called for every `get_connection`.

### 8.2 Invariants

- Centralized **READ/WRITE** path for ETL:
  - All COPY/truncate helpers go through this module.
- Bulk operations:
  - Are schema-conscious (validate columns) and explicit.
- No automatic retries:
  - Failures propagate to callers to handle.

### 8.3 Failure Modes (Explicit)

- Pool/connection issues:
  - Raise psycopg/connection errors; no silent fallbacks.
- Column mismatch in COPY:
  - Raises `ValueError` rather than silently misloading.
- Misuse of async `DatabaseConnection`:
  - Would fail at runtime due to uninitialized `_connection`; not used in standard ETL scripts.

---

## 9. Summary for Track 1 Audit

- `etl/db.py` centralizes ETL database semantics around:
  - A small psycopg pool keyed by `Config.pg_dsn`.
  - Explicit truncate + COPY patterns for loaders.
- The effective contract:

  1. Obtain connections via `get_connection(config)`.
  2. Use `truncate_table` and `copy_from_polars` / `copy_from_records` for deterministic bulk loads.
  3. Return connections with `release_connection`.
  4. Allow callers to own transaction boundaries and error handling.

- The `DatabaseConnection`/async section is present but not authoritative; core ETL behavior is defined entirely by the synchronous helpers above, and this audit reflects that stable, non-breaking contract.
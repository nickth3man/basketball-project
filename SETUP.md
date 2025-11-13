# SETUP / RUNBOOK

Detailed setup guide for the local Basketball-Reference + Stathead-style clone.

This document is intentionally explicit and non-interactive so it can be used
as a runbook or CI reference.

Referenced components:

- DB schema: [`db/schema.sql`](db/schema.sql:1), [`db/migrations/`](db/migrations/001_initial_schema.sql:1)
- ETL: [`etl/`](etl/__init__.py:1), [`scripts/run_full_etl.py`](scripts/run_full_etl.py:1)
- API: [`api/`](api/__init__.py:1), [`api/main.py`](api/main.py:1)
- Frontend: [`app/`](app/page.tsx:1), [`components/`](components/index.ts:1)
- Validation: [`etl/validate_data.py`](etl/validate_data.py:1), [`etl/validate_metrics.py`](etl/validate_metrics.py:1)
- Benchmarks: [`scripts/run_benchmarks.py`](scripts/run_benchmarks.py:1)
- Tests: [`tests/`](tests/test_api_smoke.py:1)

## 1. Environment and Tooling

### 1.1 Python

- Required: Python 3.11+
- Recommended: use a dedicated virtual environment in the repo root.

Create and activate:

```bash
python -m venv .venv

# Windows
.venv\\Scripts\\activate

# Unix/macOS
source .venv/bin/activate
```

Install backend + ETL dependencies:

```bash
# Prefer:
pip install -r requirements.txt

# If not present, install based on imports:
pip install fastapi "uvicorn[standard]" sqlalchemy asyncpg "psycopg[binary]" polars pytest
```

(Use your own constraints/lockfile if provided.)

### 1.2 Node / TypeScript / Next.js

Requirements:

- Node.js 20+
- npm (ships with Node)

Install dependencies:

```bash
npm install
```

`tsconfig.json` and `.vscode/settings.json` are configured for:

- TypeScript strictness suitable for Next.js
- ESLint/Ruff integration (if enabled locally)

### 1.3 Ruff and Editor Integration

Ruff config: [`ruff.toml`](ruff.toml:1)

Recommended (optional):

```bash
pip install ruff
ruff check
```

VS Code workspace settings: [`.vscode/settings.json`](.vscode/settings.json:1)

- Suggest enabling:
  - Python: default formatter / Ruff
  - TypeScript/TSX: ESLint or built-in tooling

## 2. Database Setup

Assumes local Postgres running and accessible.

### 2.1 Create database

Create the database used by ETL/API:

```bash
createdb basketball
```

(Or via `psql` / GUI with the same name.)

### 2.2 Apply schema

Apply the base schema in one shot:

```bash
psql "postgresql://postgres:postgres@localhost:5432/basketball" -f db/schema.sql
```

If you prefer migrations explicitly:

1. Run [`db/migrations/001_initial_schema.sql`](db/migrations/001_initial_schema.sql:1)
2. Then run [`db/migrations/002_advanced_views.sql`](db/migrations/002_advanced_views.sql:1)

No modifications to these files should be made locally; treat them as authoritative.

## 3. Environment Variables

Use `.env` for local development; it is consumed by:

- ETL: [`etl/config.py`](etl/config.py:1)
- API: [`api/config.py`](api/config.py:1)
- Frontend (Next.js): `NEXT_PUBLIC_*` variables

### 3.1 Base env file

Create from example:

```bash
cp .env.example .env
```

Key variables to set explicitly:

```bash
PG_DSN=postgresql://postgres:postgres@localhost:5432/basketball
API_PG_DSN=postgresql+asyncpg://postgres:postgres@localhost:5432/basketball
CSV_ROOT=./csv_files
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Notes:

- `PG_DSN`:
  - Used by ETL helpers in [`etl/config.get_config`](etl/config.py:33)
- `API_PG_DSN`:
  - Used by FastAPI async engine in [`api/config.ApiSettings`](api/config.py:1)
- `CSV_ROOT`:
  - Directory where your input CSVs live; see [`docs/phase_0_csv_inventory.json`](docs/phase_0_csv_inventory.json:1)
- `NEXT_PUBLIC_API_BASE_URL`:
  - Read by the frontend at build/runtime to call the API.
- Optional:
  - `ETL_LOG_LEVEL`, `API_SMOKE_SKIP_DB`, etc., as needed.

## 4. Running the ETL

The ETL is orchestrated via [`scripts/run_full_etl.py`](scripts/run_full_etl.py:1),
which wires together modules under [`etl/`](etl/__init__.py:1).

Preconditions:

- Postgres is running.
- `PG_DSN` points at the target database.
- CSV files exist in `CSV_ROOT` respecting the inventory in
  [`docs/phase_0_csv_inventory.json`](docs/phase_0_csv_inventory.json:1).

Run:

```bash
python -m scripts.run_full_etl
```

Behavior:

- Uses [`etl.db.get_connection`](etl/db.py:19) for pooled psycopg3 connections.
- Loads dimensions, players, teams, games, boxscores, play-by-play, seasons, etc.
- Creates or updates derived tables required by advanced views.
- Uses metadata helpers in [`etl/load_metadata.py`](etl/load_metadata.py:1) when `etl_runs` exists.

No schema or core behavior is altered by this runbook.

## 5. Validation Harnesses (Pre-flight Checks)

Run after ETL to assert basic integrity.

### 5.1 Structural & Referential Validation

Module: [`etl/validate_data.py`](etl/validate_data.py:1)

Command:

```bash
python -m etl.validate_data
```

Checks:

- Structural:
  - Required tables exist:
    - `players`, `teams`, `games`,
      `player_season`, `team_season`,
      `boxscore_team`, `pbp_events`
  - Required advanced views exist:
    - `vw_player_season_advanced`
    - `vw_team_season_advanced`
    - `vw_player_career_aggregates`
- Referential:
  - `player_season.player_id` -> `players.player_id` (no orphans)
  - `team_season.team_id` -> `teams.team_id`
  - `boxscore_team.game_id` -> `games.game_id`
  - `pbp_events.game_id` -> `games.game_id`
- Summary:
  - Warn (non-fatal) if `players`, `teams`, or `games` have zero rows.

Exit codes:

- 0: OK (may have warnings).
- 1: Fatal structural or referential issues.
- 2: Unexpected error (connection, etc).

### 5.2 Metrics Sanity Validation

Module: [`etl/validate_metrics.py`](etl/validate_metrics.py:1)

Command:

```bash
python -m etl.validate_metrics
```

Checks (against views from [`db/migrations/002_advanced_views.sql`](db/migrations/002_advanced_views.sql:1)):

- `vw_player_season_advanced`:
  - `ts_pct`, `efg_pct` within plausible [0, 1.5] soft bounds.
  - `ws_per_48` in [-1, 1.5] soft.
  - `bpm`, `obpm`, `dbpm` in [-20, 20] soft.
  - Wider hard bounds used to flag extreme anomalies.
- `vw_team_season_advanced`:
  - `ortg`, `drtg` ~ [50, 150] soft.
  - `nrtg` ~ [-50, 50] soft.
  - Hard bounds used for fatal conditions.

Exit codes:

- 0: No hard-bound anomalies.
- 1: One or more extreme anomalies found.
- 2: Unexpected error.

## 6. Running the API

The backend is a FastAPI app with an application factory.

Module: [`api/main.py`](api/main.py:1)

Start in development:

```bash
uvicorn api.main:create_app --factory --reload
```

Behavior:

- Reads `API_PG_DSN` via [`api/config.ApiSettings`](api/config.py:1).
- Creates async engine and session in [`api/db.py`](api/db.py:1).
- Registers routers in [`api/routers/`](api/routers/__init__.py:1), including:
  - `/api/v1/players`, `/api/v1/teams`, `/api/v1/games`, etc.
  - Tools endpoints:
    - `/api/v1/tools/player-season-finder`
    - `/api/v1/tools/player-game-finder`
    - `/api/v1/tools/team-season-finder`
    - `/api/v1/tools/leaderboards`
    - plus additional splits/streak/span/versus/event finders.

Contracts:

- Responses use the standard envelope from [`api/models.PaginatedResponse`](api/models.py:28):
  - `data`: list
  - `pagination`: `{page, page_size, total, ...}`
  - `filters`: `{raw: {...}}`
- New tooling does not alter these DTOs.

## 7. Running the Frontend

Frontend: Next.js app in [`app/`](app/page.tsx:1)

Ensure:

- API is running and reachable at `NEXT_PUBLIC_API_BASE_URL`.

Start dev server:

```bash
npm run dev
```

Navigate:

- `http://localhost:3000/`
- Tools:
  - `/tools/player-season-finder`
  - `/tools/player-game-finder`
  - `/tools/team-season-finder`
  - `/tools/leaderboards`
  - `/tools/splits`, `/tools/streak-finder`, `/tools/span-finder`,
    `/tools/versus-finder`, etc.
- Core:
  - `/players`, `/teams`, `/games`, `/seasons` and detail routes.

## 8. Tests and API Contract Smoke

Run all tests:

```bash
pytest
```

Key suites:

- [`tests/test_api_smoke.py`](tests/test_api_smoke.py:1)
  - Starts the FastAPI app in-process.
  - Uses `API_PG_DSN` (set or defaults) to reach the DB.
  - Verifies core endpoints and tools return:
    - `data`, `pagination`, `filters` with expected shapes.
  - Optional gating:
    - `API_SMOKE_SKIP_DB=true` skips DB-dependent tests.
- [`tests/test_tools_endpoints.py`](tests/test_tools_endpoints.py:1)
  - Deeper coverage of tools endpoints; treated as canonical for contract shape.

These tests are read-only and do not mutate data.

## 9. Performance Benchmarks

Helper: [`scripts/run_benchmarks.py`](scripts/run_benchmarks.py:1)

Prerequisites:

- API running (e.g. via `uvicorn`).
- DB loaded via ETL.

Run:

```bash
python -m scripts.run_benchmarks
```

Configuration:

- `API_BASE_URL` (default `http://localhost:8000`)
- `BENCH_N` (default `5`)

Benchmarked endpoints (HTTP-level):

- `GET /api/v1/players` (small page)
- `POST /api/v1/tools/player-season-finder`
- `POST /api/v1/tools/player-game-finder`
- `POST /api/v1/tools/team-season-finder`
- `POST /api/v1/tools/leaderboards`

Output:

- JSON printed to stdout per endpoint:
  - `avg_ms`, `p95_ms`, `max_ms`
  - `status_codes`
  - `ok` flag (true if any 200 seen)

This is intentionally lightweight, suitable for local timing and CI smoke.

## 10. Legal / Data Notes

- This project does NOT ship proprietary Basketball-Reference or Stathead data.
- You are responsible for:
  - Obtaining input data from permitted sources.
  - Respecting all applicable terms of service.
- The schema and tools are designed to work with:
  - Publicly licensed or self-scraped data that you are legally allowed to use.
  - Locally stored CSVs referenced via `CSV_ROOT`.

## 11. Summary: Zero → Full Stack

Canonical sequence to go from empty environment to full stack:

1. Clone repo and create Python venv.
2. Install Python and Node dependencies.
3. Start local Postgres, create `basketball` DB.
4. Apply [`db/schema.sql`](db/schema.sql:1) (and migrations if using them directly).
5. Configure `.env` with:
   - `PG_DSN`, `API_PG_DSN`, `CSV_ROOT`, `NEXT_PUBLIC_API_BASE_URL`.
6. Place CSVs under `CSV_ROOT` following [`docs/phase_0_csv_inventory.json`](docs/phase_0_csv_inventory.json:1).
7. Run ETL:
   - `python -m scripts.run_full_etl`
8. Run validations:
   - `python -m etl.validate_data`
   - `python -m etl.validate_metrics`
9. Start API:
   - `uvicorn api.main:create_app --factory --reload`
10. Start frontend:
    - `npm run dev`
11. Run tests:
    - `pytest`
12. Run benchmarks:
    - `python -m scripts.run_benchmarks`

All additions (validation modules, benchmarks, docs, smoke tests) are additive and
do not change the core schema, ETL, API contracts, or frontend UX.

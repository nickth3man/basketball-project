# Local Basketball-Reference + Stathead-style Clone

Local-first, open-source-powered clone of core Basketball-Reference and Stathead-style functionality:

- Explorer-style browsing for players, teams, games, and seasons.
- Advanced stat views and finder-style tools (player seasons, games, leaderboards, splits, etc.).
- Runs entirely on your machine using public/derivable data and local Postgres.

This repository is designed to be:

- Reproducible end-to-end: schema, ETL, API, frontend.
- Inspectable: no opaque services, no hidden logic.
- Safe: no proprietary Basketball-Reference / Stathead data is shipped.

## Architecture Overview

- Postgres database
  - Schema and views in [`db/schema.sql`](db/schema.sql:1) and migrations under [`db/migrations/`](db/migrations/001_initial_schema.sql:1).
- ETL pipeline (Python)
  - Code under [`etl/`](etl/__init__.py:1)
  - Orchestrated by [`scripts/run_full_etl.py`](scripts/run_full_etl.py:1)
  - Uses environment-driven config ([`etl/config.py`](etl/config.py:1)) and [`etl/db.py`](etl/db.py:1) for connections.
- FastAPI backend
  - Application factory: [`api/main.py:create_app`](api/main.py:1)
  - Settings: [`api/config.py`](api/config.py:1)
  - Async SQLAlchemy session management: [`api/db.py`](api/db.py:1), [`api/deps.py`](api/deps.py:1)
  - Routers under [`api/routers/`](api/routers/__init__.py:1)
  - Response models / DTOs: [`api/models.py`](api/models.py:1)
- Next.js + TypeScript frontend
  - Next 13+ `app/` router: [`app/`](app/page.tsx:1)
  - Feature pages for tools, players, teams, games under `app/*`
  - Shared components: [`components/`](components/index.ts:1)
- Tooling / tests
  - Linting/config: [`ruff.toml`](ruff.toml:1), [`.vscode/settings.json`](.vscode/settings.json:1)
  - API tests: [`tests/test_api_smoke.py`](tests/test_api_smoke.py:1), [`tests/test_tools_endpoints.py`](tests/test_tools_endpoints.py:1)
- New validation and benchmark helpers
  - Data validation: [`etl/validate_data.py`](etl/validate_data.py:1)
  - Metrics sanity checks: [`etl/validate_metrics.py`](etl/validate_metrics.py:1)
  - HTTP benchmarks: [`scripts/run_benchmarks.py`](scripts/run_benchmarks.py:1)

## Quickstart

Prerequisites:

- Python 3.11+
- Node.js 20+
- Local PostgreSQL instance
- Recommended: virtual environment (venv) for Python

### 1. Clone and create virtualenv

```bash
git clone https://github.com/your-org/basketball-project.git
cd basketball-project

python -m venv .venv
# Windows
.venv\\Scripts\\activate
# Unix
source .venv/bin/activate
```

Install Python dependencies (if `requirements.txt` or equivalent exists in this repo):

```bash
pip install -r requirements.txt
```

(If no lockfile is present, install the libraries referenced in `api/`, `etl/`, and tests:
`fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `psycopg[binary]`, `polars`, `pytest`, etc.)

### 2. Install frontend dependencies

```bash
npm install
```

### 3. Configure environment

Copy the example env file and adjust:

```bash
cp .env.example .env
```

Key variables (keep explicit):

- `PG_DSN`
  - Used by ETL to connect to Postgres.
  - Example: `postgresql://postgres:postgres@localhost:5432/basketball`
- `API_PG_DSN`
  - Used by FastAPI / SQLAlchemy async engine.
  - Example: `postgresql+asyncpg://postgres:postgres@localhost:5432/basketball`
- `CSV_ROOT`
  - Root directory for your local CSV inputs.
- `NEXT_PUBLIC_API_BASE_URL`
  - Base URL for the frontend to call the API (e.g. `http://localhost:8000`).

These are consumed by:

- ETL via [`etl/config.get_config()`](etl/config.py:33)
- API via [`api/config.ApiSettings`](api/config.py:1)
- Frontend via standard Next.js env handling.

### 4. Create database and apply schema

Create the `basketball` database (example):

```bash
createdb basketball
```

Apply the schema:

```bash
psql "$PG_DSN" -f db/schema.sql
```

If you use a migration tool, run [`db/migrations/001_initial_schema.sql`](db/migrations/001_initial_schema.sql:1) then [`db/migrations/002_advanced_views.sql`](db/migrations/002_advanced_views.sql:1) in order.

### 5. Run the ETL

Populate the database from your local CSV inventory (see [`docs/phase_0_csv_inventory.json`](docs/phase_0_csv_inventory.json:1)):

```bash
python -m scripts.run_full_etl
```

This will:

- Load dimensions, games, boxscores, play-by-play, player/team seasons, etc.
- Track runs via metadata helpers when the `etl_runs` table exists.

### 6. Start the API

Use the FastAPI factory:

```bash
uvicorn api.main:create_app --factory --reload
```

This will:

- Use `API_PG_DSN` for the async engine.
- Expose core and tools endpoints under `/api/v1/...`.

### 7. Start the frontend

With the API running:

```bash
npm run dev
```

Then open:

- `http://localhost:3000` for the main app.
- Tools and explorers under `/tools/*`, `/players`, `/teams`, `/games`, etc.

## Running Tests

Tests are designed to be schema/shape aware and non-destructive.

```bash
pytest
```

Notes:

- `tests/test_api_smoke.py` uses the configured `API_PG_DSN` and expects a reachable DB.
- `API_SMOKE_SKIP_DB=true` can be set to skip DB-backed smoke tests.
- `tests/test_tools_endpoints.py` exercises tools endpoints more deeply.

## Validation Harnesses

Use these as pre-flight / CI checks after ETL and before exposing the app.

1) Data validation:

```bash
python -m etl.validate_data
```

Performs:

- Structural checks:
  - Ensures key tables exist:
    - `players`, `teams`, `games`, `player_season`, `team_season`,
      `boxscore_team`, `pbp_events`
  - Ensures advanced views from migrations exist:
    - `vw_player_season_advanced`,
      `vw_team_season_advanced`,
      `vw_player_career_aggregates`
- Referential integrity (query-based, does not rely on DB FKs):
  - Orphan `player_season.player_id` not in `players`
  - Orphan `team_season.team_id` not in `teams`
  - Orphan `boxscore_team.game_id` not in `games`
  - Orphan `pbp_events.game_id` not in `games`
- Summary checks:
  - Warns if `players`, `teams`, or `games` row counts are zero.

Exit codes:

- 0: all checks passed (maybe with warnings).
- 1: structural or referential failures.
- 2: unexpected error (e.g., connection issues).

2) Metrics sanity:

```bash
python -m etl.validate_metrics
```

Performs sanity checks (against views from [`db/migrations/002_advanced_views.sql`](db/migrations/002_advanced_views.sql:1)):

- On `vw_player_season_advanced`:
  - `ts_pct` in [0, 1.5] soft, [0, 3.0] hard
  - `efg_pct` in [0, 1.5] soft, [0, 3.0] hard
  - `ws_per_48` in [-1, 1.5] soft, [-5, 5] hard
  - `bpm`, `obpm`, `dbpm` in [-20, 20] soft, [-40, 40] hard
- On `vw_team_season_advanced`:
  - `ortg`, `drtg` in [50, 150] soft, [0, 300] hard
  - `nrtg` in [-50, 50] soft, [-200, 200] hard

Behavior:

- Logs soft bound violations as warnings (first N rows sampled).
- Exits non-zero if hard-bound violations (extreme anomalies) are found.

## Performance Benchmarks

Run simple HTTP benchmarks against a running API:

```bash
python -m scripts.run_benchmarks
```

Configuration:

- `API_BASE_URL` (default `http://localhost:8000`)
- `BENCH_N` (requests per endpoint, default `5`)

Endpoints benchmarked:

- `GET /api/v1/players` (small page)
- `POST /api/v1/tools/player-season-finder`
- `POST /api/v1/tools/player-game-finder`
- `POST /api/v1/tools/team-season-finder`
- `POST /api/v1/tools/leaderboards`

Output:

- JSON to stdout with, per endpoint:
  - `name`, `method`, `url`
  - `n`
  - `avg_ms`, `p95_ms`, `max_ms`
  - `ok` (whether any run returned 200)
  - `status_codes` (unique response codes)

## From Zero to Full Stack

End-to-end sequence from a clean clone:

1) Set up Python venv and install backend/ETL deps.
2) Install Node deps with `npm install`.
3) Create Postgres DB and apply [`db/schema.sql`](db/schema.sql:1) (or run migrations).
4) Configure `.env` with:
   - `PG_DSN`, `API_PG_DSN`, `CSV_ROOT`, `NEXT_PUBLIC_API_BASE_URL`.
5) Run ETL: `python -m scripts.run_full_etl`.
6) Run validations:
   - `python -m etl.validate_data`
   - `python -m etl.validate_metrics`
7) Start API:
   - `uvicorn api.main:create_app --factory --reload`
8) Start frontend:
   - `npm run dev`
9) Run tests:
   - `pytest`
10) Run benchmarks:
    - `python -m scripts.run_benchmarks`

All new scripts and docs are additive and do not modify:

- The SQL schema or migrations.
- Core ETL behavior.
- API endpoint contracts or response envelopes.
- Frontend routes or UX flows.

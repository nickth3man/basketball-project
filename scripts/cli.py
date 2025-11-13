"""
Unified CLI for the Local Basketball-Reference + Stathead-style Clone.

Usage:

    python -m scripts.cli <command> [options]

Commands (high level):

    init-db         Initialize database schema using db/migrations/*.sql
    run-etl         Run ETL pipeline (delegates to scripts.run_full_etl)
    validate        Run validation suite and write JSON reports
    run-api         Start FastAPI application via uvicorn
    run-frontend    Run Next.js dev server (npm run dev)
    run-benchmarks  Run HTTP benchmarks against the API
    status          Run read-only diagnostics across core components

Notes:

- Non-interactive and automation-friendly.
- Uses existing config helpers in etl/config.py, etl/db.py, api/config.py.
- Returns exit code 0 on success, non-zero on failure.
- Existing entrypoints (scripts/run_full_etl.py, scripts/run_benchmarks.py)
  are preserved and remain directly runnable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from etl.config import get_config as get_etl_config
from etl.db import (
    get_connection as etl_get_connection,
)
from etl.db import (
    release_connection as etl_release_connection,
)
from etl.validate import (
    check_awards_and_draft,
    check_fk_integrity,
    check_games_integrity,
    check_player_season_consistency,
    check_team_season_consistency,
)
from metrics.registry import RegistryUnavailableError, load_registry
from scripts import run_benchmarks as benchmarks_module
from scripts import run_full_etl as run_full_etl_module

try:
    from api.main import create_app
except Exception:  # noqa: BLE001
    # Import errors will be surfaced where needed (e.g., run-api/status).
    create_app = None  # type: ignore[assignment]

try:
    import psycopg
except Exception:  # noqa: BLE001
    # psycopg is optional; required only for init-db.
    psycopg = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def _print_err(msg: str) -> None:
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def _load_sql_files(migrations_dir: Path) -> List[Path]:
    sql_files = sorted(p for p in migrations_dir.glob("*.sql") if p.is_file())
    return sql_files


def _ensure_schema_migrations_table(
    conn: "psycopg.Connection",  # type: ignore[name-defined]
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    conn.commit()


def _get_applied_migrations(
    conn: "psycopg.Connection",  # type: ignore[name-defined]
) -> set[str]:
    with conn.cursor() as cur:
        cur.execute("SELECT filename FROM schema_migrations")
        rows = cur.fetchall()
    return {r[0] for r in rows}


def _apply_migration(
    conn: "psycopg.Connection",  # type: ignore[name-defined]
    path: Path,
) -> None:
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
        cur.execute(
            "INSERT INTO schema_migrations (filename) VALUES (%s)",
            (path.name,),
        )


def _status_line(name: str, status: str, detail: str = "") -> str:
    if detail:
        return f"{name:16s} {status:5s} - {detail}"
    return f"{name:16s} {status:5s}"


# ---------------------------------------------------------------------------
# Subcommand implementations
# ---------------------------------------------------------------------------


def cmd_init_db(args: argparse.Namespace) -> int:
    """
    Initialize database schema from db/migrations/.

    Uses PG* environment variables:

        PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

    Idempotent:
    - Creates schema_migrations if missing.
    - Applies each .sql in db/migrations in sorted order once.
    """
    if psycopg is None:
        _print_err("psycopg is required for init-db but is not installed")
        return 1

    host = os.getenv("PGHOST")
    port = os.getenv("PGPORT")
    user = os.getenv("PGUSER")
    password = os.getenv("PGPASSWORD")
    database = os.getenv("PGDATABASE")

    if not all([host, port, user, password, database]):
        _print_err(
            "Missing required PG* environment variables. "
            "Expected PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE."
        )
        return 1

    dsn = "host={h} port={p} dbname={d} user={u} password={pw}".format(
        h=host,
        p=port,
        d=database,
        u=user,
        pw=password,
    )

    migrations_dir = Path("db") / "migrations"
    if not migrations_dir.is_dir():
        _print_err(f"Migrations directory not found: {migrations_dir}")
        return 1

    sql_files = _load_sql_files(migrations_dir)
    if not sql_files:
        _print("No migration files found; nothing to do.")
        return 0

    try:
        with psycopg.connect(dsn) as conn:  # type: ignore[call-arg]
            _ensure_schema_migrations_table(conn)
            applied = _get_applied_migrations(conn)

            for path in sql_files:
                if path.name in applied:
                    _print(
                        f"[init-db] Skipping already applied migration: {path.name}",
                    )
                    continue

                _print(f"[init-db] Applying migration: {path.name}")
                try:
                    with conn.transaction():
                        _apply_migration(conn, path)
                    _print(f"[init-db] Applied: {path.name}")
                except Exception as exc:  # noqa: BLE001
                    _print_err(f"[init-db] Failed applying {path.name}: {exc}")
                    conn.rollback()
                    return 1

    except Exception as exc:  # noqa: BLE001
        _print_err(f"[init-db] Connection or migration failure: {exc}")
        return 1

    _print("[init-db] All migrations applied successfully.")
    return 0


def cmd_run_etl(args: argparse.Namespace) -> int:
    """
    Delegate to scripts.run_full_etl without spawning a new process.

    Maps CLI options to run_full_etl's parser/environment model.
    """
    # Use ETL config for defaults.
    # Use ETL config for env defaults; run_full_etl handles reading it.
    get_etl_config()

    # Build synthetic argv compatible with scripts.run_full_etl._parse_args.
    etl_argv: List[str] = []

    if args.mode:
        etl_argv.extend(["--mode", args.mode])

    if args.seasons:
        for s in args.seasons:
            etl_argv.extend(["--season", str(s)])

    if args.start_date:
        etl_argv.extend(["--start-date", args.start_date])

    if args.end_date:
        etl_argv.extend(["--end-date", args.end_date])

    if args.subset:
        etl_argv.extend(["--subset", args.subset])

    if args.dry_run:
        etl_argv.append("--dry-run")

    # Run via the module's own entrypoint so behavior stays centralized.
    # scripts.run_full_etl.main() already returns an int exit code.
    try:
        # Temporarily patch sys.argv the way argparse expects.
        old_argv = sys.argv
        sys.argv = [old_argv[0]] + etl_argv
        try:
            exit_code = run_full_etl_module.main()
        finally:
            sys.argv = old_argv
    except SystemExit as exc:
        # In case run_full_etl.main() calls sys.exit(...)
        code = int(exc.code) if isinstance(exc.code, int) else 1
        return code
    except Exception as exc:  # noqa: BLE001
        _print_err(f"[run-etl] Unexpected error: {exc}")
        return 1

    return int(exit_code)


def cmd_validate(args: argparse.Namespace) -> int:
    """
    Run validation checks and emit JSON reports under var/reports/validation.
    """
    config = get_etl_config()
    conn = etl_get_connection(config)

    reports_dir = Path("var") / "reports" / "validation"
    reports_dir.mkdir(parents=True, exist_ok=True)

    summary: Dict[str, Any] = {
        "checks": [],
    }

    def _run_check(
        name: str,
        fn,
        critical: bool = True,
    ) -> Tuple[str, str]:
        try:
            fn(conn)
            status = "passed"
            summary["checks"].append(
                {
                    "name": name,
                    "status": status,
                    "critical": critical,
                }
            )
            return name, "OK"
        except Exception as exc:  # noqa: BLE001
            status = "failed" if critical else "warn"
            summary["checks"].append(
                {
                    "name": name,
                    "status": status,
                    "critical": critical,
                    "error": str(exc),
                }
            )
            if critical:
                return name, f"FAIL ({exc})"
            return name, f"WARN ({exc})"

    # Core checks from etl.validate (critical)
    results: List[Tuple[str, str]] = []
    results.append(
        _run_check(
            "fk_integrity",
            check_fk_integrity,
            critical=True,
        )
    )
    results.append(
        _run_check(
            "player_season_consistency",
            check_player_season_consistency,
            critical=True,
        )
    )
    results.append(
        _run_check(
            "team_season_consistency",
            check_team_season_consistency,
            critical=True,
        )
    )
    results.append(
        _run_check(
            "games_integrity",
            check_games_integrity,
            critical=True,
        )
    )
    # Awards/draft checks are treated as critical to match ETL validation expectations.
    results.append(
        _run_check(
            "awards_and_draft",
            check_awards_and_draft,
            critical=True,
        )
    )

    # Persist report.
    report_path = reports_dir / "validation_report.json"
    with report_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    # Human-readable summary.
    passed = sum(1 for c in summary["checks"] if c["status"] == "passed")
    failed = sum(1 for c in summary["checks"] if c["status"] == "failed")
    warn = sum(1 for c in summary["checks"] if c["status"] == "warn")

    _print(
        f"[validate] checks: passed={passed}, warn={warn}, failed={failed}, "
        f"report={report_path}"
    )

    etl_release_connection(conn)

    # Non-zero if any critical validations failed.
    return 0 if failed == 0 else 1


def cmd_run_api(args: argparse.Namespace) -> int:
    """
    Start the FastAPI app using uvicorn programmatically.
    """
    if create_app is None:
        _print_err("[run-api] Unable to import api.main:create_app")
        return 1

    try:
        import uvicorn
    except Exception:  # noqa: BLE001
        # uvicorn is an external dependency; surface a clear message.
        _print_err("[run-api] uvicorn is required but not installed")
        return 1

    host = args.host
    port = int(args.port)
    reload_flag = bool(args.reload)

    # Determine log level.
    log_level = os.getenv("API_LOG_LEVEL", "info")

    if reload_flag:
        # Standard dev reload server (single worker).
        uvicorn.run(
            "api.main:create_app",
            factory=True,
            host=host,
            port=port,
            reload=True,
            log_level=log_level,
        )
        return 0

    # Production-style: allow multiple workers via API_WORKERS.
    workers = 1
    raw_workers = os.getenv("API_WORKERS")
    if raw_workers:
        try:
            parsed = int(raw_workers)
            if parsed > 1:
                workers = parsed
        except ValueError:
            workers = 1

    # When using multiple workers, point uvicorn at the factory reference.
    uvicorn.run(
        "api.main:create_app",
        factory=True,
        host=host,
        port=port,
        reload=False,
        log_level=log_level,
        workers=workers,
    )
    return 0


def cmd_run_frontend(args: argparse.Namespace) -> int:
    """
    Run Next.js dev server via `npm run dev` from repo root.

    Designed for local development workflows only.
    """
    cmd = ["npm", "run", "dev"]
    proc = subprocess.Popen(
        cmd,
        stdout=sys.stdout,
        stderr=sys.stderr,
        cwd=str(Path(".").resolve()),
    )
    try:
        return_code = proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        return_code = proc.wait()
    return int(return_code)


def cmd_run_benchmarks(args: argparse.Namespace) -> int:
    """
    Delegate to scripts.run_benchmarks module.
    """
    try:
        report = benchmarks_module.run_benchmarks()
        # Keep behavior consistent with original script: print JSON.
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:  # noqa: BLE001
        _print_err(f"[run-benchmarks] Error: {exc}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """
    Read-only diagnostics:

    1) DB connectivity via etl.db helpers.
    2) Latest ETL run metadata (if etl_runs exists).
    3) Metrics registry load.
    4) API wiring via create_app().
    """
    overall_ok = True

    # 1) DB connectivity (critical)
    db_status = "FAIL"
    db_detail = ""
    try:
        config = get_etl_config()
        conn = etl_get_connection(config)
        db_status = "OK"
        db_detail = "Connected via etl.db"
    except Exception as exc:  # noqa: BLE001
        overall_ok = False
        db_status = "FAIL"
        db_detail = str(exc)
        conn = None  # type: ignore[assignment]
    _print(_status_line("db", db_status, db_detail))

    # 2) ETL metadata (non-fatal)
    if conn is not None:
        latest_status = "WARN"
        latest_detail = "etl_runs table missing"
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT to_regclass('public.etl_runs')
                    """
                )
                row = cur.fetchone()
                if row and row[0]:
                    cur.execute(
                        """
                        SELECT
                            etl_run_id,
                            job_name,
                            mode,
                            status,
                            started_at,
                            finished_at
                        FROM etl_runs
                        ORDER BY etl_run_id DESC
                        LIMIT 1
                        """
                    )
                    latest = cur.fetchone()
                    if latest:
                        (
                            etl_run_id,
                            job_name,
                            mode,
                            status,
                            started_at,
                            finished_at,
                        ) = latest
                        latest_status = "OK"
                        latest_detail = (
                            f"latest_run id={etl_run_id} job={job_name} "
                            f"mode={mode} status={status} "
                            f"started_at={started_at} "
                            f"finished_at={finished_at}"
                        )
                    else:
                        latest_status = "WARN"
                        latest_detail = "etl_runs table empty"
            _print(_status_line("etl_metadata", latest_status, latest_detail))
        except Exception as exc:  # noqa: BLE001
            _print(
                _status_line(
                    "etl_metadata",
                    "WARN",
                    f"error reading etl_runs ({exc})",
                )
            )
        finally:
            etl_release_connection(conn, config)  # type: ignore[arg-type]

    # 3) Metrics registry (critical)
    metrics_status = "OK"
    metrics_detail = "Loaded"
    try:
        load_registry()
    except RegistryUnavailableError as exc:
        metrics_status = "FAIL"
        metrics_detail = str(exc)
        overall_ok = False
    except Exception as exc:  # noqa: BLE001
        metrics_status = "FAIL"
        metrics_detail = str(exc)
        overall_ok = False
    _print(_status_line("metrics_registry", metrics_status, metrics_detail))

    # 4) API wiring via create_app (critical)
    api_status = "OK"
    api_detail = "create_app() constructed"
    if create_app is None:
        api_status = "FAIL"
        api_detail = "api.main.create_app not importable"
        overall_ok = False
    else:
        try:
            app = create_app()  # noqa: F841
        except Exception as exc:  # noqa: BLE001
            api_status = "FAIL"
            api_detail = str(exc)
            overall_ok = False
    _print(_status_line("api", api_status, api_detail))

    return 0 if overall_ok else 1


# ---------------------------------------------------------------------------
# Argument parsing / dispatch
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.cli",
        description="Unified CLI for local basketball project",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init-db
    p_init = subparsers.add_parser(
        "init-db",
        help="Initialize database schema from db/migrations",
    )
    p_init.set_defaults(func=cmd_init_db)

    # run-etl
    p_etl = subparsers.add_parser(
        "run-etl",
        help="Run ETL pipeline (delegates to scripts.run_full_etl)",
    )
    p_etl.add_argument(
        "--mode",
        choices=[
            "full",
            "incremental_by_season",
            "incremental_by_date_range",
            "subset",
            "dry_run",
        ],
        default="full",
    )
    p_etl.add_argument(
        "--season",
        dest="seasons",
        action="append",
        help="Season end year for incremental_by_season (repeatable)",
    )
    p_etl.add_argument(
        "--start-date",
        dest="start_date",
        help="Start date (YYYY-MM-DD) for incremental_by_date_range",
    )
    p_etl.add_argument(
        "--end-date",
        dest="end_date",
        help="End date (YYYY-MM-DD) for incremental_by_date_range",
    )
    p_etl.add_argument(
        "--subset",
        dest="subset",
        help=(
            "Comma-separated subset of loaders to run "
            "(dimensions,player_seasons,team_seasons,games,boxscores,"
            "pbp,awards,inactive,validations)"
        ),
    )
    p_etl.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="Alias for --mode=dry_run (no writes; validations only)",
    )
    p_etl.set_defaults(func=cmd_run_etl)

    # validate
    p_val = subparsers.add_parser(
        "validate",
        help="Run validation suite and write JSON report",
    )
    p_val.set_defaults(func=cmd_validate)

    # run-api
    p_api = subparsers.add_parser(
        "run-api",
        help="Start FastAPI application via uvicorn",
    )
    p_api.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface (default: 0.0.0.0)",
    )
    p_api.add_argument(
        "--port",
        default=8000,
        type=int,
        help="Port (default: 8000)",
    )
    p_api.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (dev mode, single worker)",
    )
    p_api.set_defaults(func=cmd_run_api)

    # run-frontend
    p_front = subparsers.add_parser(
        "run-frontend",
        help="Run Next.js dev server (npm run dev)",
    )
    p_front.set_defaults(func=cmd_run_frontend)

    # run-benchmarks
    p_bench = subparsers.add_parser(
        "run-benchmarks",
        help="Run API benchmarks",
    )
    p_bench.set_defaults(func=cmd_run_benchmarks)

    # status
    p_status = subparsers.add_parser(
        "status",
        help=("Run diagnostics (DB, ETL metadata, metrics registry, API wiring)"),
    )
    p_status.set_defaults(func=cmd_status)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 1
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())

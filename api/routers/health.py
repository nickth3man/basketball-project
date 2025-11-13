from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, status
from metrics.registry import RegistryUnavailableError, load_registry
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.db import AsyncSessionLocal
from api.logging_utils import get_logger, log_api_event
from api.models import HealthStatus, ReadinessCheck, ReadinessResponse

logger = get_logger(__name__)
router = APIRouter(tags=["health"])


# -----------------------
# Internal helper methods
# -----------------------


async def _check_db() -> ReadinessCheck:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return ReadinessCheck(name="db", status="ok")
    except SQLAlchemyError as exc:  # pragma: no cover - defensive
        msg = f"DB connectivity failed: {exc.__class__.__name__}"
        return ReadinessCheck(name="db", status="error", message=msg)


async def _check_migrations() -> ReadinessCheck:
    """
    Validate that schema_migrations table exists and that all expected
    migration filenames under db/migrations/ have been applied.

    Rules:
    - If table missing: error.
    - If expected migration missing: error.
    - If extra applied: warn (non-fatal to overall readiness).
    """
    expected: List[str] = []
    root = Path(__file__).resolve().parents[2]
    migrations_dir = root / "db" / "migrations"
    if migrations_dir.is_dir():
        for path in sorted(migrations_dir.glob("*.sql")):
            expected.append(path.name)

    if not expected:
        # No local expectations; treat as warn so behavior is explicit.
        return ReadinessCheck(
            name="migrations",
            status="warn",
            message="No migration files found in db/migrations",
        )

    async with AsyncSessionLocal() as session:
        try:
            # Check existence of schema_migrations table by a lightweight query.
            result = await session.execute(
                text("SELECT filename FROM schema_migrations ORDER BY filename ASC")
            )
        except SQLAlchemyError as exc:
            msg = (
                "schema_migrations table missing or unreadable: "
                f"{exc.__class__.__name__}"
            )
            return ReadinessCheck(
                name="migrations",
                status="error",
                message=msg,
            )

        applied = [row[0] for row in result.fetchall()]
        expected_set = set(expected)
        applied_set = set(applied)

        missing = sorted(expected_set - applied_set)
        extra = sorted(applied_set - expected_set)

        if missing:
            return ReadinessCheck(
                name="migrations",
                status="error",
                message=f"Missing migrations: {', '.join(missing)}",
            )

        if extra:
            return ReadinessCheck(
                name="migrations",
                status="warn",
                message=f"Unexpected applied migrations: {', '.join(extra)}",
            )

        return ReadinessCheck(name="migrations", status="ok")


async def _check_metrics_registry() -> ReadinessCheck:
    try:
        load_registry()
        return ReadinessCheck(name="metrics_registry", status="ok")
    except RegistryUnavailableError as exc:
        return ReadinessCheck(
            name="metrics_registry",
            status="error",
            message=str(exc),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return ReadinessCheck(
            name="metrics_registry",
            status="error",
            message=f"Unexpected metrics registry error: {exc}",
        )


async def _check_etl_status() -> ReadinessCheck:
    """
    Non-critical ETL status check.

    Behavior:
    - If etl_runs table exists and last run success: ok.
    - If table missing: warn.
    - If last run failed or stale: warn.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text(
                    "SELECT etl_run_id, job_name, mode, status, "
                    "started_at, finished_at "
                    "FROM etl_runs "
                    "ORDER BY started_at DESC "
                    "LIMIT 1"
                )
            )
        except SQLAlchemyError:
            return ReadinessCheck(
                name="etl",
                status="warn",
                message="etl_runs table missing or unreadable",
            )

        row = result.first()
        if row is None:
            return ReadinessCheck(
                name="etl",
                status="warn",
                message="No ETL runs found",
            )

        # Row is positional: keep generic to avoid tight coupling.
        _, job_name, mode, run_status, started_at, finished_at = row

        # Consider success statuses as ok.
        success_statuses = {"success", "completed", "ok"}
        if str(run_status).lower() in success_statuses:
            # Optional: stale detection (e.g., older than 7 days) -> warn.
            try:
                if isinstance(finished_at, datetime):
                    now = datetime.now(tz=timezone.utc)
                    # Treat older than 7 days as stale.
                    if finished_at.tzinfo is None:
                        finished_at = finished_at.replace(tzinfo=timezone.utc)
                    if now - finished_at > timedelta(days=7):
                        return ReadinessCheck(
                            name="etl",
                            status="warn",
                            message=(
                                "Last ETL run successful but stale "
                                f"(job={job_name}, mode={mode})"
                            ),
                        )
            except Exception:  # pragma: no cover - defensive
                # If parsing fails, fall back to ok.
                pass

            return ReadinessCheck(name="etl", status="ok")

        return ReadinessCheck(
            name="etl",
            status="warn",
            message=(
                "Last ETL run not successful "
                f"(status={run_status}, job={job_name}, mode={mode})"
            ),
        )


def _aggregate_status(checks: List[ReadinessCheck]) -> str:
    """
    Aggregate overall readiness based on check statuses.

    Critical checks: db, migrations, metrics_registry.

    Rules:
    - If any critical check is error -> error.
    - Else if any non-critical is warn -> degraded.
    - Else -> ok.
    """
    by_name: Dict[str, ReadinessCheck] = {c.name: c for c in checks}

    critical_names = {"db", "migrations", "metrics_registry"}

    for name in critical_names:
        check = by_name.get(name)
        if check is not None and check.status == "error":
            return "error"

    # Non-critical (currently `etl`) may degrade but not error overall.
    for check in checks:
        if check.name not in critical_names and check.status == "warn":
            return "degraded"

    return "ok"


# --------------
# API endpoints
# --------------


@router.get(
    "/api/v1/health/live",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
)
async def health_live() -> HealthStatus:
    """
    Fast, dependency-free liveness check.

    Requirements:
    - No DB, filesystem, or external calls.
    - Always returns 200 with {"status": "ok"} if handler executes.
    """
    payload = HealthStatus(status="ok")
    log_api_event(logger, "health_live", status="ok")
    return payload


@router.get(
    "/api/v1/health/ready",
    response_model=ReadinessResponse,
)
async def health_ready() -> Any:
    """
    Readiness endpoint for routing real traffic.
    """
    checks: List[ReadinessCheck] = []

    db_check = await _check_db()
    checks.append(db_check)

    migrations_check = await _check_migrations()
    checks.append(migrations_check)

    metrics_check = await _check_metrics_registry()
    checks.append(metrics_check)

    etl_check = await _check_etl_status()
    checks.append(etl_check)

    overall_status = _aggregate_status(checks)
    http_status = (
        status.HTTP_503_SERVICE_UNAVAILABLE
        if overall_status == "error"
        else status.HTTP_200_OK
    )

    log_api_event(
        logger,
        "health_ready",
        status_code=http_status,
        overall_status=overall_status,
        checks=[c.dict() for c in checks],
    )

    body = ReadinessResponse(status=overall_status, checks=checks)
    if http_status != status.HTTP_200_OK:
        # FastAPI supports returning (content, status_code); keep it simple.
        return body.dict(), http_status

    return body


@router.get(
    "/api/v1/health/etl",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
)
async def health_etl() -> HealthStatus:
    """
    ETL introspection endpoint.

    - If etl_runs exists, returns summaries of recent runs.
    - If missing or on error, returns degraded with empty runs list.
    - Always HTTP 200.
    """
    details: Dict[str, Any] = {"runs": []}

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text(
                    "SELECT etl_run_id, job_name, mode, status, "
                    "started_at, finished_at "
                    "FROM etl_runs "
                    "ORDER BY started_at DESC "
                    "LIMIT 10"
                )
            )
            rows = result.fetchall()
        except SQLAlchemyError:
            msg = "etl_runs table missing or unreadable"
            details["message"] = msg
            payload = HealthStatus(status="degraded", details=details)
            log_api_event(
                logger,
                "health_etl",
                status_code=status.HTTP_200_OK,
                status=payload.status,
                message=msg,
            )
            return payload

    for (
        etl_run_id,
        job_name,
        mode,
        run_status,
        started_at,
        finished_at,
    ) in rows:
        details["runs"].append(
            {
                "etl_run_id": etl_run_id,
                "job_name": job_name,
                "mode": mode,
                "status": run_status,
                "started_at": started_at,
                "finished_at": finished_at,
            }
        )

    payload = HealthStatus(status="ok", details=details)
    log_api_event(
        logger,
        "health_etl",
        status_code=status.HTTP_200_OK,
        status=payload.status,
        runs_count=len(details["runs"]),
    )
    return payload

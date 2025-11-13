import logging
import os
from typing import Any, Dict

LOG_LEVEL = os.getenv("ETL_LOG_LEVEL", "INFO").upper()


def _configure_root_logger() -> None:
    if logging.getLogger().handlers:
        # Assume already configured by application.
        return

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s "
            "[%(filename)s:%(lineno)d]"
        )
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger with consistent formatting.
    """
    _configure_root_logger()
    return logging.getLogger(name)


def log_structured(
    logger: logging.Logger,
    level: int,
    message: str,
    **fields: Dict[str, Any],
) -> None:
    """
    Lightweight structured logging wrapper: appends key=value fields.
    """
    if not logger.isEnabledFor(level):
        return

    extra_parts = []
    for k, v in fields.items():
        extra_parts.append(f"{k}={v}")
    if extra_parts:
        message = f"{message} | " + " ".join(extra_parts)

    logger.log(level, message)


# ---------------------------
# ETL-specific logging helpers
# ---------------------------


def log_etl_event(logger: logging.Logger, event: str, **fields: Any) -> None:
    """
    Generic ETL event logger.
    """
    log_structured(logger, logger.level, event, **fields)


def log_etl_step_start(
    logger: logging.Logger,
    etl_run_id: int | None,
    step_name: str,
    **fields: Any,
) -> None:
    log_structured(
        logger,
        logger.level,
        "etl_step_start",
        etl_run_id=etl_run_id,
        step_name=step_name,
        **fields,
    )


def log_etl_step_end(
    logger: logging.Logger,
    etl_run_id: int | None,
    step_name: str,
    status: str,
    **fields: Any,
) -> None:
    log_structured(
        logger,
        logger.level,
        "etl_step_end",
        etl_run_id=etl_run_id,
        step_name=step_name,
        status=status,
        **fields,
    )


def log_schema_drift_issue(
    logger: logging.Logger,
    etl_run_id: int | None,
    source_type: str,
    source_id: str,
    issue_type: str,
    severity: str,
    details: Dict[str, Any],
) -> None:
    log_structured(
        logger,
        logger.level,
        "schema_drift_issue",
        etl_run_id=etl_run_id,
        source_type=source_type,
        source_id=source_id,
        issue_type=issue_type,
        severity=severity,
        **details,
    )


def log_validation_issue(
    logger: logging.Logger,
    etl_run_id: int | None,
    check_id: str,
    severity: str,
    status: str,
    details: Dict[str, Any],
) -> None:
    log_structured(
        logger,
        logger.level,
        "validation_issue",
        etl_run_id=etl_run_id,
        check_id=check_id,
        severity=severity,
        status=status,
        **details,
    )

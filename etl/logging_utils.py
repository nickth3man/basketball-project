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
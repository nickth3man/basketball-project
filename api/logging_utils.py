from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict


def _configure_root_logger() -> None:
    """
    Configure the root logger once for the API.

    - Reads API_LOG_LEVEL (default INFO).
    - Uses a single StreamHandler to stdout.
    - Formats messages as JSON with a stable schema so that callers
      can log structured events via `log_api_event`.
    """
    root = logging.getLogger()
    if root.handlers:
        # Assume already configured (e.g., by create_app()).
        return

    level_name = os.getenv("API_LOG_LEVEL", "INFO").upper()
    try:
        level = getattr(logging, level_name, logging.INFO)
    except Exception:  # noqa: BLE001
        level = logging.INFO

    handler = logging.StreamHandler()

    class JsonFormatter(logging.Formatter):
        def format(  # type: ignore[override]
            self,
            record: logging.LogRecord,
        ) -> str:
            payload: Dict[str, Any] = {
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }

            # Attach request/response level fields if present via `extra`.
            for key in (
                "event",
                "request_id",
                "method",
                "path",
                "client_ip",
                "user_agent",
                "status_code",
                "duration_ms",
            ):
                value = getattr(record, key, None)
                if value is not None:
                    payload[key] = value

            return json.dumps(
                payload,
                separators=(",", ":"),
                ensure_ascii=False,
            )

    handler.setFormatter(JsonFormatter())
    root.setLevel(level)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """
    Return a logger using the shared root configuration.

    Safe to call multiple times; configuration is idempotent.
    """
    _configure_root_logger()
    return logging.getLogger(name)


def log_api_event(
    logger: logging.Logger,
    event: str,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """
    Log a structured API event.

    Constraints:
    - Always includes `event`.
    - Never logs sensitive data (callers must not pass secrets).
    - Uses consistent JSON format via root handler.
    """
    if not logger.isEnabledFor(level):
        return

    # Defensive filter: drop obviously sensitive keys if passed accidentally.
    sensitive_keys = {
        "password",
        "passwd",
        "authorization",
        "auth_header",
        "token",
        "access_token",
        "id_token",
        "refresh_token",
        "secret",
    }
    safe_fields: Dict[str, Any] = {}
    for key, value in fields.items():
        if key.lower() in sensitive_keys:
            continue
        safe_fields[key] = value

    logger.log(
        level,
        event,
        extra={"event": event, **safe_fields},
    )

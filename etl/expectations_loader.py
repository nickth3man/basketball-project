from __future__ import annotations

"""
Helpers for loading ETL expectations from YAML.

Design goals:
- Centralized expectations for CSV sources and DB tables.
- Safe defaults: if file is missing or invalid, return empty expectations so
  existing ETL behavior is preserved.
- No hard dependency on any specific caller; pure functions with simple types.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import yaml

from .config import Config
from .logging_utils import get_logger, log_structured

logger = get_logger(__name__)


@dataclass(frozen=True)
class Expectations:
    raw: Dict[str, Any]
    csv_sources: Dict[str, Any]
    tables: Dict[str, Any]
    defaults: Dict[str, Any]
    version: Optional[str]


_EMPTY_EXPECTATIONS = Expectations(
    raw={},
    csv_sources={},
    tables={},
    defaults={
        "on_missing_column": "error",
        "on_extra_column": "warn",
        "on_type_mismatch": "warn",
        "on_primary_key_violation": "error",
        "on_null_in_required": "error",
        "on_row_count_zero": "warn",
        "hash_algorithm": "sha256",
    },
    version=None,
)


def _load_yaml(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        log_structured(
            logger,
            logging.WARNING,
            "Expectations file missing; running without expectations",
            path=path,
        )
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        log_structured(
            logger,
            logging.WARNING,
            "Failed to parse expectations YAML; running without expectations",
            path=path,
            error=str(exc),
        )
        return {}

    if not isinstance(data, dict):
        log_structured(
            logger,
            logging.WARNING,
            "Expectations YAML has unexpected top-level type; running without expectations",
            path=path,
            type=str(type(data)),
        )
        return {}

    return data


def load_expectations(config: Optional[Config] = None) -> Expectations:
    """
    Load expectations from the configured YAML path.

    Safe behavior:
    - On any problem (missing/invalid), returns _EMPTY_EXPECTATIONS.
    - Never raises for configuration problems to avoid breaking ETL.
    """
    # Late import to avoid circulars and keep this module light.
    from .config import get_config

    if config is None:
        config = get_config()

    # Default to etl/expectations.yaml when not overridden.
    expectations_path = os.getenv("ETL_EXPECTATIONS_PATH", "etl/expectations.yaml")
    if not os.path.isabs(expectations_path):
        # Interpret as relative to repo root / current working dir.
        expectations_path = os.path.join(os.getcwd(), expectations_path)

    raw = _load_yaml(expectations_path)
    if not raw:
        return _EMPTY_EXPECTATIONS

    defaults = dict(_EMPTY_EXPECTATIONS.defaults)
    defaults.update(raw.get("defaults", {}) or {})

    csv_sources = raw.get("csv_sources") or {}
    if not isinstance(csv_sources, dict):
        csv_sources = {}

    tables = raw.get("tables") or {}
    if not isinstance(tables, dict):
        tables = {}

    version = raw.get("version")
    if version is not None:
        version = str(version)

    loaded = Expectations(
        raw=raw,
        csv_sources=csv_sources,
        tables=tables,
        defaults=defaults,
        version=version,
    )

    log_structured(
        logger,
        logging.INFO,
        "Loaded ETL expectations",
        path=expectations_path,
        version=version,
        has_csv_sources=bool(csv_sources),
        has_tables=bool(tables),
    )

    return loaded


def get_csv_expectation(
    expectations: Expectations, source_id: str
) -> Optional[Dict[str, Any]]:
    """
    Return expectations for a CSV logical source id, or None.
    """
    return expectations.csv_sources.get(source_id)


def get_table_expectation(
    expectations: Expectations, table_name: str
) -> Optional[Dict[str, Any]]:
    """
    Return expectations for a DB table, or None.
    """
    return expectations.tables.get(table_name)


def resolve_policy(
    expectations: Expectations,
    policy_key: str,
    override: Optional[str] = None,
) -> str:
    """
    Resolve an issue policy severity.

    Order:
    - explicit override (if non-empty)
    - defaults[policy_key]
    - fallback to 'warn'
    """
    if override:
        return override

    val = expectations.defaults.get(policy_key)
    if isinstance(val, str) and val:
        return val

    return "warn"


def expectations_to_json_serializable(expectations: Expectations) -> Dict[str, Any]:
    """
    Helper to get a JSON-serializable view for metadata or reports.
    """
    return {
        "version": expectations.version,
        "defaults": expectations.defaults,
        "csv_sources_keys": sorted(expectations.csv_sources.keys()),
        "tables_keys": sorted(expectations.tables.keys()),
    }


def dump_expectations_snapshot(expectations: Expectations) -> str:
    """
    Helper for debugging / logging: compact JSON snapshot of loaded expectations.
    """
    try:
        return json.dumps(
            expectations_to_json_serializable(expectations), sort_keys=True
        )
    except Exception:  # noqa: BLE001
        return "{}"

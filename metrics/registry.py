from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Set

import yaml
from api.models_v2 import MetricAggregationFunctionV2, MetricRefV2

logger = logging.getLogger(__name__)

# Public types (lightweight; callers primarily work with plain dicts)
RegistryDict = Dict[str, Any]


class RegistryLoadError(RuntimeError):
    """Raised when the metrics registry cannot be loaded or validated."""


class RegistryUnavailableError(RuntimeError):
    """Raised when the registry is unavailable (e.g., failed to load)."""


class UnknownMetricError(ValueError):
    """Raised when a metric id/alias is not defined in the registry."""


class InvalidAggregationError(ValueError):
    """Raised when an aggregation is not allowed for a metric."""


# Internal module-level cache and guard.
_registry_cache: Optional[RegistryDict] = None
_registry_error: Optional[Exception] = None
_registry_lock = threading.Lock()


def _load_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise RegistryLoadError("metrics registry root must be a mapping")
    return data


def _validate_metric_id_consistency(metrics: Dict[str, Any]) -> None:
    for key, metric in metrics.items():
        if not isinstance(metric, dict):
            raise RegistryLoadError(f"Metric '{key}' must be a mapping")
        metric_id = metric.get("id")
        if metric_id != key:
            raise RegistryLoadError(
                f"Metric id mismatch for key '{key}': found id='{metric_id}'"
            )


def _validate_enums(metric_id: str, metric: Dict[str, Any]) -> None:
    entity_type = metric.get("entity_type")
    level = metric.get("level")
    source = metric.get("source")

    if entity_type not in {"player", "team", "lineup", "game"}:
        raise RegistryLoadError(
            f"Metric '{metric_id}': invalid entity_type '{entity_type}'"
        )

    if level not in {"game", "season", "career", "span", "streak"}:
        raise RegistryLoadError(
            f"Metric '{metric_id}': invalid level '{level}'",
        )

    if source not in {"column", "expression"}:
        raise RegistryLoadError(
            f"Metric '{metric_id}': invalid source '{source}'",
        )


def _validate_expression(metric_id: str, metric: Dict[str, Any]) -> None:
    source = metric.get("source")
    expression = metric.get("expression")

    if not isinstance(expression, str) or not expression.strip():
        raise RegistryLoadError(
            f"Metric '{metric_id}': expression must be non-empty",
        )

    if source == "column":
        # For column source, expression must be bare identifier.
        if any(ch.isspace() for ch in expression):
            raise RegistryLoadError(
                f"Metric '{metric_id}': column expression must be bare",
            )


def _validate_allowed_aggregations(
    metric_id: str,
    metric: Dict[str, Any],
) -> None:
    allowed = metric.get("allowed_aggregations")
    if not isinstance(allowed, list) or not allowed:
        raise RegistryLoadError(
            f"Metric '{metric_id}': allowed_aggregations invalid",
        )

    # Valid aggregation values from MetricAggregationFunctionV2 enum.
    valid_values: Set[str] = {e.value for e in MetricAggregationFunctionV2}
    invalid = [a for a in allowed if a not in valid_values]
    if invalid:
        raise RegistryLoadError(
            f"Metric '{metric_id}': invalid allowed_aggregations {invalid}"
        )


def _validate_base_table(metric_id: str, metric: Dict[str, Any]) -> None:
    base_table = metric.get("base_table")
    if not isinstance(base_table, str) or not base_table.strip():
        raise RegistryLoadError(
            f"Metric '{metric_id}': base_table must be a non-empty string"
        )


def _build_alias_index(metrics: Dict[str, Any]) -> Dict[str, str]:
    alias_index: Dict[str, str] = {}
    seen_aliases: Set[str] = set()

    for metric_id, metric in metrics.items():
        aliases = metric.get("aliases") or []
        if not isinstance(aliases, Iterable):
            raise RegistryLoadError(
                f"Metric '{metric_id}': aliases must be a list of strings if present",
            )
        for alias in aliases:
            if not isinstance(alias, str) or not alias:
                raise RegistryLoadError(
                    f"Metric '{metric_id}': alias entries must be non-empty",
                )
            lower_alias = alias.lower()
            if lower_alias in seen_aliases:
                raise RegistryLoadError(
                    f"Alias '{alias}' defined multiple times across metrics"
                )
            seen_aliases.add(lower_alias)
            alias_index[lower_alias] = metric_id

    return alias_index


def _validate_and_normalize(raw: Dict[str, Any]) -> RegistryDict:
    if "version" not in raw or not isinstance(raw["version"], int):
        raise RegistryLoadError(
            "Registry version must be present and an integer",
        )

    metrics = raw.get("metrics")
    if not isinstance(metrics, dict):
        raise RegistryLoadError("Registry 'metrics' must be a mapping")

    _validate_metric_id_consistency(metrics)

    for metric_id, metric in metrics.items():
        _validate_enums(metric_id, metric)
        _validate_expression(metric_id, metric)
        _validate_allowed_aggregations(metric_id, metric)
        _validate_base_table(metric_id, metric)

    alias_index = _build_alias_index(metrics)

    # Attach internal-only alias index under a reserved key.
    normalized: RegistryDict = dict(raw)
    normalized["_alias_index"] = alias_index
    return normalized


def load_registry() -> RegistryDict:
    """
    Load and validate the metrics registry from metrics/registry.yaml.

    Behavior:
    - On first call:
      - Reads and parses YAML.
      - Validates structure and metrics.
      - Builds an internal alias index.
      - Caches successful result.
    - On subsequent calls:
      - Returns cached registry.

    Error handling strategy (documented and consistent):
    - If loading or validation fails:
        - Logs structured error event="metrics_registry_load_failed".
        - Stores the underlying exception.
        - Raises RegistryUnavailableError on every call.
    """
    global _registry_cache, _registry_error

    if _registry_cache is not None:
        return _registry_cache

    if _registry_error is not None:
        # Registry previously failed to load; remain deterministic.
        raise RegistryUnavailableError(
            "Metrics registry unavailable"
        ) from _registry_error

    with _registry_lock:
        # Double-check under lock.
        if _registry_cache is not None:
            return _registry_cache
        if _registry_error is not None:
            raise RegistryUnavailableError(
                "Metrics registry unavailable"
            ) from _registry_error

        try:
            root_path = Path(__file__).resolve().parents[1]
            registry_path = root_path / "metrics" / "registry.yaml"
            data = _load_yaml(registry_path)
            registry = _validate_and_normalize(data)
            _registry_cache = registry
            logger.info(
                "Metrics registry loaded",
                extra={
                    "event": "metrics_registry_loaded",
                    "metrics_count": len(registry.get("metrics", {})),
                },
            )
            return registry
        except Exception as exc:  # noqa: BLE001
            _registry_error = exc
            logger.error(
                "Failed to load metrics registry",
                exc_info=True,
                extra={"event": "metrics_registry_load_failed"},
            )
            raise RegistryUnavailableError(
                "Metrics registry unavailable",
            ) from exc


def get_metric_def(metric_id: str) -> Optional[Dict[str, Any]]:
    """
    Resolve a metric definition by canonical id or alias.

    - Returns the metric definition dict if found.
    - Returns None if not found.
    - Raises RegistryUnavailableError if registry is not available.
    """
    if not metric_id:
        return None

    registry = load_registry()
    metrics: Dict[str, Any] = registry.get("metrics", {})
    alias_index: Dict[str, str] = registry.get("_alias_index", {})

    # Exact id match first.
    if metric_id in metrics:
        return metrics[metric_id]

    # Alias lookup (case-insensitive).
    alias_key = metric_id.lower()
    canonical = alias_index.get(alias_key)
    if canonical and canonical in metrics:
        return metrics[canonical]

    return None


def _normalize_aggregation(
    metric: Dict[str, Any],
    aggregation: Optional[MetricAggregationFunctionV2],
) -> Optional[str]:
    if aggregation is None:
        return None

    agg_value = aggregation.value
    allowed = metric.get("allowed_aggregations") or []
    if agg_value not in allowed:
        raise InvalidAggregationError(
            f"Aggregation '{agg_value}' is not allowed for metric '{metric.get('id')}'",
        )

    return agg_value


def resolve_metric_ref(metric_ref: MetricRefV2) -> Dict[str, Any]:
    """
    Resolve a MetricRefV2 into a normalized descriptor dict.

    Behavior:
    - Ensures registry is loaded (or raises RegistryUnavailableError).
    - Resolves metric_ref.id as canonical id or alias.
    - Validates requested aggregation against metric.allowed_aggregations.
    - Returns a dict including at least:
        - id, name, category, entity_type, level, source,
          expression, base_table, unit, precision,
          allowed_aggregations, aliases, display,
          constraints, filters_hint,
          chosen_aggregation (if provided and valid)
    - Raises:
        - UnknownMetricError if the metric id/alias cannot be resolved.
        - InvalidAggregationError for disallowed aggregations.
        - RegistryUnavailableError if registry cannot be loaded.
    """
    metric_def = get_metric_def(metric_ref.id)
    if metric_def is None:
        # Also try alias field if present on ref.
        if metric_ref.alias:
            metric_def = get_metric_def(metric_ref.alias)
    if metric_def is None:
        raise UnknownMetricError(
            f"Unknown metric id or alias: '{metric_ref.id}'",
        )

    chosen_agg = _normalize_aggregation(metric_def, metric_ref.aggregation)

    # Build a safe descriptor copy without internal keys.
    descriptor: Dict[str, Any] = {}
    for key in [
        "id",
        "name",
        "category",
        "entity_type",
        "level",
        "source",
        "expression",
        "base_table",
        "requires",
        "unit",
        "precision",
        "allowed_aggregations",
        "filters_hint",
        "aliases",
        "display",
        "constraints",
    ]:
        if key in metric_def:
            descriptor[key] = metric_def[key]

    descriptor["chosen_aggregation"] = chosen_agg

    return descriptor

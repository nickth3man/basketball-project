from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from metrics.registry import (
    RegistryUnavailableError,
    get_metric_def,
    load_registry,
)

from api.models_v2 import (
    EntityTypeV2,
    PaginatedResponseV2,
    PaginationMetaV2,
    QueryFiltersEchoV2,
)

router = APIRouter(tags=["metrics-v2"])


DEFAULT_PAGE: int = 1
DEFAULT_PAGE_SIZE: int = 100
MAX_PAGE_SIZE: int = 500


def _normalize_pagination(
    page: Optional[int],
    page_size: Optional[int],
    total: int,
) -> PaginationMetaV2:
    page = page or DEFAULT_PAGE
    page_size = page_size or DEFAULT_PAGE_SIZE
    if page < 1:
        page = DEFAULT_PAGE
    if page_size < 1:
        page_size = DEFAULT_PAGE_SIZE
    if page_size > MAX_PAGE_SIZE:
        page_size = MAX_PAGE_SIZE

    return PaginationMetaV2(
        page=page,
        page_size=page_size,
        total=total,
    )


def _metric_summary(metric: Dict[str, Any]) -> Dict[str, Any]:
    display = metric.get("display") or {}
    return {
        "id": metric.get("id"),
        "name": metric.get("name"),
        "entity_type": metric.get("entity_type"),
        "level": metric.get("level"),
        "category": metric.get("category"),
        "unit": metric.get("unit"),
        "display": {
            "short_label": display.get("short_label"),
            "long_label": display.get("long_label"),
            "format": display.get("format"),
        },
    }


@router.get(
    "/metrics",
    response_model=PaginatedResponseV2[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
)
async def list_metrics_v2(
    entity_type: Optional[EntityTypeV2] = Query(
        default=None,
        description="Filter by entity type",
    ),
    level: Optional[str] = Query(
        default=None,
        description="Filter by metric level",
    ),
    category: Optional[str] = Query(
        default=None,
        description="Filter by metric category",
    ),
    page: Optional[int] = Query(
        default=DEFAULT_PAGE,
        ge=1,
        description="Page number for pagination",
    ),
    page_size: Optional[int] = Query(
        default=DEFAULT_PAGE_SIZE,
        ge=1,
        le=MAX_PAGE_SIZE,
        description="Page size for pagination",
    ),
) -> PaginatedResponseV2[Dict[str, Any]]:
    """
    List metrics from the registry with optional filters.

    - Read-only.
    - Backed entirely by the local metrics registry.
    """
    try:
        registry = load_registry()
    except RegistryUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "metrics_registry_unavailable",
                "detail": "Metrics registry could not be loaded",
            },
        ) from exc

    metrics: Dict[str, Any] = registry.get("metrics", {})

    def matches_filters(m: Dict[str, Any]) -> bool:
        if entity_type and m.get("entity_type") != entity_type.value:
            return False
        if level and m.get("level") != level:
            return False
        if category and m.get("category") != category:
            return False
        return True

    filtered: List[Dict[str, Any]] = [
        _metric_summary(m) for m in metrics.values() if matches_filters(m)
    ]

    total = len(filtered)
    pagination = _normalize_pagination(page, page_size, total)

    start = (pagination.page - 1) * pagination.page_size
    end = start + pagination.page_size
    page_items = filtered[start:end]

    filters_echo = QueryFiltersEchoV2(
        normalized={
            "entity_type": entity_type.value if entity_type else None,
            "level": level,
            "category": category,
        },
    )

    return PaginatedResponseV2[Dict[str, Any]](
        data=page_items,
        pagination=pagination,
        filters=filters_echo,
    )


def _sanitize_metric_definition(metric: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy of metric definition excluding internal-only keys."""
    allowed_keys = {
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
    }
    return {k: v for (k, v) in metric.items() if k in allowed_keys}


@router.get(
    "/metrics/{metric_id}",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
)
async def get_metric_v2(metric_id: str) -> Dict[str, Any]:
    """
    Retrieve a single metric definition by id or alias.

    - Returns full, safe metric definition.
    - 404 if the metric is not found.
    - 503 if registry is unavailable.
    """
    try:
        metric = get_metric_def(metric_id)
    except RegistryUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "metrics_registry_unavailable",
                "detail": "Metrics registry could not be loaded",
            },
        ) from exc

    if metric is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "metric_not_found",
                "detail": f"Metric '{metric_id}' not found",
            },
        )

    return _sanitize_metric_definition(metric)

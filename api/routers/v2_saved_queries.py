from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError

from api.models_v2 import (
    PaginatedResponseV2,
    PaginationMetaV2,
    QueryFiltersEchoV2,
)

router = APIRouter(tags=["v2-saved-queries"])

# -------------------------
# Constants / configuration
# -------------------------

SAVED_QUERIES_DIR = Path("var") / "saved_queries"

VALID_TOOL_SLUGS = {
    "leaderboards_v2": "leaderboards_v2",
    "streaks_v2": "streaks_v2",
    "spans_v2": "spans_v2",
    "splits_v2": "splits_v2",
    "versus_v2": "versus_v2",
}

MAX_PAGE_SIZE = 500


# -------------------------
# Pydantic models
# -------------------------


class SavedQuerySummaryV2(BaseModel):
    id: str
    name: str
    tool: str
    description: Optional[str] = None
    created_at: str
    updated_at: str


class SavedQueryDetailV2(SavedQuerySummaryV2):
    payload: Dict[str, Any]


class SavedQueryCreateRequestV2(BaseModel):
    name: str = Field(..., min_length=1)
    tool: str
    description: Optional[str] = None
    payload: Dict[str, Any]


class SavedQueryUpdateRequestV2(BaseModel):
    name: Optional[str] = None
    description: Optional[Optional[str]] = None  # allow explicit null
    payload: Optional[Dict[str, Any]] = None


# -------------------------
# Internal helpers
# -------------------------


def _ensure_storage_dir() -> None:
    try:
        os.makedirs(SAVED_QUERIES_DIR, exist_ok=True)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize saved queries directory: {exc}",
        ) from exc


def _tool_slug_to_filename(tool_slug: str) -> Path:
    return SAVED_QUERIES_DIR / f"{tool_slug}.json"


def _load_tool_file(tool_slug: str) -> Dict[str, Any]:
    _ensure_storage_dir()
    path = _tool_slug_to_filename(tool_slug)
    if not path.exists():
        return {"version": 1, "queries": []}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        msg = f"Corrupted saved queries file for tool '{tool_slug}': {exc}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        ) from exc
    except OSError as exc:
        msg = f"Failed to read saved queries for tool '{tool_slug}': {exc}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        ) from exc

    if not isinstance(data, dict):
        return {"version": 1, "queries": []}
    if "version" not in data:
        data["version"] = 1
    if "queries" not in data or not isinstance(data["queries"], list):
        data["queries"] = []
    return data


def _save_tool_file(tool_slug: str, data: Dict[str, Any]) -> None:
    _ensure_storage_dir()
    path = _tool_slug_to_filename(tool_slug)
    tmp_path = path.with_suffix(".json.tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except OSError as exc:
        msg = f"Failed to persist saved queries for tool '{tool_slug}': {exc}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=msg,
        ) from exc


def _iter_all_tool_files() -> List[Tuple[str, Dict[str, Any]]]:
    """Load all known tool files. Missing files are treated as empty."""
    results: List[Tuple[str, Dict[str, Any]]] = []
    for slug in VALID_TOOL_SLUGS.values():
        data = _load_tool_file(slug)
        results.append((slug, data))
    return results


def _find_query_by_id(
    query_id: str,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Return (tool_slug, file_data, query_obj) or raise 404."""
    for tool_slug, data in _iter_all_tool_files():
        for q in data.get("queries", []):
            if q.get("id") == query_id:
                return tool_slug, data, q
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "saved_query_not_found",
            "detail": f"Saved query '{query_id}' not found",
        },
    )


def _validate_tool_slug(tool: str) -> str:
    if tool not in VALID_TOOL_SLUGS:
        allowed = ", ".join(sorted(VALID_TOOL_SLUGS.keys()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid tool '{tool}'. Allowed: {allowed}",
        )
    return tool


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _summary_from_obj(obj: Dict[str, Any]) -> SavedQuerySummaryV2:
    return SavedQuerySummaryV2(
        id=obj["id"],
        name=obj["name"],
        tool=obj["tool"],
        description=obj.get("description"),
        created_at=obj["created_at"],
        updated_at=obj["updated_at"],
    )


def _detail_from_obj(obj: Dict[str, Any]) -> SavedQueryDetailV2:
    return SavedQueryDetailV2(
        id=obj["id"],
        name=obj["name"],
        tool=obj["tool"],
        description=obj.get("description"),
        created_at=obj["created_at"],
        updated_at=obj["updated_at"],
        payload=obj.get("payload") or {},
    )


def _validate_payload_for_tool(tool: str, payload: Dict[str, Any]) -> None:
    """Structural validation via the corresponding v2 request model."""
    from api.models_v2 import (  # local import to avoid cycles
        LeaderboardsQueryV2,
        SpansQueryV2,
        SplitsQueryV2,
        StreaksQueryV2,
        VersusQueryV2,
    )

    model_map = {
        "leaderboards_v2": LeaderboardsQueryV2,
        "streaks_v2": StreaksQueryV2,
        "spans_v2": SpansQueryV2,
        "splits_v2": SplitsQueryV2,
        "versus_v2": VersusQueryV2,
    }

    model = model_map.get(tool)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported tool for saved query: {tool}",
        )

    try:
        model.parse_obj(payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid payload for tool '{tool}': {exc.errors()}",
        ) from exc


# -------------------------
# Routes
# -------------------------


@router.get(
    "/saved-queries",
    response_model=PaginatedResponseV2[SavedQuerySummaryV2],
    status_code=status.HTTP_200_OK,
)
async def list_saved_queries_v2(
    tool: Optional[str] = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
) -> PaginatedResponseV2[SavedQuerySummaryV2]:
    """
    List saved queries (optionally filtered by tool).
    """

    if tool is not None:
        _validate_tool_slug(tool)
        tool_slugs = [tool]
    else:
        tool_slugs = list(VALID_TOOL_SLUGS.values())

    all_summaries: List[SavedQuerySummaryV2] = []
    for slug in tool_slugs:
        data = _load_tool_file(slug)
        for obj in data.get("queries", []):
            try:
                all_summaries.append(_summary_from_obj(obj))
            except Exception:
                # Skip malformed entries instead of breaking the whole list.
                continue

    # Stable ordering: newest first by created_at then id
    all_summaries.sort(
        key=lambda q: (q.created_at, q.id),
        reverse=True,
    )

    start = (page - 1) * page_size
    end = start + page_size
    page_items = all_summaries[start:end]

    pagination = PaginationMetaV2(
        page=page,
        page_size=page_size,
        total=len(all_summaries),
    )
    filters = QueryFiltersEchoV2(
        normalized={"tool": tool if tool is not None else None},
    )
    return PaginatedResponseV2[SavedQuerySummaryV2](
        data=page_items,
        pagination=pagination,
        filters=filters,
    )


@router.get(
    "/saved-queries/{query_id}",
    response_model=SavedQueryDetailV2,
    status_code=status.HTTP_200_OK,
)
async def get_saved_query_v2(query_id: str) -> SavedQueryDetailV2:
    """
    Fetch a single saved query by id.
    """
    _, _, obj = _find_query_by_id(query_id)
    return _detail_from_obj(obj)


@router.post(
    "/saved-queries",
    response_model=SavedQueryDetailV2,
    status_code=status.HTTP_201_CREATED,
)
async def create_saved_query_v2(
    req: SavedQueryCreateRequestV2,
) -> SavedQueryDetailV2:
    """
    Create a new saved query.
    """
    from uuid import uuid4

    tool = _validate_tool_slug(req.tool)

    if not req.payload:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="payload is required",
        )

    _validate_payload_for_tool(tool, req.payload)

    now = _utc_now_iso()
    query_id = str(uuid4())

    file_data = _load_tool_file(tool)
    queries = file_data.get("queries", [])
    queries.append(
        {
            "id": query_id,
            "name": req.name,
            "tool": tool,
            "description": req.description,
            "created_at": now,
            "updated_at": now,
            "payload": req.payload,
        },
    )
    file_data["version"] = 1
    file_data["queries"] = queries
    _save_tool_file(tool, file_data)

    return SavedQueryDetailV2(
        id=query_id,
        name=req.name,
        tool=tool,
        description=req.description,
        created_at=now,
        updated_at=now,
        payload=req.payload,
    )


@router.put(
    "/saved-queries/{query_id}",
    response_model=SavedQueryDetailV2,
    status_code=status.HTTP_200_OK,
)
async def update_saved_query_v2(
    query_id: str,
    req: SavedQueryUpdateRequestV2,
) -> SavedQueryDetailV2:
    """
    Update an existing saved query.
    """
    tool_slug, file_data, obj = _find_query_by_id(query_id)
    updated = False

    if req.name is not None:
        if not req.name:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="name cannot be empty",
            )
        obj["name"] = req.name
        updated = True

    if req.description is not None:
        # supports explicit null to clear the description
        obj["description"] = req.description
        updated = True

    if req.payload is not None:
        if not req.payload:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="payload, if provided, cannot be empty",
            )
        _validate_payload_for_tool(obj["tool"], req.payload)
        obj["payload"] = req.payload
        updated = True

    if not updated:
        return _detail_from_obj(obj)

    obj["updated_at"] = _utc_now_iso()

    # Persist back to the same tool file
    queries = file_data.get("queries", [])
    for idx, existing in enumerate(queries):
        if existing.get("id") == query_id:
            queries[idx] = obj
            break
    file_data["version"] = 1
    file_data["queries"] = queries
    _save_tool_file(tool_slug, file_data)

    return _detail_from_obj(obj)


@router.delete(
    "/saved-queries/{query_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_saved_query_v2(query_id: str) -> None:
    """
    Delete a saved query.
    """
    tool_slug, file_data, obj = _find_query_by_id(query_id)
    original = file_data.get("queries", [])
    queries: List[Dict[str, Any]] = []
    for q in original:
        if q.get("id") != obj.get("id"):
            queries.append(q)
    if len(queries) == len(original):
        # Should not happen given _find_query_by_id, but guard anyway
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "saved_query_not_found",
                "detail": f"Saved query '{query_id}' not found",
            },
        )
    file_data["version"] = 1
    file_data["queries"] = queries
    _save_tool_file(tool_slug, file_data)

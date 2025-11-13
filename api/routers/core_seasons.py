from __future__ import annotations

from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import func, select, table, column
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db, get_pagination
from api.models import (
    ErrorResponse,
    FiltersEcho,
    PaginatedResponse,
    PaginationMeta,
    Season,
)

router = APIRouter(tags=["seasons"])


def _seasons_table():
    return table(
        "seasons",
        column("season_id"),
        column("season_end_year"),
        column("lg"),
        column("is_lockout"),
    )


@router.get("/seasons", response_model=PaginatedResponse)
async def list_seasons(
    db: AsyncSession = Depends(get_db),
    page_data: Tuple[int, int] = Depends(get_pagination),
    from_season: int | None = Query(
        None,
        description="Include seasons with season_end_year >= this value.",
    ),
    to_season: int | None = Query(
        None,
        description="Include seasons with season_end_year <= this value.",
    ),
    lg: str | None = Query(
        None,
        description="Filter by league code.",
    ),
) -> PaginatedResponse:
    page, page_size = page_data
    echo: Dict[str, Any] = {}
    seasons = _seasons_table()

    query = select(
        seasons.c.season_id,
        seasons.c.season_end_year,
        seasons.c.lg,
        seasons.c.is_lockout,
    )

    where_clauses: List[Any] = []

    if from_season is not None:
        echo["from_season"] = from_season
        where_clauses.append(seasons.c.season_end_year >= from_season)

    if to_season is not None:
        echo["to_season"] = to_season
        where_clauses.append(seasons.c.season_end_year <= to_season)

    if lg:
        echo["lg"] = lg
        where_clauses.append(seasons.c.lg == lg)

    if where_clauses:
        query = query.where(*where_clauses)

    query = query.order_by(seasons.c.season_end_year)

    count_stmt = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    offset = (page - 1) * page_size
    rows = (
        await db.execute(query.limit(page_size).offset(offset))
    ).mappings()

    data = [Season(**dict(r)) for r in rows]

    return PaginatedResponse(
        data=data,
        pagination=PaginationMeta(page=page, page_size=page_size, total=total),
        filters=FiltersEcho(raw=echo),
    )


@router.get(
    "/seasons/{season}",
    response_model=Season,
    responses={404: {"model": ErrorResponse}},
)
async def get_season(
    season: int = Path(..., description="Season end year."),
    db: AsyncSession = Depends(get_db),
) -> Season:
    seasons = _seasons_table()

    stmt = (
        select(
            seasons.c.season_id,
            seasons.c.season_end_year,
            seasons.c.lg,
            seasons.c.is_lockout,
        )
        .where(seasons.c.season_end_year == season)
        .limit(1)
    )

    row = (await db.execute(stmt)).mappings().first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Season not found",
        )

    return Season(**dict(row))
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union

from pydantic import BaseModel, Field, field_validator, model_validator

# Constants
MAX_PAGE_SIZE = 200
MAX_METRICS = 10
MAX_SPLIT_DIMENSIONS = 5
MAX_SUBJECT_IDS = 100


# -------------------------
# Enums
# -------------------------


class MetricAggregationFunctionV2(str, Enum):
    sum_ = "sum"
    avg = "avg"
    min = "min"
    max = "max"
    count_ = "count"
    count_distinct = "count_distinct"


class SortDirectionV2(str, Enum):
    asc = "asc"
    desc = "desc"


class GameScopeV2(str, Enum):
    all = "all"
    regular_season = "regular_season"
    playoffs = "playoffs"


class LocationCodeV2(str, Enum):
    all = "all"
    home = "home"
    away = "away"
    neutral = "neutral"


class EntityTypeV2(str, Enum):
    player = "player"
    team = "team"


class SpanModeV2(str, Enum):
    games = "games"
    dates = "dates"


class StreakDirectionV2(str, Enum):
    at_least = "at_least"
    at_most = "at_most"
    equal = "equal"


# -------------------------
# Filter models
# -------------------------


class SeasonFilterV2(BaseModel):
    season_start: Optional[int] = None
    season_end: Optional[int] = None
    seasons: Optional[List[int]] = None


class DateRangeFilterV2(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class GameTypeFilterV2(BaseModel):
    scope: GameScopeV2 = GameScopeV2.all


class TeamFilterV2(BaseModel):
    team_ids: Optional[List[int]] = None
    exclude_team_ids: Optional[List[int]] = None
    team_group_ids: Optional[List[str]] = None


class PlayerFilterV2(BaseModel):
    player_ids: Optional[List[int]] = None
    exclude_player_ids: Optional[List[int]] = None
    player_group_ids: Optional[List[str]] = None


class OpponentFilterV2(BaseModel):
    opponent_team_ids: Optional[List[int]] = None
    opponent_player_ids: Optional[List[int]] = None
    opponent_group_ids: Optional[List[str]] = None


class LocationFilterV2(BaseModel):
    location: LocationCodeV2 = LocationCodeV2.all


class ResultOutcomeV2(str, Enum):
    win = "win"
    loss = "loss"
    any = "any"


class ResultFilterV2(BaseModel):
    outcome: Optional[ResultOutcomeV2] = None
    min_margin: Optional[int] = None
    max_margin: Optional[int] = None


# -------------------------
# Advanced conditions
# -------------------------


class AdvancedConditionV2(BaseModel):
    field: str
    op: str  # Literal-style validation enforced below
    value: Any

    @field_validator("op")
    @classmethod
    def validate_op(cls, v: str) -> str:
        allowed = {
            "eq",
            "ne",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "not_in",
            "between",
        }
        if v not in allowed:
            raise ValueError(f"Unsupported op: {v}")
        return v


class ConditionGroupV2(BaseModel):
    all: Optional[List[Union["AdvancedConditionV2", "ConditionGroupV2"]]] = None
    any: Optional[List[Union["AdvancedConditionV2", "ConditionGroupV2"]]] = None

    @model_validator(mode="after")
    def validate_all_or_any(self) -> "ConditionGroupV2":
        if not self.all and not self.any:
            raise ValueError(
                "ConditionGroupV2 requires at least one of 'all' or 'any'",
            )
        return self


ConditionGroupV2.update_forward_refs()
AdvancedConditionV2.update_forward_refs()


# -------------------------
# Shared value objects
# -------------------------


class SplitDimensionV2(BaseModel):
    id: str
    description: Optional[str] = None


class MetricRefV2(BaseModel):
    id: str
    alias: Optional[str] = None
    aggregation: Optional[MetricAggregationFunctionV2] = None
    params: Optional[Dict[str, Any]] = None


class SortSpecV2(BaseModel):
    metric_id: Optional[str] = None
    field: Optional[str] = None
    direction: SortDirectionV2

    @model_validator(mode="after")
    def validate_target(self) -> "SortSpecV2":
        if not self.metric_id and not self.field:
            raise ValueError(
                "SortSpecV2 requires at least one of 'metric_id' or 'field'"
            )
        return self


class PageSpecV2(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1)


# -------------------------
# Base tool query and shared responses
# -------------------------


class ToolQueryV2(BaseModel):
    season_filter: Optional[SeasonFilterV2] = None
    date_range: Optional[DateRangeFilterV2] = None
    game_type: Optional[GameTypeFilterV2] = None
    team_filter: Optional[TeamFilterV2] = None
    player_filter: Optional[PlayerFilterV2] = None
    opponent_filter: Optional[OpponentFilterV2] = None
    location_filter: Optional[LocationFilterV2] = None
    result_filter: Optional[ResultFilterV2] = None
    conditions: Optional[ConditionGroupV2] = None
    metrics: Optional[List[MetricRefV2]] = None
    sort: Optional[SortSpecV2] = None
    page: Optional[PageSpecV2] = None


class QueryFiltersEchoV2(BaseModel):
    normalized: Dict[str, Any] = Field(default_factory=dict)


class PaginationMetaV2(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)


T = TypeVar("T")


class PaginatedResponseV2(BaseModel, Generic[T]):
    data: List[T]
    pagination: PaginationMetaV2
    filters: QueryFiltersEchoV2


# -------------------------
# Streaks
# -------------------------


class StreaksQueryV2(ToolQueryV2):
    subject_type: EntityTypeV2
    subject_ids: List[int]
    stat_metric: MetricRefV2
    threshold_value: Optional[float] = None
    threshold_direction: StreakDirectionV2 = StreakDirectionV2.at_least
    min_length: int = Field(2, ge=1)
    max_length: Optional[int] = None
    max_results: Optional[int] = None
    include_partial: bool = False


class StreaksResultRowV2(BaseModel):
    subject_type: EntityTypeV2
    subject_id: int
    streak_id: str
    start_game_id: str
    end_game_id: str
    start_date: date
    end_date: date
    length: int
    metric_id: str
    metric_value: float
    games_count: int
    is_active: bool
    extra_metrics: Optional[Dict[str, float]] = None


class StreaksQueryResponseV2(PaginatedResponseV2[StreaksResultRowV2]):
    pass


# -------------------------
# Spans
# -------------------------


class SpansQueryV2(ToolQueryV2):
    subject_type: EntityTypeV2
    subject_ids: List[int]
    span_mode: SpanModeV2
    min_span_length: int = Field(1, ge=1)
    max_span_length: Optional[int] = None
    metrics: List[MetricRefV2]
    sort: SortSpecV2
    max_results: Optional[int] = None


class SpansResultRowV2(BaseModel):
    subject_type: EntityTypeV2
    subject_id: int
    span_id: str
    start_game_id: str
    end_game_id: str
    start_date: date
    end_date: date
    span_length_games: int
    metrics: Dict[str, float]
    games_count: int


class SpansQueryResponseV2(PaginatedResponseV2[SpansResultRowV2]):
    pass


# -------------------------
# Leaderboards
# -------------------------


class LeaderboardsQueryV2(ToolQueryV2):
    entity_type: EntityTypeV2
    metrics: List[MetricRefV2]
    primary_metric_id: str
    season_filter: SeasonFilterV2
    min_games: Optional[int] = None
    min_minutes: Optional[int] = None
    min_attempts_by_metric: Optional[Dict[str, int]] = None
    page: PageSpecV2


class LeaderboardsResultRowV2(BaseModel):
    entity_type: EntityTypeV2
    entity_id: int
    label: str
    season_end_year: Optional[int] = None
    metrics: Dict[str, float]
    rank: int


class LeaderboardsQueryResponseV2(
    PaginatedResponseV2[LeaderboardsResultRowV2],
):
    pass


# -------------------------
# Splits
# -------------------------


class SplitsQueryV2(ToolQueryV2):
    subject_type: EntityTypeV2
    subject_id: int
    split_dimensions: List[SplitDimensionV2]
    metrics: List[MetricRefV2]
    include_totals: bool = True


class SplitsResultRowV2(BaseModel):
    subject_type: EntityTypeV2
    subject_id: int
    split_keys: Dict[str, str]
    metrics: Dict[str, float]
    games_count: int


class SplitsQueryResponseV2(PaginatedResponseV2[SplitsResultRowV2]):
    pass


# -------------------------
# Versus
# -------------------------


class VersusQueryV2(ToolQueryV2):
    subject_type: EntityTypeV2
    subject_ids: List[int]
    versus_team_ids: Optional[List[int]] = None
    versus_player_ids: Optional[List[int]] = None
    versus_group_ids: Optional[List[str]] = None
    split_by_opponent: bool = False
    metrics: List[MetricRefV2]


class VersusResultRowV2(BaseModel):
    subject_type: EntityTypeV2
    subject_id: int
    opponent_type: Optional[EntityTypeV2] = None
    opponent_id: Optional[int] = None
    opponent_group_id: Optional[str] = None
    metrics: Dict[str, float]
    games_count: int


class VersusQueryResponseV2(PaginatedResponseV2[VersusResultRowV2]):
    pass


__all__ = [
    "MetricAggregationFunctionV2",
    "SortDirectionV2",
    "GameScopeV2",
    "LocationCodeV2",
    "EntityTypeV2",
    "SpanModeV2",
    "StreakDirectionV2",
    "SeasonFilterV2",
    "DateRangeFilterV2",
    "GameTypeFilterV2",
    "TeamFilterV2",
    "PlayerFilterV2",
    "OpponentFilterV2",
    "LocationFilterV2",
    "ResultFilterV2",
    "AdvancedConditionV2",
    "ConditionGroupV2",
    "SplitDimensionV2",
    "MetricRefV2",
    "SortSpecV2",
    "PageSpecV2",
    "ToolQueryV2",
    "QueryFiltersEchoV2",
    "PaginationMetaV2",
    "PaginatedResponseV2",
    "StreaksQueryV2",
    "StreaksResultRowV2",
    "StreaksQueryResponseV2",
    "SpansQueryV2",
    "SpansResultRowV2",
    "SpansQueryResponseV2",
    "LeaderboardsQueryV2",
    "LeaderboardsResultRowV2",
    "LeaderboardsQueryResponseV2",
    "SplitsQueryV2",
    "SplitsResultRowV2",
    "SplitsQueryResponseV2",
    "VersusQueryV2",
    "VersusResultRowV2",
    "VersusQueryResponseV2",
]

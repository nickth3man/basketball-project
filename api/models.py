from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# -------------------------
# Generic response envelope
# -------------------------


class PaginationMeta(BaseModel):
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1)
    total: int = Field(..., ge=0)


class FiltersEcho(BaseModel):
    """Echo of parsed/normalized filters for transparency."""

    raw: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    detail: str


class PaginatedResponse(BaseModel):
    data: List[Any]
    pagination: PaginationMeta
    filters: FiltersEcho


# -------------------------
# Core entities (subset)
# -------------------------


class Player(BaseModel):
    player_id: int
    slug: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_active: Optional[bool] = None
    hof_inducted: Optional[bool] = None
    rookie_year: Optional[int] = None
    final_year: Optional[int] = None


class Team(BaseModel):
    team_id: int
    team_abbrev: Optional[str] = None
    team_name: Optional[str] = None
    team_city: Optional[str] = None
    is_active: Optional[bool] = None
    start_season: Optional[int] = None
    end_season: Optional[int] = None


class Season(BaseModel):
    season_id: int
    season_end_year: int
    lg: Optional[str] = None
    is_lockout: Optional[bool] = None


class Game(BaseModel):
    game_id: str
    season_end_year: Optional[int] = None
    game_date_est: str
    home_team_id: Optional[int] = None
    away_team_id: Optional[int] = None
    home_pts: Optional[int] = None
    away_pts: Optional[int] = None
    is_playoffs: Optional[bool] = None


# -------------------------
# Summary / hub projections
# -------------------------


class PlayerSeasonSummary(BaseModel):
    seas_id: int
    player_id: int
    season_end_year: int
    team_id: Optional[int] = None
    team_abbrev: Optional[str] = None
    is_total: Optional[bool] = None
    is_playoffs: Optional[bool] = None
    g: Optional[int] = None
    pts_per_g: Optional[float] = None
    trb_per_g: Optional[float] = None
    ast_per_g: Optional[float] = None


class TeamSeasonSummary(BaseModel):
    team_season_id: int
    team_id: int
    season_end_year: int
    is_playoffs: Optional[bool] = None
    g: Optional[int] = None
    pts: Optional[int] = None
    opp_pts: Optional[int] = None


class BoxscoreTeamRow(BaseModel):
    game_id: str
    team_id: int
    opponent_team_id: Optional[int] = None
    is_home: bool
    team_abbrev: Optional[str] = None
    pts: Optional[int] = None


class PbpEventRow(BaseModel):
    game_id: str
    eventnum: int
    period: Optional[int] = None
    clk: Optional[str] = None
    event_type: Optional[str] = None
    team_id: Optional[int] = None
    player1_id: Optional[int] = None
    description: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None


# -------------------------
# Tool request/response DTOs
# -------------------------


class PlayerSeasonFinderRequest(BaseModel):
    player_ids: Optional[List[int]] = None
    from_season: Optional[int] = None
    to_season: Optional[int] = None
    is_playoffs: Optional[bool] = None
    page: int = 1
    page_size: int = 50


class PlayerSeasonFinderResponseRow(BaseModel):
    seas_id: int
    player_id: int
    season_end_year: int
    team_id: Optional[int] = None
    g: Optional[int] = None
    pts_per_g: Optional[float] = None


class PlayerGameFinderRequest(BaseModel):
    player_ids: Optional[List[int]] = None
    from_season: Optional[int] = None
    to_season: Optional[int] = None
    is_playoffs: Optional[bool] = None
    page: int = 1
    page_size: int = 50


class PlayerGameFinderResponseRow(BaseModel):
    game_id: str
    player_id: int
    season_end_year: Optional[int] = None
    pts: Optional[int] = None
    trb: Optional[int] = None
    ast: Optional[int] = None


class TeamSeasonFinderRequest(BaseModel):
    team_ids: Optional[List[int]] = None
    from_season: Optional[int] = None
    to_season: Optional[int] = None
    is_playoffs: Optional[bool] = None
    page: int = 1
    page_size: int = 50


class TeamSeasonFinderResponseRow(BaseModel):
    team_season_id: int
    team_id: int
    season_end_year: int
    g: Optional[int] = None
    pts: Optional[int] = None


class TeamGameFinderRequest(BaseModel):
    team_ids: Optional[List[int]] = None
    from_season: Optional[int] = None
    to_season: Optional[int] = None
    is_playoffs: Optional[bool] = None
    page: int = 1
    page_size: int = 50


class TeamGameFinderResponseRow(BaseModel):
    game_id: str
    team_id: int
    is_home: Optional[bool] = None
    pts: Optional[int] = None
    opp_pts: Optional[int] = None


class StreakFinderRequest(BaseModel):
    player_id: Optional[int] = None
    team_id: Optional[int] = None
    min_length: int = 2
    page: int = 1
    page_size: int = 50


class StreakFinderResponseRow(BaseModel):
    subject_id: int
    start_game_id: str
    end_game_id: str
    length: int
    stat: str
    value: float


class SpanFinderRequest(BaseModel):
    player_id: Optional[int] = None
    team_id: Optional[int] = None
    span_length: int = 5
    page: int = 1
    page_size: int = 50


class SpanFinderResponseRow(BaseModel):
    subject_id: int
    start_game_id: str
    end_game_id: str
    span_length: int
    stat: str
    value: float


class VersusFinderRequest(BaseModel):
    player_id: Optional[int] = None
    team_id: Optional[int] = None
    opponent_ids: Optional[List[int]] = None
    page: int = 1
    page_size: int = 50


class VersusFinderResponseRow(BaseModel):
    subject_id: int
    opponent_id: int
    g: int
    pts_per_g: Optional[float] = None


class EventFinderRequest(BaseModel):
    game_ids: Optional[List[str]] = None
    event_types: Optional[List[str]] = None
    player_ids: Optional[List[int]] = None
    team_ids: Optional[List[int]] = None
    page: int = 1
    page_size: int = 50


class EventFinderResponseRow(BaseModel):
    game_id: str
    eventnum: int
    event_type: Optional[str] = None
    period: Optional[int] = None
    clk: Optional[str] = None
    team_id: Optional[int] = None
    player1_id: Optional[int] = None
    description: Optional[str] = None


class LeaderboardsRequest(BaseModel):
    scope: str = Field(
        ...,
        description=("One of: player_season, player_career, team_season, single_game"),
    )
    stat: str
    season_end_year: Optional[int] = None
    is_playoffs: Optional[bool] = None
    page: int = 1
    page_size: int = 50


class LeaderboardsResponseRow(BaseModel):
    subject_id: int
    label: str
    stat: float
    season_end_year: Optional[int] = None
    game_id: Optional[str] = None


class SplitsRequest(BaseModel):
    subject_type: str = Field(..., description="player or team")
    subject_id: int
    split_type: str = Field(
        ...,
        description="home_away or versus_opponent (minimal subset)",
    )
    page: int = 1
    page_size: int = 50


class SplitsResponseRow(BaseModel):
    subject_id: int
    split_key: str
    g: int
    pts_per_g: Optional[float] = None


# -------------------------
# Health / readiness models
# -------------------------


class HealthStatus(BaseModel):
    status: str
    details: Optional[Dict[str, Any]] = None


class ReadinessCheck(BaseModel):
    name: str
    status: str
    message: Optional[str] = None


class ReadinessResponse(BaseModel):
    status: str
    checks: List[ReadinessCheck]


__all__ = [
    "PaginationMeta",
    "FiltersEcho",
    "ErrorResponse",
    "PaginatedResponse",
    "Player",
    "Team",
    "Season",
    "Game",
    "PlayerSeasonSummary",
    "TeamSeasonSummary",
    "BoxscoreTeamRow",
    "PbpEventRow",
    "PlayerSeasonFinderRequest",
    "PlayerSeasonFinderResponseRow",
    "PlayerGameFinderRequest",
    "PlayerGameFinderResponseRow",
    "TeamSeasonFinderRequest",
    "TeamSeasonFinderResponseRow",
    "TeamGameFinderRequest",
    "TeamGameFinderResponseRow",
    "StreakFinderRequest",
    "StreakFinderResponseRow",
    "SpanFinderRequest",
    "SpanFinderResponseRow",
    "VersusFinderRequest",
    "VersusFinderResponseRow",
    "EventFinderRequest",
    "EventFinderResponseRow",
    "LeaderboardsRequest",
    "LeaderboardsResponseRow",
    "SplitsRequest",
    "SplitsResponseRow",
    "HealthStatus",
    "ReadinessCheck",
    "ReadinessResponse",
]

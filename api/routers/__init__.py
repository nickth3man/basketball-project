"""
Router package.

Routers are mounted in [`api.main.create_app()`](api/main.py:1)
under versioned prefixes:

- `/api/v1` for existing stable endpoints.
- `/api/v2` for new generalized tool contracts.

This module exposes routers so `api.main` can import them via
`from .routers import ...`.
"""

# v1 / legacy routers ---------------------------------------------------------

from . import (
    core_games,
    core_pbp,
    core_players,
    core_seasons,
    core_teams,
    health,
    tools_event_finder,
    tools_leaderboards,
    tools_player_finder,
    tools_span,
    tools_splits,
    tools_streaks,
    tools_team_finder,
    tools_versus,
    v2_metrics,
    v2_saved_queries,
    v2_tools_leaderboards,
    v2_tools_spans,
    v2_tools_splits,
    v2_tools_streaks,
    v2_tools_versus,
)

__all__ = [
    # v1 / legacy routers
    "core_games",
    "core_pbp",
    "core_players",
    "core_seasons",
    "core_teams",
    "tools_event_finder",
    "tools_leaderboards",
    "tools_player_finder",
    "tools_span",
    "tools_splits",
    "tools_streaks",
    "tools_team_finder",
    "tools_versus",
    # v2 routers
    "v2_metrics",
    "v2_saved_queries",
    "v2_tools_leaderboards",
    "v2_tools_spans",
    "v2_tools_splits",
    "v2_tools_streaks",
    "v2_tools_versus",
    # health
    "health",
]

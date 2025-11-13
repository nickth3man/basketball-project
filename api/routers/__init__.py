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

from . import core_games
from . import core_pbp
from . import core_players
from . import core_seasons
from . import core_teams
from . import tools_player_finder
from . import tools_team_finder
from . import tools_streaks
from . import tools_span
from . import tools_versus
from . import tools_event_finder as tools_pbp_search
from . import tools_leaderboards
from . import tools_splits

# v2 tool routers (additive; do not modify v1 behavior) ----------------------

from . import v2_tools_streaks
from . import v2_tools_spans
from . import v2_tools_leaderboards
from . import v2_tools_splits
from . import v2_tools_versus
from . import v2_metrics
from . import v2_saved_queries

# health / readiness routers -------------------------------------------------

from . import health

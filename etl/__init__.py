"""
ETL package for the Local Basketball-Reference + Stathead-style Clone.

Modules:
- config: configuration handling
- paths: central CSV path definitions
- db: database connection and bulk load helpers
- logging_utils: structured logging helpers
- id_resolution: pure functions for resolving ids from in-memory data
- load_metadata: ETL run and data version metadata
- load_dimensions: dimension table loaders (players, teams, seasons, mappings)
- load_player_seasons: player_season hub and satellites
- load_team_seasons: team_season hub and satellites
- load_games_and_boxscores: games and team boxscores
- load_pbp: play-by-play events
- load_awards_and_draft: awards and draft picks
- load_inactive: inactive_players
- validate: validation routines
"""

from .config import Config, get_config  # noqa: F401
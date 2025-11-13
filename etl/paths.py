"""
Centralized CSV paths used by the ETL, based on docs/phase_0_csv_inventory.json.

All paths here are relative to the configured CSV root. Call `resolve_csv_path`
to join with the actual root directory (see etl.config.Config).
"""

import os
from typing import Dict

from .config import Config

# Core dimension files
PLAYER_CSV = "player.csv"
PLAYER_DIRECTORY_CSV = "playerdirectory.csv"
COMMON_PLAYER_INFO_CSV = "common_player_info.csv"
PLAYER_SEASON_INFO_CSV = "playerseasoninfo.csv"
PLAYER_CAREER_INFO_CSV = "playercareerinfo.csv"

TEAM_CSV = "team.csv"
TEAM_HISTORY_CSV = "team_history.csv"
TEAM_DETAILS_CSV = "team_details.csv"

# Player season stat satellites (per-game, totals, per36, per100, advanced)
PLAYER_PER_GAME_CSV = "playerstatspergame.csv"
PLAYER_TOTALS_CSV = "playerstatstotals.csv"
PLAYER_PER36_CSV = "playerstatsper36.csv"
PLAYER_PER100_CSV = "playerstatsper100poss.csv"
PLAYER_ADVANCED_CSV = "playerstatsadvanced.csv"

# Team season stats
TEAM_TOTALS_CSV = "teamstats.csv"
TEAM_PER_GAME_CSV = "teamstatspergame.csv"
TEAM_PER100_CSV = "teamstatsper100poss.csv"
TEAM_OPP_TOTALS_CSV = "oppteamstats.csv"
TEAM_OPP_PER_GAME_CSV = "oppteamstatspergame.csv"
TEAM_OPP_PER100_CSV = "oppteamstatsper100poss.csv"

# Games and box scores
GAMES_CSV = "games.csv"
GAME_SUMMARY_CSV = "gamesummary.csv"
LINE_SCORE_CSV = "linescore.csv"
OTHER_STATS_CSV = "other_stats.csv"
BOX_SCORE_PLAYER_CSV = "boxscore_player.csv"  # if provided

# Play-by-play
PBP_CSV = "play_by_play.csv"

# Awards and draft
AWARDS_ALL_STAR_CSV = "all_starselections.csv"
AWARDS_PLAYER_SHARES_CSV = "playerawardshares.csv"
AWARDS_END_OF_SEASON_TEAMS_CSV = "endofseasonteams.csv"
AWARDS_END_OF_SEASON_VOTING_CSV = "endofseasonteams_voting.csv"
DRAFT_PICKS_CSV = "draft_history.csv"

# Inactive
INACTIVE_PLAYERS_CSV = "inactive_players.csv"


def resolve_csv_path(config: Config, relative_name: str) -> str:
    """
    Join the configured CSV root with a relative CSV filename.
    """
    return os.path.join(config.effective_csv_root, relative_name)


def all_known_csvs() -> Dict[str, str]:
    """
    Return a mapping of logical labels to relative CSV filenames.
    Useful for metadata/version tracking.
    """
    return {
        "player": PLAYER_CSV,
        "playerdirectory": PLAYER_DIRECTORY_CSV,
        "common_player_info": COMMON_PLAYER_INFO_CSV,
        "playerseasoninfo": PLAYER_SEASON_INFO_CSV,
        "playercareerinfo": PLAYER_CAREER_INFO_CSV,
        "team": TEAM_CSV,
        "team_history": TEAM_HISTORY_CSV,
        "team_details": TEAM_DETAILS_CSV,
        "player_per_game": PLAYER_PER_GAME_CSV,
        "player_totals": PLAYER_TOTALS_CSV,
        "player_per36": PLAYER_PER36_CSV,
        "player_per100": PLAYER_PER100_CSV,
        "player_advanced": PLAYER_ADVANCED_CSV,
        "team_totals": TEAM_TOTALS_CSV,
        "team_per_game": TEAM_PER_GAME_CSV,
        "team_per100": TEAM_PER100_CSV,
        "team_opp_totals": TEAM_OPP_TOTALS_CSV,
        "team_opp_per_game": TEAM_OPP_PER_GAME_CSV,
        "team_opp_per100": TEAM_OPP_PER100_CSV,
        "games": GAMES_CSV,
        "game_summary": GAME_SUMMARY_CSV,
        "line_score": LINE_SCORE_CSV,
        "other_stats": OTHER_STATS_CSV,
        "boxscore_player": BOX_SCORE_PLAYER_CSV,
        "pbp": PBP_CSV,
        "awards_all_star": AWARDS_ALL_STAR_CSV,
        "awards_player_shares": AWARDS_PLAYER_SHARES_CSV,
        "awards_end_of_season_teams": AWARDS_END_OF_SEASON_TEAMS_CSV,
        "awards_end_of_season_voting": AWARDS_END_OF_SEASON_VOTING_CSV,
        "draft_picks": DRAFT_PICKS_CSV,
        "inactive_players": INACTIVE_PLAYERS_CSV,
    }

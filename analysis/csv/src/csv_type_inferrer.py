"""CSV Type Inference for NBA Data Files."""

import logging
from typing import Set

# Get logger from main module for consistent logging
logger = logging.getLogger('csv_analysis')


class CSVTypeInferrer:
    """Infers the type of NBA CSV based on filename and column patterns."""

    # CSV type mapping configuration
    CSV_TYPE_MAPPING = {
        "game": "game_info",
        "game_info": "game_info",
        "game_summary": "game_summary",
        "game.csv": "game_info",
        "game_info.csv": "game_info",
        "game_summary.csv": "game_summary",
        "player": "player_stats",
        "playertotals": "player_totals",
        "playerpergame": "player_per_game",
        "playerseasoninfo": "player_season_info",
        "playercareerinfo": "player_career_info",
        "player.csv": "player_stats",
        "playertotals.csv": "player_totals",
        "playerpergame.csv": "player_per_game",
        "playerseasoninfo.csv": "player_season_info",
        "playercareerinfo.csv": "player_career_info",
        "team": "team_stats",
        "teamtotals": "team_totals",
        "teamstatspergame": "team_per_game",
        "team.csv": "team_stats",
        "teamtotals.csv": "team_totals",
        "teamstatspergame.csv": "team_per_game",
        "play_by_play": "play_by_play",
        "play_by_play.csv": "play_by_play",
        "pbp": "play_by_play",
        "inactive_players": "inactive_players",
        "inactive_players.csv": "inactive_players",
        "officials": "officials",
        "officials.csv": "officials",
        "draft": "draft",
        "draft_history": "draft_history",
        "draft_combine_stats": "draft_combine",
        "draft_history.csv": "draft_history",
        "draft_combine_stats.csv": "draft_combine",
        "award": "awards",
        "playerawardshares": "player_awards",
        "endofseasonteams": "all_star_voting",
        "playerawardshares.csv": "player_awards",
        "endofseasonteams.csv": "all_star_voting",
        "all_starselections": "all_star_selections",
        "all_starselections.csv": "all_star_selections",
        "line_score": "line_score",
        "line_score.csv": "line_score",
        "opponentstatsper100poss": "opponent_stats_per100",
        "opponentstatspergame": "opponent_stats_pergame",
        "opponenttotals": "opponent_totals",
        "opponentstatsper100poss.csv": "opponent_stats_per100",
        "opponentstatspergame.csv": "opponent_stats_pergame",
        "opponenttotals.csv": "opponent_totals",
        "per100poss": "per100_possessions",
        "per36minutes": "per36_minutes",
        "per100poss.csv": "per100_possessions",
        "per36minutes.csv": "per36_minutes",
        "other_stats": "other_stats",
        "other_stats.csv": "other_stats",
        "playerdirectory": "player_directory",
        "playershooting": "player_shooting",
        "playerplaybyplay": "player_playbyplay",
        "playercareerinfo3.csv": "player_career_info",
        "playerdirectory.csv": "player_directory",
        "playershooting.csv": "player_shooting",
        "playerplaybyplay.csv": "player_playbyplay",
        "team_details": "team_details",
        "team_history": "team_history",
        "team_info_common": "team_info_common",
        "teamabbrev": "team_abbreviations",
        "teamsummaries": "team_summaries",
        "team_details.csv": "team_details",
        "team_history.csv": "team_history",
        "team_info_common.csv": "team_info_common",
        "teamabbrev.csv": "team_abbreviations",
        "teamsummaries.csv": "team_summaries",
        "advanced": "advanced_stats",
        "advanced.csv": "advanced_stats",
        "common_player_info": "common_player_info",
        "common_player_info.csv": "common_player_info",
    }

    @classmethod
    def infer_type(cls, csv_name: str, columns: Set[str]) -> str:
        """
        Infer the type of NBA CSV based on filename and columns.

        Args:
            csv_name: Name of the CSV file (without path)
            columns: Set of column names in the CSV

        Returns:
            Inferred CSV type string
        """
        csv_name_lower = csv_name.lower()

        # Try exact match first
        if csv_name_lower in cls.CSV_TYPE_MAPPING:
            return cls.CSV_TYPE_MAPPING[csv_name_lower]

        # Try partial match
        for key, value in cls.CSV_TYPE_MAPPING.items():
            if key in csv_name_lower:
                return value

        return "unknown"

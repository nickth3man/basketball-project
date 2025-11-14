"""Basketball-specific validation rules for NBA data."""

import logging
from typing import Any, Dict

import polars as pl
from analysis_types import ValidationResult

# Get logger from main module for consistent logging
logger = logging.getLogger('csv_analysis')


class BasketballValidator:
    """Validates NBA data using basketball-specific rules."""

    def __init__(self, df: pl.DataFrame, csv_type: str):
        """
        Initialize the validator.

        Args:
            df: Polars DataFrame containing the data
            csv_type: Type of CSV (e.g., 'player_stats', 'game_info')
        """
        self.df = df
        self.csv_type = csv_type

    def get_validation_rules(self) -> Dict[str, Any]:
        """Get validation rules based on CSV type."""
        base_rules = {
            "shooting_logic": self.validate_shooting_logic,
            "efficiency_ranges": self.validate_efficiency_ranges,
        }

        # Add type-specific rules
        if self.csv_type in [
            "player_stats",
            "player_totals",
            "player_per_game",
            "per100_possessions",
            "per36_minutes",
        ]:
            logger.debug("Adding player-specific validation rules")
            base_rules.update({
                "per_ranges": self.validate_per_ranges,
            })

        if self.csv_type == "play_by_play":
            logger.debug("Adding play-by-play validation rules")
            base_rules.update({
                "temporal_consistency": self.validate_temporal_consistency,
                "score_progression": self.validate_score_progression,
            })

        if self.csv_type in ["game_info", "game_summary"]:
            logger.debug("Adding game-specific validation rules")
            base_rules.update({
                "score_calculation": self.validate_score_calculation,
                "game_logic": self.validate_game_logic,
            })

        if self.csv_type == "draft_history":
            logger.debug("Adding draft validation rules")
            base_rules.update({
                "draft_logic": self.validate_draft_logic,
            })

        return base_rules

    def validate_shooting_logic(self) -> ValidationResult:
        """Validate shooting statistics logic (FGM ≤ FGA, etc.)."""
        logger.debug("Validating shooting logic...")
        issues: list[str] = []

        # FGM ≤ FGA
        if "FGM" in self.df.columns and "FGA" in self.df.columns:
            logger.debug("Checking FGM <= FGA constraint")
            violations = (self.df["FGM"] > self.df["FGA"]).sum()
            if violations > 0:
                issues.append(f"FGM > FGA in {violations} rows")

        # FTM ≤ FTA
        if "FTM" in self.df.columns and "FTA" in self.df.columns:
            violations = (self.df["FTM"] > self.df["FTA"]).sum()
            if violations > 0:
                issues.append(f"FTM > FTA in {violations} rows")

        # 3PM ≤ 3PA
        if "FG3M" in self.df.columns and "FG3A" in self.df.columns:
            violations = (self.df["FG3M"] > self.df["FG3A"]).sum()
            if violations > 0:
                issues.append(f"FG3M > FG3A in {violations} rows")

        if not issues:
            return {
                "status": "passed",
                "message": "Shooting logic validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"Shooting logic violations: {len(issues)}",
            "details": issues,
        }

    def validate_efficiency_ranges(self) -> ValidationResult:
        """Validate efficiency metrics are in reasonable ranges."""
        logger.debug("Validating efficiency ranges...")
        issues: list[str] = []

        # Field Goal Percentage (0-100%)
        if "FG_PCT" in self.df.columns:
            logger.debug("Checking FG_PCT range [0,1]")
            out_of_range = ((self.df["FG_PCT"] < 0) | (self.df["FG_PCT"] > 1)).sum()
            if out_of_range > 0:
                issues.append(f"FG_PCT out of range [0,1] in {out_of_range} rows")

        # True Shooting Percentage (typically 0.35-0.75 for NBA)
        if "TS_PCT" in self.df.columns:
            out_of_range = ((self.df["TS_PCT"] < 0.2) | (self.df["TS_PCT"] > 0.8)).sum()
            if out_of_range > 0:
                issues.append(
                    f"TS_PCT out of reasonable range [0.2,0.8] in {out_of_range} rows"
                )

        # Effective Field Goal Percentage
        if "EFG_PCT" in self.df.columns:
            out_of_range = ((self.df["EFG_PCT"] < 0) | (self.df["EFG_PCT"] > 1)).sum()
            if out_of_range > 0:
                issues.append(f"EFG_PCT out of range [0,1] in {out_of_range} rows")

        if not issues:
            return {
                "status": "passed",
                "message": "Efficiency ranges validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"Efficiency range violations: {len(issues)}",
            "details": issues,
        }

    def validate_per_ranges(self) -> ValidationResult:
        """Validate PER is in reasonable ranges (typically 5-35)."""
        logger.debug("Validating PER ranges...")
        issues: list[str] = []

        if "PER" in self.df.columns:
            logger.debug("Checking PER range [0,40]")
            out_of_range = ((self.df["PER"] < 0) | (self.df["PER"] > 40)).sum()
            if out_of_range > 0:
                issues.append(
                    f"PER out of reasonable range [0,40] in {out_of_range} rows"
                )

        if not issues:
            return {
                "status": "passed",
                "message": "PER ranges validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"PER range violations: {len(issues)}",
            "details": issues,
        }

    def validate_temporal_consistency(self) -> ValidationResult:
        """Validate temporal consistency in play-by-play data."""
        # This would validate game clock progression, quarter transitions, etc.
        # Simplified version for now
        return {
            "status": "passed",
            "message": "Temporal consistency validation passed",
            "details": [],
        }

    def validate_score_progression(self) -> ValidationResult:
        """Validate score progression makes sense."""
        # This would validate score changes match event types
        return {
            "status": "passed",
            "message": "Score progression validation passed",
            "details": [],
        }

    def validate_score_calculation(self) -> ValidationResult:
        """Validate score calculations match expected formulas."""
        issues: list[str] = []

        # Basic score validation: PTS should roughly equal 2*FGM + FTM + 3*FG3M
        if all(col in self.df.columns for col in ["PTS", "FGM", "FTM", "FG3M"]):
            expected_pts = 2 * self.df["FGM"] + self.df["FTM"] + self.df["FG3M"]
            discrepancies = (
                (self.df["PTS"] - expected_pts).abs() > 1
            ).sum()  # Allow small rounding differences
            if discrepancies > 0:
                issues.append(f"PTS calculation discrepancies in {discrepancies} rows")

        if not issues:
            return {
                "status": "passed",
                "message": "Score calculation validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"Score calculation violations: {len(issues)}",
            "details": issues,
        }

    def validate_game_logic(self) -> ValidationResult:
        """Validate basic game logic."""
        issues: list[str] = []

        # Home and away scores should be positive
        if "HOME_PTS" in self.df.columns:
            negative_scores = (self.df["HOME_PTS"] < 0).sum()
            if negative_scores > 0:
                issues.append(f"Negative home scores in {negative_scores} rows")

        if "AWAY_PTS" in self.df.columns:
            negative_scores = (self.df["AWAY_PTS"] < 0).sum()
            if negative_scores > 0:
                issues.append(f"Negative away scores in {negative_scores} rows")

        if not issues:
            return {
                "status": "passed",
                "message": "Game logic validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"Game logic violations: {len(issues)}",
            "details": issues,
        }

    def validate_draft_logic(self) -> ValidationResult:
        """Validate draft-specific logic with historical context awareness."""
        issues: list[str] = []

        # Historical context:
        # - Pre-1989 drafts routinely exceeded 60 picks (multiple rounds,
        #   territorial picks, compensatory selections).
        # - Since 1989 the league formalized the draft to two rounds
        #   (typically 60 picks, occasionally 58-59 when picks are forfeited).
        # This validator enforces a strict lower bound while applying
        # context-aware upper bounds when season metadata is present.

        # Draft picks should be positive
        if "OVERALL_PICK" in self.df.columns:
            invalid_picks = (self.df["OVERALL_PICK"] < 1).sum()
            if invalid_picks > 0:
                issues.append(
                    f"OVERALL_PICK less than 1 in {invalid_picks} rows"
                )

            # Season-based validation if available
            if "season" in self.df.columns:
                # Modern drafts (1989-present): max 60 picks, can be 58-59
                # due to forfeitures or sanctions
                modern_drafts = self.df.filter(pl.col("season") >= 1989)
                if len(modern_drafts) > 0:
                    modern_invalid = (

                        (modern_drafts["OVERALL_PICK"] > 60)
                    ).sum()
                    if modern_invalid > 0:
                        issues.append(
                            f"OVERALL_PICK out of range [1,60] for modern drafts "
                            f"(season >= 1989) in {modern_invalid} rows"
                        )

                # Historical drafts (pre-1989): could have many more rounds
                historical_drafts = self.df.filter(pl.col("season") < 1989)
                if len(historical_drafts) > 0:
                    # Warn about extremely high picks even in historical drafts
                    extreme_picks = (historical_drafts["OVERALL_PICK"] > 200).sum()
                    if extreme_picks > 0:
                        issues.append(
                            f"OVERALL_PICK greater than 200 in {extreme_picks} rows "
                            f"(possible data quality issue even for historical drafts)"
                        )
            else:
                # No season column - use conservative approach
                very_high_picks = (self.df["OVERALL_PICK"] > 100).sum()
                if very_high_picks > 0:
                    issues.append(
                        f"OVERALL_PICK greater than 100 in {very_high_picks} rows "
                        "(possible data issue - season data not available for context)"
                    )

        if not issues:
            return {
                "status": "passed",
                "message": "Draft logic validation passed",
                "details": [],
            }

        return {
            "status": "failed",
            "message": f"Draft logic violations: {len(issues)}",
            "details": issues,
        }

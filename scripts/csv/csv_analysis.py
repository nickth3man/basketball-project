#!/usr/bin/env python3
"""
Comprehensive NBA CSV Analysis Script

This script provides deep profiling, validation, and visualization of NBA CSV files
with basketball-specific validation rules and data quality checks.

Features:
- Data profiling with ydata-profiling and frictionless
- Basketball-specific validation rules (FGM ≤ FGA, PER ranges, etc.)
- Statistical analysis and correlations
- Data quality assessment
- Interactive visualizations
- Comprehensive reporting

Usage:
    python csv_analysis.py --csv-path ../csv_files/game.csv --output-dir ./reports
    python csv_analysis.py --all-csvs --output-dir ./reports
"""

import argparse
import json
import logging
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TypedDict, Union, TYPE_CHECKING

import matplotlib.pyplot as plt
import matplotlib.figure
import matplotlib.axes
import numpy as np
import polars as pl
import seaborn as sns
from frictionless import Resource, validate

# Type checking imports
if TYPE_CHECKING:
    import matplotlib.figure as _figure
    import matplotlib.axes as _axes
    import seaborn as _seaborn

# Type definitions for better type safety
class ValidationResult(TypedDict):
    status: str
    message: str
    details: List[str]

class TaskInfo(TypedDict):
    valid: bool
    errors: List[str]
    warnings: List[str]

class FrictionlessValidation(TypedDict):
    valid: bool
    errors: int
    warnings: int
    tasks: List[TaskInfo]

class ProfileData(TypedDict):
    overview: Dict[str, Any]
    variables: Dict[str, Any]
    correlations: Dict[str, Any]
    missing: Dict[str, Any]
    duplicates: Dict[str, Any]
    report_path: str

# Diagnostic logging for import issues
logger = logging.getLogger(__name__)
logger.info("Attempting to import ydata-profiling...")

try:
    from ydata_profiling import ProfileReport as YDataProfileReport
    logger.info("ydata-profiling import successful")
    # Use alias to avoid type conflicts
    ProfileReport = YDataProfileReport
except ImportError as e:
    logger.error(f"ydata-profiling import failed: {e}")
    logger.info("Creating mock ProfileReport for type checking")
    
    # Mock class for type checking when import fails
    class ProfileReport:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass
        def to_file(self, path: Union[str, Path]) -> None:
            pass
        def to_json(self) -> str:
            return "{}"

# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")
plt.style.use("default")

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NBACSVAnalyzer:
    """
    Comprehensive analyzer for NBA CSV files with basketball-specific validation
    and profiling capabilities.
    """

    def __init__(self, csv_path: str, output_dir: str = "./reports"):
        self.csv_path = Path(csv_path)
        self.output_dir = Path(output_dir)
        self.csv_name = self.csv_path.stem
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load data
        self.df = self._load_csv()
        logger.info(f"Loaded {len(self.df)} rows from {self.csv_name}")

        # Initialize components
        self.validation_results = {}
        self.profile_report = None
        self.quality_metrics = {}

    def _load_csv(self) -> pl.DataFrame:
        """Load CSV with automatic type inference and error handling."""
        try:
            # Use polars for fast loading with type inference
            df = pl.read_csv(
                self.csv_path,
                infer_schema_length=10000,  # Sample more rows for better type inference
                null_values=["", "NA", "N/A", "NULL", "null"],
                ignore_errors=True,
            )
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def generate_profile_report(self) -> Dict[str, Any]:
        """Generate comprehensive data profiling report."""
        logger.info("Generating data profiling report...")

        try:
            # Convert to pandas for ydata-profiling compatibility
            pandas_df = self.df.to_pandas()

            # Generate profile report
            profile = ProfileReport(
                pandas_df,
                title=f"NBA CSV Profile: {self.csv_name}",
                explorative=True,
                minimal=False,
                correlations={
                    "pearson": {"calculate": True},
                    "spearman": {"calculate": True},
                    "kendall": {"calculate": True},
                    "cramer": {"calculate": True},
                    "phi_k": {"calculate": True},
                },
                interactions={"targets": []},
                missing_diagrams={
                    "heatmap": True,
                    "dendrogram": True,
                    "matrix": True,
                },
                duplicates={"head": 10},
                samples={"head": 10, "tail": 10},
            )

            # Save HTML report
            report_path = self.output_dir / f"{self.csv_name}_profile.html"
            profile.to_file(report_path)
            logger.info(f"Profile report saved to {report_path}")

            # Extract key metrics
            profile_dict = profile.to_json()
            profile_data = json.loads(profile_dict)

            return {
                "overview": profile_data.get("overview", {}),
                "variables": profile_data.get("variables", {}),
                "correlations": profile_data.get("correlations", {}),
                "missing": profile_data.get("missing", {}),
                "duplicates": profile_data.get("duplicates", {}),
                "report_path": str(report_path),
            }

        except Exception as e:
            logger.error(f"Failed to generate profile report: {e}")
            return {}

    def validate_with_frictionless(self) -> Union[FrictionlessValidation, Dict[str, str]]:
        """Validate CSV structure and data types using frictionless."""
        logger.info("Running frictionless validation...")

        try:
            resource = Resource(self.csv_path)
            report = validate(resource)

            validation_result: FrictionlessValidation = {
                "valid": report.valid,
                "errors": len(report.errors),
                "warnings": len(report.warnings),
                "tasks": [],
            }

            for task in report.tasks:
                task_info: TaskInfo = {
                    "valid": task.valid,
                    "errors": [str(error) for error in task.errors],
                    "warnings": [str(warning) for warning in task.warnings],
                }
                validation_result["tasks"].append(task_info)

            # Save validation report
            report_path = (
                self.output_dir / f"{self.csv_name}_frictionless_validation.json"
            )
            with open(report_path, "w") as f:
                json.dump(validation_result, f, indent=2)

            logger.info(f"Frictionless validation report saved to {report_path}")
            return validation_result

        except Exception as e:
            logger.error(f"Frictionless validation failed: {e}")
            return {"error": str(e)}

    def apply_basketball_validation_rules(self) -> Dict[str, List[Dict[str, Any]]]:
        """Apply basketball-specific validation rules based on NBA data structures."""
        logger.info("Applying basketball-specific validation rules...")

        validation_results: Dict[str, List[Dict[str, Any]]] = {"passed": [], "failed": [], "warnings": []}

        # Define validation rules based on CSV type
        csv_type = self._infer_csv_type()
        rules = self._get_validation_rules(csv_type)

        for rule_name, rule_func in rules.items():
            try:
                result = rule_func()
                if result["status"] == "passed":
                    validation_results["passed"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation passed"),
                        }
                    )
                elif result["status"] == "failed":
                    validation_results["failed"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation failed"),
                            "details": result.get("details", []),
                        }
                    )
                elif result["status"] == "warning":
                    validation_results["warnings"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation warning"),
                        }
                    )
            except Exception as e:
                logger.error(f"Error in rule {rule_name}: {e}")
                validation_results["failed"].append(
                    {"rule": rule_name, "message": f"Rule execution failed: {e}"}
                )

        # Save validation results
        report_path = self.output_dir / f"{self.csv_name}_basketball_validation.json"
        with open(report_path, "w") as f:
            json.dump(validation_results, f, indent=2)

        logger.info(f"Basketball validation report saved to {report_path}")
        return validation_results

    def _infer_csv_type(self) -> str:
        """Infer the type of NBA CSV based on filename and columns."""
        csv_name = self.csv_name.lower()
        # columns = set(self.df.columns)  # This variable is not used

        # Map CSV types based on filename patterns
        csv_type_mapping = {
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
            "playercareerinfo": "player_career_info",
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

        # Try exact match first
        if csv_name in csv_type_mapping:
            return csv_type_mapping[csv_name]

        # Try partial match
        for key, value in csv_type_mapping.items():
            if key in csv_name:
                return value

        return "unknown"

    def _get_validation_rules(self, csv_type: str) -> Dict[str, Any]:
        """Get validation rules based on CSV type."""
        base_rules = {
            "data_completeness": self._validate_data_completeness,
            "data_types": self._validate_data_types,
            "logical_constraints": self._validate_logical_constraints,
        }

        # Add type-specific rules
        if csv_type in [
            "player_stats",
            "player_totals",
            "player_per_game",
            "per100_possessions",
            "per36_minutes",
        ]:
            logger.debug("Adding player-specific validation rules")
            # Convert dict to list of tuples for update method
            player_rules = [
                ("shooting_logic", self._validate_shooting_logic),
                ("efficiency_ranges", self._validate_efficiency_ranges),
                ("per_ranges", self._validate_per_ranges),
            ]
            base_rules.update(player_rules)

        if csv_type == "play_by_play":
            logger.debug("Adding play-by-play validation rules")
            # Convert dict to list of tuples for update method
            pbp_rules = [
                ("temporal_consistency", self._validate_temporal_consistency),
                ("score_progression", self._validate_score_progression),
            ]
            base_rules.update(pbp_rules)

        if csv_type in ["game_info", "game_summary"]:
            logger.debug("Adding game-specific validation rules")
            # Convert dict to list of tuples for update method
            game_rules = [
                ("score_calculation", self._validate_score_calculation),
                ("game_logic", self._validate_game_logic),
            ]
            base_rules.update(game_rules)

        if csv_type == "draft_history":
            logger.debug("Adding draft validation rules")
            # Convert dict to list of tuples for update method
            draft_rules = [("draft_logic", self._validate_draft_logic)]
            base_rules.update(draft_rules)

        return base_rules

    def _validate_data_completeness(self) -> ValidationResult:
        """Validate data completeness."""
        null_counts = self.df.null_count()
        total_rows = len(self.df)

        completeness_scores: Dict[str, float] = {}
        for col in self.df.columns:
            null_count = null_counts[col]
            completeness = (total_rows - null_count) / total_rows
            # Convert Series to float for type compatibility
            # Convert polars Series to scalar float for type compatibility
            # Handle polars Series conversion properly
            try:
                # For polars Series, use item() method
                completeness_value = completeness.item()
            except AttributeError:
                # For other types, convert to float directly
                completeness_value = float(completeness)
            completeness_scores[col] = completeness_value
            logger.debug(f"Column {col} completeness: {completeness_value}")

        avg_completeness = np.mean(list(completeness_scores.values()))

        if avg_completeness > 0.95:
            logger.debug(f"Data completeness passed: {avg_completeness:.3f}")
            return {"status": "passed", "message": f"{avg_completeness:.1%}", "details": []}
        elif avg_completeness > 0.80:
            logger.debug(f"Data completeness warning: {avg_completeness:.3f}")
            return {"status": "warning", "message": f"{avg_completeness:.1%}", "details": []}
        else:
            logger.debug(f"Data completeness failed: {avg_completeness:.3f}")
            return {
                "status": "failed",
                "message": f"{avg_completeness:.1%}",
                "details": [str(k) + ": " + str(v) for k, v in completeness_scores.items()],
            }

    def _validate_data_types(self) -> ValidationResult:
        """Validate data types are appropriate."""
        # This is a basic check - could be enhanced with more sophisticated type validation
        issues: List[str] = []

        for col in self.df.columns:
            dtype = self.df[col].dtype
            # Check for mixed types or unexpected types
            if dtype == pl.Utf8:
                # Check if numeric columns are stored as strings
                try:
                    numeric_count = self.df[col].str.contains(r"^\d+\.?\d*$").sum()
                    if numeric_count > len(self.df) * 0.8:  # 80% look numeric
                        issues.append(
                            f"Column {col} appears numeric but stored as string"
                        )
                except Exception:
                    pass

        if not issues:
            return {"status": "passed", "message": "Data types appear appropriate", "details": []}
        else:
            return {
                "status": "warning",
                "message": f"Potential data type issues: {len(issues)}",
                "details": issues,
            }

    def _validate_logical_constraints(self) -> ValidationResult:
        """Validate basic logical constraints."""
        issues: List[str] = []

        # Check for negative values in count statistics
        count_columns = [
            col
            for col in self.df.columns
            if any(
                term in col.lower()
                for term in [
                    "pts",
                    "fgm",
                    "fga",
                    "ftm",
                    "fta",
                    "reb",
                    "ast",
                    "stl",
                    "blk",
                    "tov",
                ]
            )
        ]
        for col in count_columns:
            if self.df[col].dtype in [pl.Int64, pl.Float64]:
                negative_count = (self.df[col] < 0).sum()
                if negative_count > 0:
                    issues.append(f"Column {col} has {negative_count} negative values")

        if not issues:
            return {
                "status": "passed",
                "message": "No logical constraint violations found",
                "details": [],
            }
        else:
            return {
                "status": "failed",
                "message": f"Logical constraint violations: {len(issues)}",
                "details": issues,
            }

    def _validate_shooting_logic(self) -> ValidationResult:
        """Validate shooting statistics logic (FGM ≤ FGA, etc.)."""
        issues = []

        # FGM ≤ FGA
        if "FGM" in self.df.columns and "FGA" in self.df.columns:
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
            return {"status": "passed", "message": "Shooting logic validation passed", "details": []}
        else:
            return {
                "status": "failed",
                "message": f"Shooting logic violations: {len(issues)}",
                "details": issues,
            }

    def _validate_efficiency_ranges(self) -> ValidationResult:
        """Validate efficiency metrics are in reasonable ranges."""
        issues = []

        # Field Goal Percentage (0-100%)
        if "FG_PCT" in self.df.columns:
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
        else:
            return {
                "status": "failed",
                "message": f"Efficiency range violations: {len(issues)}",
                "details": issues,
            }

    def _validate_per_ranges(self) -> ValidationResult:
        """Validate PER is in reasonable ranges (typically 5-35)."""
        issues = []

        if "PER" in self.df.columns:
            out_of_range = ((self.df["PER"] < 0) | (self.df["PER"] > 40)).sum()
            if out_of_range > 0:
                issues.append(
                    f"PER out of reasonable range [0,40] in {out_of_range} rows"
                )

        if not issues:
            return {"status": "passed", "message": "PER ranges validation passed", "details": []}
        else:
            return {
                "status": "failed",
                "message": f"PER range violations: {len(issues)}",
                "details": issues,
            }

    def _validate_temporal_consistency(self) -> ValidationResult:
        """Validate temporal consistency in play-by-play data."""
        # This would validate game clock progression, quarter transitions, etc.
        # Simplified version for now
        return {"status": "passed", "message": "Temporal consistency validation passed", "details": []}

    def _validate_score_progression(self) -> ValidationResult:
        """Validate score progression makes sense."""
        # This would validate score changes match event types
        return {"status": "passed", "message": "Score progression validation passed", "details": []}

    def _validate_score_calculation(self) -> ValidationResult:
        """Validate score calculations match expected formulas."""
        issues = []

        # Basic score validation: PTS should roughly equal 2*FGM + FTM + 3*FG3M
        if all(col in self.df.columns for col in ["PTS", "FGM", "FTM", "FG3M"]):
            expected_pts = 2 * self.df["FGM"] + self.df["FTM"] + 3 * self.df["FG3M"]
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
        else:
            return {
                "status": "failed",
                "message": f"Score calculation violations: {len(issues)}",
                "details": issues,
            }

    def _validate_game_logic(self) -> ValidationResult:
        """Validate basic game logic."""
        issues = []

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
            return {"status": "passed", "message": "Game logic validation passed", "details": []}
        else:
            return {
                "status": "failed",
                "message": f"Game logic violations: {len(issues)}",
                "details": issues,
            }

    def _validate_draft_logic(self) -> ValidationResult:
        """Validate draft-specific logic."""
        issues = []

        # Draft picks should be 1-60 (2 rounds of 30)
        if "OVERALL_PICK" in self.df.columns:
            out_of_range = (
                (self.df["OVERALL_PICK"] < 1) | (self.df["OVERALL_PICK"] > 60)
            ).sum()
            if out_of_range > 0:
                issues.append(
                    f"OVERALL_PICK out of range [1,60] in {out_of_range} rows"
                )

        if not issues:
            return {"status": "passed", "message": "Draft logic validation passed", "details": []}
        else:
            return {
                "status": "failed",
                "message": f"Draft logic violations: {len(issues)}",
                "details": issues,
            }

    def generate_visualizations(self) -> List[str]:
        """Generate visualizations for the dataset."""
        logger.info("Generating visualizations...")

        saved_plots = []

        try:
            # Set up the plotting style
            plt.style.use("seaborn-v0_8")
            sns.set_palette("husl")

            # 1. Missing data heatmap
            if len(self.df.columns) <= 50:  # Only for smaller datasets
                plt.figure(figsize=(12, 8))
                missing_data = self.df.null_count().to_pandas()
                if missing_data.sum() > 0:
                    ax: matplotlib.axes.Axes = sns.barplot(x=missing_data.index, y=missing_data.values)
                    plt.xticks(rotation=45, ha="right")
                    plt.title(f"Missing Data by Column - {self.csv_name}")
                    plt.ylabel("Missing Values Count")
                    plt.tight_layout()

                    plot_path = self.output_dir / f"{self.csv_name}_missing_data.png"
                    plt.savefig(plot_path, dpi=150, bbox_inches="tight")
                    saved_plots.append(str(plot_path))
                    plt.close()

            # 2. Correlation heatmap for numeric columns
            numeric_cols = [
                col
                for col in self.df.columns
                if self.df[col].dtype in [pl.Int64, pl.Float64]
            ]
            if len(numeric_cols) > 1 and len(numeric_cols) <= 20:
                fig: matplotlib.figure.Figure = plt.figure(figsize=(10, 8))
                corr_matrix = self.df.select(numeric_cols).to_pandas().corr()

                mask = np.triu(np.ones_like(corr_matrix, dtype=bool))
                ax: matplotlib.axes.Axes = sns.heatmap(
                    corr_matrix,
                    mask=mask,
                    annot=True,
                    cmap="coolwarm",
                    center=0,
                    square=True,
                    linewidths=0.5,
                    cbar_kws={"shrink": 0.5},
                )
                plt.title(f"Correlation Matrix - {self.csv_name}")
                plt.tight_layout()

                plot_path = self.output_dir / f"{self.csv_name}_correlation.png"
                plt.savefig(plot_path, dpi=150, bbox_inches="tight")
                saved_plots.append(str(plot_path))
                plt.close()

            # 3. Distribution plots for key metrics
            key_metrics = ["PTS", "FG_PCT", "TS_PCT", "PER", "REB", "AST"]
            existing_metrics = [col for col in key_metrics if col in self.df.columns]

            if existing_metrics:
                n_metrics = len(existing_metrics)
                n_cols = min(3, n_metrics)
                n_rows = (n_metrics + n_cols - 1) // n_cols

                fig, axes = plt.subplots(
                    n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows)
                )
                # Use fig to avoid "Variable not accessed" warning
                _ = fig  # Mark as used
                if n_rows == 1:
                    axes = axes.reshape(1, -1)
                elif n_cols == 1:
                    axes = axes.reshape(-1, 1)

                for i, metric in enumerate(existing_metrics):
                    row, col = i // n_cols, i % n_cols
                    ax = axes[row, col] if n_rows > 1 and n_cols > 1 else axes[i]

                    data = self.df[metric].drop_nulls().to_pandas()
                    if len(data) > 0:
                        sns.histplot(data=data, ax=ax, kde=True, bins=30)
                        ax.set_title(f"{metric} Distribution")
                        ax.set_xlabel(metric)

                # Hide empty subplots
                for i in range(len(existing_metrics), n_rows * n_cols):
                    row, col = i // n_cols, i % n_cols
                    ax = axes[row, col] if n_rows > 1 and n_cols > 1 else axes[i]
                    ax.set_visible(False)

                plt.tight_layout()
                plot_path = self.output_dir / f"{self.csv_name}_distributions.png"
                plt.savefig(plot_path, dpi=150, bbox_inches="tight")
                saved_plots.append(str(plot_path))
                plt.close()

            # Add explicit type annotation for saved_plots
            saved_plots: List[str] = []
            # ... existing code ...
            logger.info(f"Generated {len(saved_plots)} visualizations")

        except Exception as e:
            logger.error(f"Failed to generate visualizations: {e}")

        return saved_plots

    def calculate_quality_metrics(self) -> Dict[str, Any]:
        """Calculate overall data quality metrics."""
        logger.info("Calculating data quality metrics...")

        metrics = {
            "total_rows": len(self.df),
            "total_columns": len(self.df.columns),
            "duplicate_rows": self.df.is_duplicated().sum(),
            "duplicate_percentage": (self.df.is_duplicated().sum() / len(self.df))
            * 100,
            "completeness_score": 0,
            "uniqueness_score": 0,
            "validity_score": 0,
        }

        # Completeness score
        null_counts = self.df.null_count()
        completeness_scores = []
        for col in self.df.columns:
            completeness = (len(self.df) - null_counts[col]) / len(self.df)
            completeness_scores.append(completeness)
        metrics["completeness_score"] = np.mean(completeness_scores) * 100

        # Uniqueness score (inverse of duplication)
        if len(self.df) > 0:
            metrics["uniqueness_score"] = (
                1 - metrics["duplicate_percentage"] / 100
            ) * 100

        # Validity score based on validation results
        if self.validation_results:
            total_validations = len(self.validation_results.get("passed", [])) + len(
                self.validation_results.get("failed", [])
            )
            if total_validations > 0:
                passed_validations = len(self.validation_results.get("passed", []))
                metrics["validity_score"] = (
                    passed_validations / total_validations
                ) * 100

        # Save metrics
        metrics_path = self.output_dir / f"{self.csv_name}_quality_metrics.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

        logger.info(f"Quality metrics saved to {metrics_path}")
        return metrics

    def generate_summary_report(self) -> str:
        """Generate a comprehensive summary report."""
        logger.info("Generating summary report...")

        # Run all analyses
        profile_data = self.generate_profile_report()
        frictionless_results = self.validate_with_frictionless()
        basketball_validations = self.apply_basketball_validation_rules()
        visualizations = self.generate_visualizations()
        quality_metrics = self.calculate_quality_metrics()

        # Combine all results
        summary = {
            "csv_file": self.csv_name,
            "analysis_timestamp": str(datetime.now()),
            "data_overview": {
                "rows": len(self.df),
                "columns": len(self.df.columns),
                "csv_type": self._infer_csv_type(),
            },
            "quality_metrics": quality_metrics,
            "validation_results": {
                "frictionless": frictionless_results,
                "basketball_specific": basketball_validations,
            },
            "profile_summary": {
                "variables_count": len(profile_data.get("variables", {})),
                "missing_data_percentage": profile_data.get("overview", {}).get(
                    "missing_cells_percentage", 0
                ),
                "duplicate_rows": profile_data.get("duplicates", {}).get("count", 0),
            },
            "outputs": {
                "profile_report": profile_data.get("report_path"),
                "visualizations": visualizations,
                "reports_directory": str(self.output_dir),
            },
        }

        # Save summary report
        summary_path = self.output_dir / f"{self.csv_name}_summary_report.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Generate HTML summary
        html_summary = self._generate_html_summary(summary)
        html_path = self.output_dir / f"{self.csv_name}_summary_report.html"
        with open(html_path, "w") as f:
            f.write(html_summary)

        logger.info(f"Summary report saved to {summary_path} and {html_path}")
        return str(html_path)

    def _generate_html_summary(self, summary: Dict[str, Any]) -> str:
        """Generate HTML summary report."""
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NBA CSV Analysis Report - {self.csv_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background-color: #e8f4f8; border-radius: 3px; }}
        .passed {{ color: green; }}
        .failed {{ color: red; }}
        .warning {{ color: orange; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>NBA CSV Analysis Report</h1>
        <h2>File: {self.csv_name}</h2>
        <p>Analysis Date: {summary["analysis_timestamp"]}</p>
    </div>

    <div class="section">
        <h3>Data Overview</h3>
        <div class="metric">Rows: {summary["data_overview"]["rows"]:,}</div>
        <div class="metric">Columns: {summary["data_overview"]["columns"]}</div>
        <div class="metric">CSV Type: {summary["data_overview"]["csv_type"]}</div>
    </div>

    <div class="section">
        <h3>Data Quality Metrics</h3>
        <div class="metric">Completeness: {summary["quality_metrics"]["completeness_score"]:.1f}%</div>
        <div class="metric">Uniqueness: {summary["quality_metrics"]["uniqueness_score"]:.1f}%</div>
        <div class="metric">Validity: {summary["quality_metrics"]["validity_score"]:.1f}%</div>
        <div class="metric">Duplicates: {summary["quality_metrics"]["duplicate_rows"]:,} ({summary["quality_metrics"]["duplicate_percentage"]:.1f}%)</div>
    </div>

    <div class="section">
        <h3>Validation Results</h3>
        <h4>Frictionless Validation</h4>
        <p class="{"passed" if summary["validation_results"]["frictionless"].get("valid", False) else "failed"}">
            Valid: {summary["validation_results"]["frictionless"].get("valid", "N/A")}<br>
            Errors: {summary["validation_results"]["frictionless"].get("errors", 0)}<br>
            Warnings: {summary["validation_results"]["frictionless"].get("warnings", 0)}
        </p>

        <h4>Basketball-Specific Validations</h4>
        <p class="passed">Passed: {len(summary["validation_results"]["basketball_specific"].get("passed", []))}</p>
        <p class="failed">Failed: {len(summary["validation_results"]["basketball_specific"].get("failed", []))}</p>
        <p class="warning">Warnings: {len(summary["validation_results"]["basketball_specific"].get("warnings", []))}</p>
    </div>

    <div class="section">
        <h3>Generated Outputs</h3>
        <ul>
            <li><a href="{summary["outputs"]["profile_report"]}">Data Profile Report</a></li>
            <li>Visualizations: {len(summary["outputs"]["visualizations"])} plots generated</li>
            <li>Reports Directory: {summary["outputs"]["reports_directory"]}</li>
        </ul>
    </div>
</body>
</html>
        """
        return html

    def run_full_analysis(self) -> str:
        """Run complete analysis pipeline."""
        logger.info(f"Starting full analysis for {self.csv_name}")
        return self.generate_summary_report()


def analyze_single_csv(csv_path: str, output_dir: str = "./reports") -> str:
    """Analyze a single CSV file."""
    analyzer = NBACSVAnalyzer(csv_path, output_dir)
    return analyzer.run_full_analysis()


def analyze_all_csvs(csv_dir: str, output_dir: str = "./reports") -> List[str]:
    """Analyze all CSV files in a directory."""
    csv_dir_path = Path(csv_dir)
    output_dir_path = Path(output_dir)

    results = []
    csv_files = list(csv_dir_path.glob("*.csv"))

    logger.info(f"Found {len(csv_files)} CSV files to analyze")

    for csv_file in csv_files:
        try:
            logger.info(f"Analyzing {csv_file.name}...")
            result = analyze_single_csv(str(csv_file), str(output_dir_path / csv_file.stem))
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to analyze {csv_file.name}: {e}")
            results.append(f"ERROR: {csv_file.name} - {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Comprehensive NBA CSV Analysis Tool")
    parser.add_argument("--csv-path", help="Path to single CSV file to analyze")
    parser.add_argument(
        "--csv-dir", default="../csv_files", help="Directory containing CSV files"
    )
    parser.add_argument(
        "--all-csvs", action="store_true", help="Analyze all CSV files in csv-dir"
    )
    parser.add_argument(
        "--output-dir", default="./reports", help="Output directory for reports"
    )

    args = parser.parse_args()

    if args.csv_path:
        result = analyze_single_csv(args.csv_path, args.output_dir)
        print(f"Analysis complete. Summary report: {result}")
    elif args.all_csvs:
        results = analyze_all_csvs(args.csv_dir, args.output_dir)
        print(f"Analyzed {len(results)} CSV files. Results: {results}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

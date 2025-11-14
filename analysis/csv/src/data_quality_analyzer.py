"""Data quality analysis for NBA CSV files."""

import logging
from typing import Any, Dict

import numpy as np
import polars as pl
from analysis_types import ValidationResult

# Get logger from main module for consistent logging
logger = logging.getLogger('csv_analysis')


class DataQualityAnalyzer:
    """Analyzes data quality metrics and completeness."""

    def __init__(self, df: pl.DataFrame):
        """
        Initialize the analyzer.

        Args:
            df: Polars DataFrame containing the data
        """
        self.df = df

    def validate_data_completeness(self) -> ValidationResult:
        """Validate data completeness."""
        logger.debug(
            f"Validating data completeness for DataFrame with {len(self.df)} rows"
        )
        
        # Guard against empty DataFrame
        if len(self.df) == 0:
            logger.warning("DataFrame is empty - cannot validate completeness")
            return {
                "status": "warning",
                "message": "DataFrame is empty (0 rows)",
                "details": [],
            }
        
        null_counts = self.df.null_count()
        total_rows = len(self.df)
        logger.debug(f"Calculating completeness for {len(self.df.columns)} columns")

        completeness_scores: Dict[str, float] = {}
        for col in self.df.columns:
            null_count = null_counts[col]
            completeness = (total_rows - null_count) / total_rows
            # Handle polars Series conversion properly for type compatibility
            try:
                completeness_value = completeness.item()
            except (AttributeError, TypeError):
                # Convert to pandas Series first, then to float
                completeness_value = float(completeness.to_pandas().iloc[0])
            completeness_scores[col] = completeness_value
            
            # Log columns with low completeness
            if completeness_value < 0.5:
                logger.warning(
                    f"Column '{col}' has low completeness: "
                    f"{completeness_value:.2%} ({null_count}/{total_rows} nulls)"
                )
            else:
                logger.debug(f"Column '{col}' completeness: {completeness_value:.2%}")

        avg_completeness = np.mean(list(completeness_scores.values()))

        if avg_completeness > 0.95:
            logger.debug("Data completeness passed: %.3f", avg_completeness)
            return {
                "status": "passed",
                "message": f"{avg_completeness:.1%}",
                "details": [],
            }
        if avg_completeness > 0.80:
            logger.debug("Data completeness warning: %.3f", avg_completeness)
            return {
                "status": "warning",
                "message": f"{avg_completeness:.1%}",
                "details": [],
            }

        logger.debug("Data completeness failed: %.3f", avg_completeness)
        detail_lines = [f"{col}: {score}" for col, score in completeness_scores.items()]
        return {
            "status": "failed",
            "message": f"{avg_completeness:.1%}",
            "details": detail_lines,
        }

    def validate_data_types(self) -> ValidationResult:
        """Validate data types are appropriate."""
        logger.debug(f"Validating data types for {len(self.df.columns)} columns")
        issues: list[str] = []

        for col in self.df.columns:
            dtype = self.df[col].dtype
            logger.debug(f"Column '{col}' has dtype: {dtype}")
            
            # Check for mixed types or unexpected types
            if dtype == pl.Utf8:
                # Check if numeric columns are stored as strings
                try:
                    # More comprehensive numeric pattern
                    # (including decimals, negatives, scientific notation)
                    numeric_pattern = r"^-?\d+\.?\d*(?:[eE][+-]?\d+)?$"
                    non_null_df = self.df.filter(pl.col(col).is_not_null())
                    
                    if len(non_null_df) > 0:
                        numeric_count = non_null_df[col].str.contains(
                            numeric_pattern
                        ).sum()
                        numeric_percentage = numeric_count / len(non_null_df)
                        
                        if numeric_percentage > 0.8:  # 80% look numeric
                            issue_msg = (
                                f"Column '{col}' appears numeric "
                                f"({numeric_percentage:.1%} numeric values) "
                                f"but stored as string"
                            )
                            issues.append(issue_msg)
                            logger.warning(issue_msg)
                            logger.info(
                                f"  Sample values from '{col}': "
                                f"{non_null_df[col].head(5).to_list()}"
                            )
                        elif numeric_percentage > 0.3:
                            logger.info(
                                f"Column '{col}' has mixed content: "
                                f"{numeric_percentage:.1%} numeric values"
                            )
                    else:
                        logger.debug(f"Column '{col}' contains all null values")
                        
                except Exception as e:
                    logger.debug(f"Error checking if column '{col}' is numeric: {e}")
                    pass

        if not issues:
            return {
                "status": "passed",
                "message": "Data types appear appropriate",
                "details": [],
            }
        else:
            return {
                "status": "warning",
                "message": f"Potential data type issues: {len(issues)}",
                "details": issues,
            }

    def validate_logical_constraints(self) -> ValidationResult:
        """Validate basic logical constraints."""
        issues: list[str] = []

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

    def calculate_quality_metrics(self) -> Dict[str, Any]:
        """Calculate overall data quality metrics."""
        logger.info(
            f"Calculating data quality metrics for DataFrame with "
            f"{len(self.df)} rows, {len(self.df.columns)} columns"
        )

        total_rows = len(self.df)
        
        # Guard against empty DataFrame - critical for division by zero
        if total_rows == 0:
            logger.error(
                "Cannot calculate quality metrics for empty DataFrame (0 rows)"
            )
            logger.warning("Returning default quality metrics with zeros")
            return {
                "total_rows": 0,
                "total_columns": len(self.df.columns),
                "duplicate_rows": 0,
                "duplicate_percentage": 0.0,
                "completeness_score": 0.0,
                "uniqueness_score": 0.0,
                "validity_score": 0.0,
            }
        
        # Calculate duplicate statistics with division guard
        duplicate_count = self.df.is_duplicated().sum()
        duplicate_percentage = (
            (duplicate_count / total_rows) * 100 if total_rows > 0 else 0.0
        )
        
        logger.debug(
            f"Found {duplicate_count} duplicate rows "
            f"({duplicate_percentage:.2f}%)"
        )
        
        metrics: Dict[str, Any] = {
            "total_rows": total_rows,
            "total_columns": len(self.df.columns),
            "duplicate_rows": duplicate_count,
            "duplicate_percentage": duplicate_percentage,
            "completeness_score": 0.0,
            "uniqueness_score": 0.0,
            "validity_score": 0.0,
        }

        # Completeness score with division guard
        logger.debug("Calculating completeness scores per column...")
        null_counts = self.df.null_count().to_dicts()[0]
        completeness_scores: list[float] = []
        
        for col in self.df.columns:
            col_nulls = int(null_counts.get(col, 0))
            # Guard against division by zero
            completeness = (
                (total_rows - col_nulls) / total_rows
                if total_rows > 0 else 0.0
            )
            completeness_scores.append(float(completeness))
            
            if col_nulls > 0:
                missing_pct = (1 - completeness) * 100
                logger.debug(
                    f"Column '{col}': {col_nulls}/{total_rows} nulls "
                    f"({missing_pct:.1f}% missing)"
                )
        
        avg_completeness = (
            np.mean(completeness_scores) * 100
            if completeness_scores else 0.0
        )
        metrics["completeness_score"] = avg_completeness
        logger.info(f"Average completeness score: {avg_completeness:.2f}%")

        # Uniqueness score (inverse of duplication) with division guard
        if total_rows > 0:
            uniqueness = (1 - duplicate_percentage / 100) * 100
            metrics["uniqueness_score"] = uniqueness
            logger.info(f"Uniqueness score: {uniqueness:.2f}%")
        else:
            metrics["uniqueness_score"] = 0.0
            logger.debug("Uniqueness score set to 0 (empty DataFrame)")

        logger.info(
            f"Quality metrics calculation complete: "
            f"completeness={metrics['completeness_score']:.1f}%, "
            f"uniqueness={metrics['uniqueness_score']:.1f}%"
        )
        return metrics

#!/usr/bin/env python3
"""
Comprehensive NBA CSV Analysis Script

This script provides deep profiling, validation, and visualization of NBA CSV files
with basketball-specific validation rules and data quality checks.

Features:
- Data profiling with ydata-profiling
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
import gc
import json
import logging
import multiprocessing as mp
import os
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Union

import polars as pl

# Import modular components
from basketball_validator import BasketballValidator
from csv_type_inferrer import CSVTypeInferrer
from data_quality_analyzer import DataQualityAnalyzer
from report_generator import ReportGenerator
from visualization_generator import VisualizationGenerator

# Diagnostic logging for import issues
logging.info("Attempting to import ydata-profiling...")

try:
    from ydata_profiling import ProfileReport  # type: ignore[import-untyped]

    logging.info("ydata-profiling import successful")
except ImportError as exc:
    logging.error("ydata-profiling import failed: %s", exc)
    logging.info("Creating mock ProfileReport for type checking")

    class ProfileReport:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
            _ = args, kwargs  # Mark as used
            pass
        def to_file(self, path: Union[str, Path]) -> None:  # pragma: no cover
            _ = path  # Mark as used
            pass

        def to_json(self) -> str:  # pragma: no cover
            return "{}"


# Suppress warnings for cleaner output
warnings.filterwarnings("ignore")

# Setup comprehensive logging with file and console handlers
def setup_logging():
    """Configure comprehensive logging to both file and console."""
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"csv_analysis_{timestamp}.log"
    
    # Create logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Detailed formatter with function name and line number
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - '
        '[%(funcName)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler for detailed logs
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    # Console handler for important messages
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging initialized - detailed logs: {log_file}")
    return logger

logger = setup_logging()


def detect_and_convert_numeric_columns(df: pl.DataFrame) -> pl.DataFrame:
    """
    Detect string columns that appear to be numeric and attempt conversion.
    
    Args:
        df: Polars DataFrame to process
        
    Returns:
        DataFrame with numeric columns converted
    """
    logger.debug("Detecting and converting numeric string columns...")
    
    for col in df.columns:
        if df[col].dtype == pl.Utf8:
            # Sample non-null values to check if they're numeric
            non_null_df = df.filter(pl.col(col).is_not_null())
            
            if len(non_null_df) == 0:
                logger.debug(f"Column '{col}' contains all null values, skipping")
                continue
            
            # Pattern for numeric values
            # (including decimals, negatives, scientific notation)
            numeric_pattern = r"^-?\d+\.?\d*(?:[eE][+-]?\d+)?$"
            
            try:
                # Check if values match numeric pattern
                matches = non_null_df[col].str.contains(numeric_pattern)
                numeric_count = matches.sum()
                numeric_percentage = numeric_count / len(non_null_df)
                
                if numeric_percentage > 0.9:  # 90% threshold for conversion
                    logger.info(
                        f"Column '{col}' appears numeric "
                        f"({numeric_percentage:.1%} numeric values), converting..."
                    )
                    
                    # Attempt conversion with error handling
                    try:
                        df = df.with_columns(
                            pl.col(col).cast(pl.Float64, strict=False).alias(col)
                        )
                        converted_count = df[col].is_not_null().sum()
                        logger.info(
                            f"Successfully converted '{col}' to numeric "
                            f"({converted_count} values)"
                        )
                    except Exception as conv_error:
                        logger.warning(
                            f"Failed to convert column '{col}' to numeric: "
                            f"{conv_error}"
                        )
                elif numeric_percentage > 0.3:
                    logger.debug(
                        f"Column '{col}' has mixed content: "
                        f"{numeric_percentage:.1%} numeric values"
                    )
                    
            except Exception as e:
                logger.debug(f"Error analyzing column '{col}': {e}")
                continue
    
    return df


class NBACSVAnalyzer:
    """
    Simplified orchestrator for NBA CSV file analysis.
    Delegates specific responsibilities to specialized components.
    """

    def __init__(self, csv_path: str, output_dir: str = "analysis/csv/output"):
        self.csv_path = Path(csv_path)
        self.output_dir = Path(output_dir)
        self.csv_name = self.csv_path.stem
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load data
        logger.info(f"Starting analysis for {self.csv_name}")
        logger.debug(f"CSV path: {self.csv_path}, Output dir: {self.output_dir}")
        
        self.df = self._load_csv()
        
        # Early validation for empty DataFrames
        if len(self.df) == 0:
            logger.error(f"DataFrame is EMPTY (0 rows) for {self.csv_name}")
            logger.error("Cannot proceed with analysis on empty data")
            raise ValueError(f"CSV file {self.csv_name} contains no data rows")
        
        logger.info(
            f"Loaded {len(self.df)} rows, {len(self.df.columns)} columns "
            f"from {self.csv_name}"
        )
        logger.debug(f"Columns: {list(self.df.columns)}")
        dtypes_dict = dict(zip(
            self.df.columns,
            [str(dtype) for dtype in self.df.dtypes]
        ))
        logger.debug(f"Dtypes: {dtypes_dict}")

        # Infer CSV type
        self.csv_type = CSVTypeInferrer.infer_type(
            self.csv_name, set(self.df.columns)
        )
        logger.info(f"Inferred CSV type: {self.csv_type}")

        # Initialize specialized components
        self.quality_analyzer = DataQualityAnalyzer(self.df)
        self.basketball_validator = BasketballValidator(self.df, self.csv_type)
        self.viz_generator = VisualizationGenerator(
            self.df, self.csv_name, self.output_dir
        )
        self.report_generator = ReportGenerator(self.csv_name, self.output_dir)

        # Storage for results
        self.validation_results: Dict[str, list[Dict[str, Any]]] = {
            "passed": [],
            "failed": [],
            "warnings": [],
        }

    def _load_csv(self) -> pl.DataFrame:
        """Load CSV with automatic type inference and error handling."""
        try:
            logger.debug(f"Reading CSV file: {self.csv_path}")
            df = pl.read_csv(
                self.csv_path,
                infer_schema_length=1000,
                null_values=["", "NA", "N/A", "NULL", "null"],
                ignore_errors=True,
            )
            logger.debug(
                f"Initial load: {len(df)} rows, {len(df.columns)} columns"
            )
            
            # Detect and convert numeric string columns
            logger.debug("Attempting numeric type conversion for string columns...")
            df = detect_and_convert_numeric_columns(df)
            
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            logger.exception("Full traceback for CSV load error:")
            raise

    def generate_profile_report(self) -> Dict[str, Any]:
        """Generate comprehensive data profiling report."""
        if os.getenv("SKIP_PROFILE") == "1":
            logger.info("Skipping profile report generation due to SKIP_PROFILE=1")
            return {}

        logger.info(f"Generating data profiling report for {self.csv_name}...")
        logger.debug(
            f"DataFrame shape: {self.df.shape}, "
            f"memory usage: {self.df.estimated_size('mb'):.2f} MB"
        )

        try:
            logger.debug("Converting Polars DataFrame to Pandas...")
            pandas_df = self.df.to_pandas()
            logger.debug(f"Conversion complete. Pandas shape: {pandas_df.shape}")

            profile = ProfileReport(
                pandas_df,
                title=f"NBA CSV Profile: {self.csv_name}",
                explorative=False,
                minimal=True,
                correlations={"pearson": {"calculate": True}},
                interactions={"targets": []},
                missing_diagrams={
                    "heatmap": False,
                    "dendrogram": False,
                    "matrix": False,
                },
                duplicates={"head": 10},
                samples={"head": 10, "tail": 10},
            )

            report_path = self.output_dir / f"{self.csv_name}_profile.html"
            logger.debug(f"Saving profile report to {report_path}")
            profile.to_file(report_path)
            logger.info(f"Profile report saved to {report_path}")

            logger.debug("Converting profile to JSON...")
            profile_dict = profile.to_json()
            logger.debug(f"Profile JSON length: {len(profile_dict)} characters")
            
            profile_data = json.loads(profile_dict)
            profile_keys = (
                list(profile_data.keys())
                if isinstance(profile_data, dict)
                else 'NOT A DICT'
            )
            logger.debug(
                f"Profile data type: {type(profile_data)}, keys: {profile_keys}"
            )

            del pandas_df
            gc.collect()
            
            # Defensive extraction with logging
            result = {
                "overview": (
                    profile_data.get("overview", {})
                    if isinstance(profile_data, dict) else {}
                ),
                "variables": (
                    profile_data.get("variables", {})
                    if isinstance(profile_data, dict) else {}
                ),
                "correlations": (
                    profile_data.get("correlations", {})
                    if isinstance(profile_data, dict) else {}
                ),
                "missing": (
                    profile_data.get("missing", {})
                    if isinstance(profile_data, dict) else {}
                ),
                "duplicates": (
                    profile_data.get("duplicates", {})
                    if isinstance(profile_data, dict) else {}
                ),
                "report_path": str(report_path),
            }
            logger.debug(f"Extracted profile result keys: {list(result.keys())}")

            return result

        except Exception as e:
            logger.error(f"Failed to generate profile report: {e}")
            logger.exception("Full traceback for profile generation error:")
            return {}

    def apply_basketball_validation_rules(self) -> Dict[str, list[Dict[str, Any]]]:
        """Apply basketball-specific validation rules."""
        logger.info(
            f"Applying basketball-specific validation rules "
            f"for {self.csv_name}..."
        )
        logger.debug(f"CSV type: {self.csv_type}")

        validation_results: Dict[str, list[Dict[str, Any]]] = {
            "passed": [],
            "failed": [],
            "warnings": [],
        }

        # Get validation rules from specialized validator
        logger.debug("Retrieving validation rules from BasketballValidator...")
        rules = self.basketball_validator.get_validation_rules()
        logger.debug(f"Basketball-specific rules: {list(rules.keys())}")

        # Also add base quality rules
        base_rules = {
            "data_completeness": self.quality_analyzer.validate_data_completeness,
            "data_types": self.quality_analyzer.validate_data_types,
            "logical_constraints": self.quality_analyzer.validate_logical_constraints,
        }
        rules.update(base_rules)
        logger.info(f"Total validation rules to apply: {len(rules)}")

        for rule_name, rule_func in rules.items():
            try:
                logger.debug(f"Executing validation rule: {rule_name}")
                result = rule_func()
                logger.debug(
                    f"Rule '{rule_name}' returned: "
                    f"{result.get('status', 'UNKNOWN')} - type: {type(result)}"
                )
                
                if not isinstance(result, dict):
                    logger.error(
                        f"Rule '{rule_name}' returned non-dict type: "
                        f"{type(result)}"
                    )
                    validation_results["failed"].append({
                        "rule": rule_name,
                        "message": f"Rule returned invalid type: {type(result)}"
                    })
                    continue
                
                if result["status"] == "passed":
                    logger.debug(f"✓ Rule '{rule_name}' PASSED")
                    validation_results["passed"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation passed"),
                        }
                    )
                elif result["status"] == "failed":
                    details = result.get("details", [])
                    logger.warning(
                        f"✗ Rule '{rule_name}' FAILED: "
                        f"{result.get('message', 'No message')}"
                    )
                    if details:
                        if len(details) > 3:
                            logger.debug(f"  Failure details: {details[:3]}...")
                        else:
                            logger.debug(f"  Failure details: {details}")
                    validation_results["failed"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation failed"),
                            "details": details,
                        }
                    )
                elif result["status"] == "warning":
                    logger.info(
                        f"⚠ Rule '{rule_name}' WARNING: "
                        f"{result.get('message', 'No message')}"
                    )
                    validation_results["warnings"].append(
                        {
                            "rule": rule_name,
                            "message": result.get("message", "Validation warning"),
                        }
                    )
                else:
                    logger.warning(
                        f"Rule '{rule_name}' returned unknown status: "
                        f"{result.get('status', 'None')}"
                    )
            except Exception as e:
                logger.error(f"Error executing rule '{rule_name}': {e}")
                logger.exception(f"Full traceback for rule '{rule_name}':")
                validation_results["failed"].append(
                    {"rule": rule_name, "message": f"Rule execution failed: {e}"}
                )

        # Log summary statistics
        passed_count = len(validation_results["passed"])
        failed_count = len(validation_results["failed"])
        warning_count = len(validation_results["warnings"])
        total_count = passed_count + failed_count + warning_count
        
        logger.info(
            f"Validation summary: {passed_count} passed, {failed_count} failed, "
            f"{warning_count} warnings (total: {total_count})"
        )
        
        # Save validation results
        report_path = self.output_dir / f"{self.csv_name}_basketball_validation.json"
        logger.debug(f"Saving validation results to {report_path}")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(validation_results, f, ensure_ascii=False, indent=2)

        logger.info(f"Basketball validation report saved to {report_path}")
        self.validation_results = validation_results
        return validation_results

    def generate_summary_report(self) -> str:
        """Generate a comprehensive summary report."""
        logger.info("Generating summary report...")

        # Run all analyses
        profile_data = self.generate_profile_report()
        gc.collect()

        frictionless_results = ReportGenerator.validate_with_frictionless(
            self.csv_path
        )
        gc.collect()

        basketball_validations = self.apply_basketball_validation_rules()
        gc.collect()

        visualizations = self.viz_generator.generate_visualizations()
        gc.collect()

        quality_metrics = self.quality_analyzer.calculate_quality_metrics()

        # Add validity score based on validation results
        if self.validation_results:
            total_validations = len(self.validation_results.get("passed", [])) + len(
                self.validation_results.get("failed", [])
            )
            if total_validations > 0:
                passed_validations = len(self.validation_results.get("passed", []))
                quality_metrics["validity_score"] = (
                    passed_validations / total_validations
                ) * 100

        # Save quality metrics
        metrics_path = self.output_dir / f"{self.csv_name}_quality_metrics.json"
        with open(metrics_path, "w", encoding="utf-8") as f:
            json.dump(quality_metrics, f, ensure_ascii=False, indent=2)
        logger.info(f"Quality metrics saved to {metrics_path}")

        gc.collect()

        # Combine all results
        summary: Dict[str, Any] = {
            "csv_file": self.csv_name,
            "analysis_timestamp": str(datetime.now()),
            "data_overview": {
                "rows": len(self.df),
                "columns": len(self.df.columns),
                "csv_type": self.csv_type,
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
                "duplicate_rows": (
                    profile_data.get("duplicates", {}).get("count", 0)
                    if isinstance(profile_data.get("duplicates"), dict)
                    else 0
                ),
            },
            "outputs": {
                "profile_report": profile_data.get("report_path"),
                "visualizations": visualizations,
                "reports_directory": str(self.output_dir),
            },
        }

        # Use report generator to save summary
        html_path = self.report_generator.save_summary_report(summary)
        return html_path

    def run_full_analysis(self) -> str:
        """Run complete analysis pipeline."""
        logger.info(f"Starting full analysis for {self.csv_name}")
        return self.generate_summary_report()


def analyze_single_csv(csv_path: str, output_dir: str = "analysis/csv/output") -> str:
    """Analyze a single CSV file."""
    analyzer = NBACSVAnalyzer(csv_path, output_dir)
    return analyzer.run_full_analysis()


def analyze_all_csvs(
    csv_dir: str,
    output_dir: str = "analysis/csv/output",
    max_workers: int = 2,
    resume: bool = False,
) -> list[str]:
    """Analyze all CSV files in a directory."""
    csv_dir_path = Path(csv_dir)
    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    results: list[str] = []
    csv_files = list(csv_dir_path.glob("*.csv"))

    if resume:
        csv_files = [
            f
            for f in csv_files
            if not (
                output_dir_path / f.stem / f"{f.stem}_summary_report.html"
            ).exists()
        ]

    logger.info(f"Found {len(csv_files)} CSV files to analyze")

    # Process files in parallel
    with mp.Pool(processes=max_workers) as pool:
        tasks: list[tuple[str, str]] = []
        for csv_file in csv_files:
            csv_path_str = str(csv_file)
            output_subdir = str(output_dir_path / csv_file.stem)
            tasks.append((csv_path_str, output_subdir))

        try:
            results = pool.starmap(analyze_single_csv, tasks)
        except Exception as e:
            logger.error(f"Parallel processing failed: {e}")
            # Fallback to sequential processing
            results = []
            for csv_path_str, output_subdir in tasks:
                try:
                    result = analyze_single_csv(csv_path_str, output_subdir)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Failed to analyze {csv_path_str}: {e}")
                    results.append(f"ERROR: {Path(csv_path_str).name} - {e}")

    return results


def main() -> None:
    """Main function to parse arguments and run analysis."""
    parser = argparse.ArgumentParser(description="Comprehensive NBA CSV Analysis Tool")
    parser.add_argument("--csv-path", help="Path to single CSV file to analyze")
    parser.add_argument(
        "--csv-dir", default="../csv_files", help="Directory containing CSV files"
    )
    parser.add_argument(
        "--all-csvs", action="store_true", help="Analyze all CSV files in csv-dir"
    )
    parser.add_argument(
        "--output-dir",
        default="analysis/csv/output",
        help="Output directory for reports",
    )
    parser.add_argument(
        "--minimal",
        action="store_true",
        help="Run in minimal mode (skip heavy operations)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Maximum number of parallel workers (default: 2)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Skip already processed CSV files"
    )

    args = parser.parse_args()

    # Set environment variables for minimal mode
    if args.minimal:
        os.environ["SKIP_PROFILE"] = "1"
        os.environ["SKIP_FRICTIONLESS"] = "1"
        os.environ["SKIP_VISUALIZATIONS"] = "1"

    if args.csv_path:
        result = analyze_single_csv(args.csv_path, args.output_dir)
        print(f"Analysis complete. Summary report: {result}")
    elif args.all_csvs:
        results = analyze_all_csvs(
            args.csv_dir, args.output_dir, args.max_workers, args.resume
        )
        print(f"Analyzed {len(results)} CSV files. Results: {results}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

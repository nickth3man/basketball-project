"""Report generation for NBA CSV analysis."""

import json
import logging
from pathlib import Path
from typing import Any, Dict

from frictionless import Resource, validate

# Get logger from main module for consistent logging
logger = logging.getLogger('csv_analysis')


class ReportGenerator:
    """Generates HTML and JSON reports for CSV analysis."""

    def __init__(self, csv_name: str, output_dir: Path):
        """
        Initialize the report generator.

        Args:
            csv_name: Name of the CSV file (without extension)
            output_dir: Directory to save reports
        """
        self.csv_name = csv_name
        self.output_dir = output_dir

    def generate_html_summary(self, summary: Dict[str, Any]) -> str:
        """Generate HTML summary report."""
        logger.debug(f"Generating HTML summary for {self.csv_name}")
        logger.debug(f"Summary keys: {list(summary.keys())}")
        logger.debug(f"Summary type: {type(summary)}")
        
        # Defensive validation of summary structure
        if not isinstance(summary, dict):
            logger.error(f"Summary is not a dict, type: {type(summary)}")
            summary = {}
        
        # Validate validation_results structure with defensive defaults
        validation_results = summary.get("validation_results", {})
        if not isinstance(validation_results, dict):
            logger.error(
                f"validation_results is not a dict, type: "
                f"{type(validation_results)}. Using empty dict."
            )
            validation_results = {}
        
        # Defensive extraction of frictionless results
        frictionless = validation_results.get("frictionless", {})
        if not isinstance(frictionless, dict):
            logger.error(
                f"Frictionless results is not a dict, type: "
                f"{type(frictionless)}. Using empty dict."
            )
            logger.error(f"Frictionless value: {frictionless}")
            frictionless = {"valid": False, "errors": 0, "warnings": 0}
        
        # Defensive extraction of basketball-specific results
        basketball_specific = validation_results.get("basketball_specific", {})
        if not isinstance(basketball_specific, dict):
            logger.error(
                f"Basketball-specific results is not a dict, type: "
                f"{type(basketball_specific)}. Using empty dict."
            )
            basketball_specific = {"passed": [], "failed": [], "warnings": []}
        
        frictionless_keys = (
            list(frictionless.keys())
            if isinstance(frictionless, dict)
            else 'NOT A DICT'
        )
        basketball_keys = (
            list(basketball_specific.keys())
            if isinstance(basketball_specific, dict)
            else 'NOT A DICT'
        )
        logger.debug(
            f"Frictionless type: {type(frictionless)}, keys: {frictionless_keys}"
        )
        logger.debug(
            f"Basketball-specific type: {type(basketball_specific)}, "
            f"keys: {basketball_keys}"
        )
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>NBA CSV Analysis Report - {self.csv_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
        .section {{
            margin: 20px 0;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
        }}
        .metric {{
            display: inline-block;
            margin: 10px;
            padding: 10px;
            background-color: #e8f4f8;
            border-radius: 3px;
        }}
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
        <div class="metric">
            Completeness: {summary["quality_metrics"]["completeness_score"]:.1f}%
        </div>
        <div class="metric">
            Uniqueness: {summary["quality_metrics"]["uniqueness_score"]:.1f}%
        </div>
        <div class="metric">
            Validity: {summary["quality_metrics"]["validity_score"]:.1f}%
        </div>
        <div class="metric">
            Duplicates: {summary["quality_metrics"]["duplicate_rows"]:,}
            ({summary["quality_metrics"]["duplicate_percentage"]:.1f}%)
        </div>
    </div>

    <div class="section">
        <h3>Validation Results</h3>
        <h4>Frictionless Validation</h4>
        <p class="{
            "passed"
            if frictionless.get("valid", False)
            else "failed"
        }">
            Valid: {frictionless.get("valid", "N/A")}<br>
            Errors: {frictionless.get("errors", 0)}<br>
            Warnings: {frictionless.get("warnings", 0)}
        </p>

        <h4>Basketball-Specific Validations</h4>
        <p class="passed">
            Passed: {
            len(basketball_specific.get("passed", []))
        }
        </p>
        <p class="failed">
            Failed: {
            len(basketball_specific.get("failed", []))
        }
        </p>
        <p class="warning">
            Warnings: {
            len(basketball_specific.get("warnings", []))
        }
        </p>
    </div>

    <div class="section">
        <h3>Generated Outputs</h3>
        <ul>
            <li>
                <a href="{summary["outputs"]["profile_report"]}">
                    Data Profile Report
                </a>
            </li>
            <li>
                Visualizations: {len(summary["outputs"]["visualizations"])}
                plots generated
            </li>
            <li>
                Reports Directory: {summary["outputs"]["reports_directory"]}
            </li>
        </ul>
    </div>
</body>
</html>
        """
        return html

    def save_summary_report(
        self,
        summary: Dict[str, Any],
    ) -> str:
        """
        Save both JSON and HTML summary reports.

        Args:
            summary: Summary data dictionary

        Returns:
            Path to the HTML report
        """
        # Save JSON summary
        summary_path = self.output_dir / f"{self.csv_name}_summary_report.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Generate and save HTML summary
        html_summary = self.generate_html_summary(summary)
        html_path = self.output_dir / f"{self.csv_name}_summary_report.html"
        with open(html_path, "w") as f:
            f.write(html_summary)

        logger.info(f"Summary report saved to {summary_path} and {html_path}")
        return str(html_path)

    @staticmethod
    def validate_with_frictionless(csv_path: Path) -> Dict[str, Any]:
        """
        Validate CSV structure using frictionless framework
        with comprehensive error handling.

        Args:
            csv_path: Path to the CSV file

        Returns:
            Validation results dictionary (always returns a well-formed dict)
        """
        import os

        if os.getenv("SKIP_FRICTIONLESS") == "1":
            logger.info("Skipping frictionless validation due to SKIP_FRICTIONLESS=1")
            return {
                "skipped": True,
                "valid": True,
                "errors": 0,
                "warnings": 0,
                "tasks": []
            }

        logger.info(f"Running frictionless validation on {csv_path.name}...")
        logger.debug(f"CSV path: {csv_path}")

        try:
            resource = Resource(path=str(csv_path.resolve()))
            logger.debug(f"Created Frictionless Resource for {csv_path.name}")
            
            report = validate(resource)
            logger.debug(
                f"Frictionless validation complete. Report type: {type(report)}"
            )
            
            # Defensive attribute checking with hasattr and getattr
            if not hasattr(report, 'valid'):
                logger.error("Frictionless report missing 'valid' attribute")
                return {
                    "error": "Frictionless report structure unexpected",
                    "valid": False,
                    "errors": 0,
                    "warnings": 0,
                    "tasks": []
                }
            
            # Safely extract report attributes
            report_valid = getattr(report, 'valid', False)
            report_errors = getattr(report, 'errors', [])
            report_warnings = getattr(report, 'warnings', [])
            report_tasks = getattr(report, 'tasks', [])
            
            logger.debug(f"Report valid: {report_valid}")
            errors_count = (
                len(report_errors)
                if hasattr(report_errors, '__len__') else 'N/A'
            )
            warnings_count = (
                len(report_warnings)
                if hasattr(report_warnings, '__len__') else 'N/A'
            )
            tasks_count = (
                len(report_tasks)
                if hasattr(report_tasks, '__len__') else 'N/A'
            )
            logger.debug(
                f"Report errors type: {type(report_errors)}, "
                f"count: {errors_count}"
            )
            logger.debug(
                f"Report warnings type: {type(report_warnings)}, "
                f"count: {warnings_count}"
            )
            logger.debug(
                f"Report tasks type: {type(report_tasks)}, "
                f"count: {tasks_count}"
            )
            
            # Safely get lengths with error handling
            try:
                error_count = (
                    len(report_errors)
                    if hasattr(report_errors, '__len__') else 0
                )
            except TypeError:
                logger.warning(
                    f"Cannot get length of report.errors "
                    f"(type: {type(report_errors)})"
                )
                error_count = 0
            
            try:
                warning_count = (
                    len(report_warnings)
                    if hasattr(report_warnings, '__len__') else 0
                )
            except TypeError:
                logger.warning(
                    f"Cannot get length of report.warnings "
                    f"(type: {type(report_warnings)})"
                )
                warning_count = 0
            
            validation_result: Dict[str, Any] = {
                "valid": bool(report_valid),
                "errors": error_count,
                "warnings": warning_count,
                "tasks": [],
            }
            
            logger.info(
                f"Frictionless validation: valid={report_valid}, "
                f"errors={error_count}, warnings={warning_count}"
            )

            # Process tasks with defensive error handling
            if hasattr(report_tasks, '__iter__'):
                for task_idx, task in enumerate(report_tasks):
                    try:
                        logger.debug(f"Processing task {task_idx}, type: {type(task)}")
                        
                        # Defensive attribute extraction
                        task_valid = getattr(task, 'valid', True)
                        task_errors = getattr(task, 'errors', [])
                        task_warnings = getattr(task, 'warnings', [])
                        
                        # Convert errors to strings safely
                        error_strings = []
                        if hasattr(task_errors, '__iter__'):
                            for err in task_errors:
                                try:
                                    error_strings.append(str(err))
                                except Exception as e:
                                    logger.debug(
                                        f"Could not convert error to string: {e}"
                                    )
                                    error_strings.append("<unparseable error>")
                        
                        # Convert warnings to strings safely
                        warning_strings = []
                        if hasattr(task_warnings, '__iter__'):
                            for warn in task_warnings:
                                try:
                                    warning_strings.append(str(warn))
                                except Exception as e:
                                    logger.debug(
                                        f"Could not convert warning to string: {e}"
                                    )
                                    warning_strings.append("<unparseable warning>")
                        
                        task_info: Dict[str, Any] = {
                            "valid": bool(task_valid),
                            "errors": error_strings,
                            "warnings": warning_strings,
                        }
                        validation_result["tasks"].append(task_info)
                        logger.debug(
                            f"Task {task_idx}: valid={task_valid}, "
                            f"errors={len(error_strings)}, "
                            f"warnings={len(warning_strings)}"
                        )
                        
                    except Exception as e:
                        logger.error(f"Error processing task {task_idx}: {e}")
                        logger.exception(f"Full traceback for task {task_idx}:")
                        # Continue processing other tasks
                        continue
            else:
                logger.warning(
                    f"Report.tasks is not iterable (type: {type(report_tasks)})"
                )

            # Save validation report
            try:
                report_dir = csv_path.parent.parent / "output" / csv_path.stem
                report_dir.mkdir(parents=True, exist_ok=True)
                report_path = (
                    report_dir / f"{csv_path.stem}_frictionless_validation.json"
                )

                logger.debug(f"Saving validation result to {report_path}")
                with open(report_path, "w", encoding='utf-8') as f:
                    json.dump(validation_result, f, indent=2, ensure_ascii=False)

                logger.info(f"Frictionless validation report saved to {report_path}")
            except Exception as e:
                logger.error(f"Failed to save Frictionless validation report: {e}")
            
            # Ensure we always return a well-formed dict
            return validation_result

        except Exception as e:
            logger.error(f"Frictionless validation failed with exception: {e}")
            logger.exception("Full traceback for Frictionless validation error:")
            # Return a well-formed error dict
            return {
                "error": str(e),
                "valid": False,
                "errors": 1,
                "warnings": 0,
                "tasks": []
            }

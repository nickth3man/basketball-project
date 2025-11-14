"""
Ingestion manifest loader and validator.

Provides utilities to:
- Load the canonical ingestion manifest (docs/ingestion_manifest.yaml)
- Verify CSV files match expected line counts and SHA256 hashes
- Track which files have been successfully loaded

The manifest serves as the single source of truth for CSV ingestion,
ensuring 100% accuracy by cryptographically verifying files before load.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml

from .config import Config
from .logging_utils import get_logger, log_structured

logger = get_logger(__name__)


@dataclass(frozen=True)
class ManifestEntry:
    """
    Represents a single CSV file in the ingestion manifest.
    """

    csv_file: str
    target_table: Optional[str]
    description: str
    line_count: int
    size_bytes: int
    sha256: str
    status: str  # 'mapped' or 'unmapped'


@dataclass(frozen=True)
class IngestionManifest:
    """
    Complete ingestion manifest with metadata and file entries.
    """

    version: str
    generated_at: str
    description: str
    entries: Dict[str, ManifestEntry]  # keyed by csv_file


def load_manifest(
    manifest_path: str = "docs/ingestion_manifest.yaml",
) -> IngestionManifest:
    """
    Load the ingestion manifest from YAML.

    Args:
        manifest_path: Path to manifest file (relative to project root)

    Returns:
        IngestionManifest instance

    Raises:
        FileNotFoundError: If manifest file doesn't exist
        ValueError: If manifest format is invalid
    """
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Manifest must be a YAML dictionary")

    entries = {}
    for file_spec in data.get("files", []):
        entry = ManifestEntry(
            csv_file=file_spec["csv_file"],
            target_table=file_spec.get("target_table"),
            description=file_spec.get("description", ""),
            line_count=file_spec["line_count"],
            size_bytes=file_spec["size_bytes"],
            sha256=file_spec["sha256"],
            status=file_spec.get("status", "mapped"),
        )
        entries[entry.csv_file] = entry

    logger.info(
        "Loaded ingestion manifest: version=%s, files=%d",
        data.get("version", "unknown"),
        len(entries),
    )

    return IngestionManifest(
        version=data.get("version", "unknown"),
        generated_at=data.get("generated_at", "unknown"),
        description=data.get("description", ""),
        entries=entries,
    )


def compute_file_hash(path: str, algorithm: str = "sha256") -> str:
    """
    Compute cryptographic hash of a file.

    Args:
        path: Path to file
        algorithm: Hash algorithm (default: sha256)

    Returns:
        Hex digest of file hash
    """
    digest = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def count_file_lines(path: str) -> int:
    """
    Count lines in a text file.

    Args:
        path: Path to file

    Returns:
        Number of lines
    """
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return sum(1 for _ in f)


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a CSV file against manifest."""

    csv_file: str
    passed: bool
    errors: List[str]
    line_count_actual: Optional[int] = None
    line_count_expected: Optional[int] = None
    hash_actual: Optional[str] = None
    hash_expected: Optional[str] = None


def validate_file(
    config: Config,
    entry: ManifestEntry,
    check_hash: bool = True,
    check_line_count: bool = True,
) -> ValidationResult:
    """
    Validate a CSV file against its manifest entry.

    Args:
        config: ETL configuration
        entry: Manifest entry to validate
        check_hash: Whether to verify SHA256 hash
        check_line_count: Whether to verify line count

    Returns:
        ValidationResult with pass/fail status and details
    """
    csv_path = os.path.join(config.effective_csv_root, entry.csv_file)
    errors = []

    if not os.path.exists(csv_path):
        return ValidationResult(
            csv_file=entry.csv_file,
            passed=False,
            errors=[f"File not found: {csv_path}"],
        )

    line_count_actual = None
    hash_actual = None

    # Check line count
    if check_line_count:
        try:
            line_count_actual = count_file_lines(csv_path)
            if line_count_actual != entry.line_count:
                errors.append(
                    f"Line count mismatch: expected {entry.line_count}, "
                    f"got {line_count_actual}"
                )
        except Exception as exc:
            errors.append(f"Failed to count lines: {exc}")

    # Check hash
    if check_hash:
        try:
            hash_actual = compute_file_hash(csv_path)
            if hash_actual != entry.sha256:
                errors.append(
                    f"SHA256 mismatch: expected {entry.sha256[:16]}..., "
                    f"got {hash_actual[:16]}..."
                )
        except Exception as exc:
            errors.append(f"Failed to compute hash: {exc}")

    result = ValidationResult(
        csv_file=entry.csv_file,
        passed=len(errors) == 0,
        errors=errors,
        line_count_actual=line_count_actual,
        line_count_expected=entry.line_count,
        hash_actual=hash_actual,
        hash_expected=entry.sha256,
    )

    if result.passed:
        log_structured(
            logger,
            logger.level,
            "CSV validation passed",
            csv_file=entry.csv_file,
            lines=line_count_actual,
        )
    else:
        log_structured(
            logger,
            logger.level,
            "CSV validation FAILED",
            csv_file=entry.csv_file,
            errors=errors,
        )

    return result


def validate_all_files(
    config: Config,
    manifest: IngestionManifest,
    check_hash: bool = True,
    check_line_count: bool = True,
    only_mapped: bool = True,
) -> Dict[str, ValidationResult]:
    """
    Validate all CSV files against the manifest.

    Args:
        config: ETL configuration
        manifest: Ingestion manifest
        check_hash: Whether to verify SHA256 hashes
        check_line_count: Whether to verify line counts
        only_mapped: If True, only validate files with target_table set

    Returns:
        Dictionary of csv_file -> ValidationResult
    """
    results = {}

    for csv_file, entry in manifest.entries.items():
        if only_mapped and not entry.target_table:
            continue

        results[csv_file] = validate_file(
            config,
            entry,
            check_hash=check_hash,
            check_line_count=check_line_count,
        )

    passed = sum(1 for r in results.values() if r.passed)
    failed = len(results) - passed

    log_structured(
        logger,
        logger.level,
        "Completed manifest validation",
        total=len(results),
        passed=passed,
        failed=failed,
    )

    return results


def generate_validation_report(results: Dict[str, ValidationResult]) -> str:
    """
    Generate a human-readable validation report.

    Args:
        results: Validation results from validate_all_files

    Returns:
        Formatted report string
    """
    lines = ["=" * 80, "CSV MANIFEST VALIDATION REPORT", "=" * 80, ""]

    passed = [r for r in results.values() if r.passed]
    failed = [r for r in results.values() if not r.passed]

    lines.append(f"Total files validated: {len(results)}")
    lines.append(f"Passed: {len(passed)}")
    lines.append(f"Failed: {len(failed)}")
    lines.append("")

    if failed:
        lines.append("FAILURES:")
        lines.append("-" * 80)
        for result in failed:
            lines.append(f"\n{result.csv_file}:")
            for error in result.errors:
                lines.append(f"  - {error}")
        lines.append("")

    if passed:
        lines.append("PASSED:")
        lines.append("-" * 80)
        for result in passed:
            lines.append(
                f"  {result.csv_file:40} {result.line_count_actual:>12,} lines"
            )

    lines.append("")
    lines.append("=" * 80)
    return "\n".join(lines)

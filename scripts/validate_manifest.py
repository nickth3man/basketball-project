"""
CLI tool to validate CSV files against the ingestion manifest.

Usage:
    python scripts/validate_manifest.py [--no-hash] [--no-count] [--all]

Options:
    --no-hash: Skip SHA256 hash verification
    --no-count: Skip line count verification
    --all: Include unmapped files in validation
"""

import argparse
import sys

from etl.config import get_config
from etl.manifest import (
    generate_validation_report,
    load_manifest,
    validate_all_files,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate CSV files against ingestion manifest"
    )
    parser.add_argument(
        "--no-hash",
        action="store_true",
        help="Skip SHA256 hash verification",
    )
    parser.add_argument(
        "--no-count",
        action="store_true",
        help="Skip line count verification",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Include unmapped files in validation",
    )

    args = parser.parse_args()

    try:
        config = get_config()
        manifest = load_manifest()

        results = validate_all_files(
            config,
            manifest,
            check_hash=not args.no_hash,
            check_line_count=not args.no_count,
            only_mapped=not args.all,
        )

        report = generate_validation_report(results)
        print(report)

        failed_count = sum(1 for r in results.values() if not r.passed)
        return 1 if failed_count > 0 else 0

    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001
        print(f"UNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())

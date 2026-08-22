#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from ai.kie.evaluation import (
    COMPLETED_STATUS,
    DEFAULT_MANIFEST_PATH,
    DEFAULT_REPORT_PATH,
    DEFAULT_SPLIT_PATH,
    evaluate_manifest,
    write_evaluation_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate deterministic KIE field extraction in separate "
            "Real OCR and Oracle OCR modes."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST_PATH,
    )
    parser.add_argument(
        "--split",
        type=Path,
        default=DEFAULT_SPLIT_PATH,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_manifest(
        args.manifest,
        split_path=args.split,
    )
    report_path = write_evaluation_report(
        report,
        args.report,
    )

    print(
        json.dumps(
            {
                "status": report["status"],
                "report_path": str(report_path),
                "sample_counts": report[
                    "sample_counts"
                ],
                "reasons": report.get("reasons", []),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )

    if report["status"] == COMPLETED_STATUS:
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Generate field-aware OCR error analysis from verified annotation records."""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.ocr.field_analysis import evaluate_field_errors

DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "field_evaluation" / "manifest.json"
DEFAULT_REPORT = PROJECT_ROOT / "results" / "field_aware_error_report.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--allow-examples",
        action="store_true",
        help="Allow explicitly synthetic/example-only records for harness tests.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    command = " ".join(shlex.quote(part) for part in ["python", *sys.argv])
    report = evaluate_field_errors(
        manifest_path=args.manifest,
        report_path=args.output,
        allow_examples=args.allow_examples,
        run_command=command,
    )
    print(
        f"{report['status']}: {report['evaluated_receipt_count']} receipts / "
        f"{report['evaluated_field_count']} fields"
    )
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()

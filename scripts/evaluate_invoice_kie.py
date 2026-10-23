"""Invoice V2 frozen evaluation: exit 2 with null metrics while data is unavailable."""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ai.kie.v2.evaluation import VERSION, evaluate
from ai.kie.v2.config import (
    BASELINE_GROUPING,
    GROUPING_CONFIGURATIONS,
    INTERVAL_GROUPING,
)


def flatten_metrics(value, prefix=""):
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            yield from flatten_metrics(item, name)
        elif item is None or type(item) in (int, float):
            yield name, item


def write_report(report, output):
    """New run directory only; full JSON includes gold, predictions and matches."""
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with (output / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "metric",
                "baseline",
                "variant",
                "delta",
                "status",
                "evaluated",
                "required",
            ]
        )
        baseline = dict(
            flatten_metrics(
                (report["metrics"] or {})
                if report["grouping"] == BASELINE_GROUPING
                else {}
            )
        )
        variant = dict(
            flatten_metrics(
                (report.get("variants") or {})
                .get(INTERVAL_GROUPING, {})
                .get("metrics", {})
            )
        )
        delta = dict(flatten_metrics(report.get("delta") or {}))
        for key in sorted(
            (baseline.keys() | variant.keys())
            or {
                "lines.detection_f1": None,
                "header_micro_accuracy": None,
                "lines.complete_line_accuracy": None,
            }
        ):
            writer.writerow(
                [
                    key,
                    baseline.get(key),
                    variant.get(key),
                    delta.get(key),
                    report["status"],
                    report["evaluated"],
                    report["coverage"]["required"],
                ]
            )
    with (output / "samples.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "sample_id",
                "grouping",
                "mode",
                "status",
                "gold_rows",
                "predicted_rows",
                "matched_rows",
                "row_precision",
                "row_recall",
                "row_f1",
                "cell_accuracy",
                "complete_line_accuracy",
                "header_micro_accuracy",
                "consistency_warnings",
            ]
        )
        for sample in report["samples"]:
            for grouping, modes in sample["variants"].items():
                for mode, item in modes.items():
                    metric = item.get("metrics", {})
                    lines = metric.get("lines", {})
                    writer.writerow(
                        [
                            sample["sample_id"],
                            grouping,
                            mode,
                            report["status"],
                            *[
                                lines.get(key)
                                for key in (
                                    "gold_rows",
                                    "predicted_rows",
                                    "matched_rows",
                                    "detection_precision",
                                    "detection_recall",
                                    "detection_f1",
                                    "matched_row_cell_correctness",
                                    "complete_line_accuracy",
                                )
                            ],
                            metric.get("header_micro_accuracy"),
                            metric.get("error_taxonomy", {}).get("CONSISTENCY_WARNING"),
                        ]
                    )
    with (output / "failures.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "record_index",
                "sample_id",
                "stage",
                "grouping",
                "mode",
                "reason",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(report["failures"])
        for reason in report["reasons"]:
            writer.writerow({"stage": "run", "reason": reason})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--print-experiment",
        action="store_true",
        help="Print the exact proposed experiment contract; does not grant QA approval",
    )
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/invoice_v2/manifest.json")
    )
    parser.add_argument(
        "--grouping", choices=GROUPING_CONFIGURATIONS, default=BASELINE_GROUPING
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Paired development A/B; requires manifest experiment authorization",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="New directory for report.json and summary/samples/failures CSV",
    )
    args = parser.parse_args()
    if args.print_experiment:
        print(
            json.dumps(
                {
                    "protocol": "grouping-ab-1.0",
                    "evaluator_version": VERSION,
                    "configurations": GROUPING_CONFIGURATIONS,
                },
                indent=2,
            )
        )
        return 0
    if args.compare and args.grouping != BASELINE_GROUPING:
        parser.error("--compare always runs both configurations; omit --grouping")
    if args.output and args.output.exists():
        parser.error("--output must be a new directory")
    report = evaluate(args.manifest, comparison=args.compare, grouping=args.grouping)
    if args.output:
        write_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))
    return 0 if report["status"] == "COMPLETED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate the explicitly annotated OCR probe subset with transparent coverage."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import jiwer
from jsonschema import Draft202012Validator, FormatChecker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = PROJECT_ROOT / "data" / "test_set" / "test_manifest.csv"
GT_DIR = PROJECT_ROOT / "data" / "ground_truth"
OCR_DIR = PROJECT_ROOT / "results" / "ocr_outputs"
REPORT_PATH = PROJECT_ROOT / "results" / "evaluation_report.csv"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "ocr-result.schema.json"

NORMALIZATION_POLICY = "collapse all whitespace sequences to one ASCII space"
METRIC_POLICY = "macro-average CER/WER over evaluated samples"
SAMPLING_RATIONALE = (
    "preliminary Week-1 probe using the seven available non-empty legacy "
    "transcriptions; not a performance estimate for all 40 frozen samples"
)
ANNOTATED_STATUSES = {"annotated", "reviewed"}


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def load_expected_samples(manifest_path: Path) -> list[dict[str, str]]:
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"Manifest is empty: {manifest_path}")
    if len({row["test_id"] for row in rows}) != len(rows):
        raise ValueError("Manifest contains duplicate test_id values")
    return rows


def load_validator(schema_path: Path) -> Draft202012Validator:
    with schema_path.open(encoding="utf-8") as handle:
        schema = json.load(handle)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def read_ocr_text(
    json_path: Path, validator: Draft202012Validator
) -> tuple[str, list[str]]:
    with json_path.open(encoding="utf-8") as handle:
        document: dict[str, Any] = json.load(handle)
    errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
    if errors:
        messages = [
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        ]
        return "", messages
    return normalize_text(" ".join(block["text"] for block in document["blocks"])), []


def evaluate(
    *,
    manifest_path: Path = MANIFEST_PATH,
    gt_dir: Path = GT_DIR,
    ocr_dir: Path = OCR_DIR,
    report_path: Path = REPORT_PATH,
    schema_path: Path = SCHEMA_PATH,
) -> dict[str, Any]:
    manifest_rows = load_expected_samples(manifest_path)
    validator = load_validator(schema_path)

    metric_rows: list[dict[str, Any]] = []
    missing_gt_ids: list[str] = []
    empty_gt_ids: list[str] = []
    missing_ocr_ids: list[str] = []
    invalid_ocr_ids: list[str] = []

    for manifest_row in manifest_rows:
        sample_id = manifest_row["test_id"]
        gt_status = manifest_row["ground_truth_status"].strip().lower()
        gt_path = gt_dir / f"{sample_id}.txt"
        ocr_path = ocr_dir / f"{sample_id}.json"

        if gt_status not in ANNOTATED_STATUSES or not gt_path.exists():
            missing_gt_ids.append(sample_id)
            continue

        gt_text = normalize_text(gt_path.read_text(encoding="utf-8"))
        if not gt_text:
            empty_gt_ids.append(sample_id)
            continue
        if not ocr_path.exists():
            missing_ocr_ids.append(sample_id)
            continue

        ocr_text, validation_errors = read_ocr_text(ocr_path, validator)
        if validation_errors:
            invalid_ocr_ids.append(sample_id)
            continue

        metric_rows.append(
            {
                "sample_id": sample_id,
                "cer_percent": round(jiwer.cer(gt_text, ocr_text) * 100, 2),
                "wer_percent": round(jiwer.wer(gt_text, ocr_text) * 100, 2),
            }
        )

    expected_count = len(manifest_rows)
    evaluated_ids = [row["sample_id"] for row in metric_rows]
    evaluated_count = len(metric_rows)
    incomplete_ids = sorted(
        set(missing_gt_ids + empty_gt_ids + missing_ocr_ids + invalid_ocr_ids)
    )
    status = "COMPLETE" if evaluated_count == expected_count else "INCOMPLETE"
    macro_cer = (
        round(sum(row["cer_percent"] for row in metric_rows) / evaluated_count, 2)
        if evaluated_count
        else None
    )
    macro_wer = (
        round(sum(row["wer_percent"] for row in metric_rows) / evaluated_count, 2)
        if evaluated_count
        else None
    )

    metadata = {
        "evaluation_scope": "Preliminary baseline / probe",
        "status": status,
        "expected_count": expected_count,
        "evaluated_count": evaluated_count,
        "missing_count": len(incomplete_ids),
        "evaluated_sample_ids": ",".join(evaluated_ids),
        "missing_sample_ids": ",".join(incomplete_ids),
        "missing_gt_ids": ",".join(missing_gt_ids),
        "empty_gt_ids": ",".join(empty_gt_ids),
        "missing_ocr_ids": ",".join(missing_ocr_ids),
        "invalid_ocr_ids": ",".join(invalid_ocr_ids),
        "normalization_policy": NORMALIZATION_POLICY,
        "metric_policy": METRIC_POLICY,
        "sampling_rationale": SAMPLING_RATIONALE,
        "macro_cer_percent": macro_cer,
        "macro_wer_percent": macro_wer,
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "record_type",
            "sample_id",
            "cer_percent",
            "wer_percent",
            "metadata_key",
            "metadata_value",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in metric_rows:
            writer.writerow({"record_type": "sample", **row})
        for key, value in metadata.items():
            writer.writerow(
                {
                    "record_type": "metadata",
                    "metadata_key": key,
                    "metadata_value": "" if value is None else value,
                }
            )

    return {"metrics": metric_rows, "metadata": metadata}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="Return exit code 2 when any frozen sample is not evaluated.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = evaluate()
    metadata = result["metadata"]
    print(
        f"{metadata['evaluation_scope']}: {metadata['evaluated_count']}/"
        f"{metadata['expected_count']} samples ({metadata['status']})"
    )
    print(f"Evaluated IDs: {metadata['evaluated_sample_ids'] or '<none>'}")
    print(f"Missing IDs: {metadata['missing_sample_ids'] or '<none>'}")
    print(f"Normalization: {metadata['normalization_policy']}")
    print(f"Metric: {metadata['metric_policy']}")
    if metadata["evaluated_count"]:
        print(
            "Macro average: "
            f"CER={metadata['macro_cer_percent']:.2f}% "
            f"WER={metadata['macro_wer_percent']:.2f}%"
        )
    print(f"Report: {REPORT_PATH}")
    if args.require_complete and metadata["status"] != "COMPLETE":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

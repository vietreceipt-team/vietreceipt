"""Field-aware OCR error analysis over KIE/Data-owned annotations."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .contract import PROJECT_ROOT, validate_ocr_result
from .pipeline import OCR_LANGUAGE, OCR_MODEL_VERSION

CANONICAL_FIELDS = (
    "merchant_name",
    "receipt_date",
    "total_amount",
    "invoice_id",
    "merchant_address",
)
PRIMARY_RESEARCH_FIELDS = {"merchant_name", "receipt_date", "total_amount"}
ERROR_TYPES = (
    "ocr_omission",
    "ocr_substitution",
    "ocr_segmentation_grouping",
    "ocr_reading_order",
    "ocr_geometry_evidence",
    "not_an_ocr_error",
)
ANNOTATION_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "annotation-record.schema.json"

NOTE_ERROR_CODES = {
    "OCR_OMISSION": "ocr_omission",
    "OCR_SUBSTITUTION": "ocr_substitution",
    "OCR_SEGMENTATION": "ocr_segmentation_grouping",
    "OCR_READING_ORDER": "ocr_reading_order",
    "OCR_GEOMETRY": "ocr_geometry_evidence",
}


def normalize_evidence_text(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def _load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _annotation_validator() -> Draft202012Validator:
    schema = _load_json(ANNOTATION_SCHEMA_PATH)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate_annotation(annotation: dict[str, Any], path: Path) -> None:
    errors = sorted(
        _annotation_validator().iter_errors(annotation),
        key=lambda error: list(error.path),
    )
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"Invalid annotation {path}: {details}")


def _resolve(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (manifest_path.parent / path).resolve()


def _note_error_type(note: str | None) -> str | None:
    if not note:
        return None
    prefix = note.split(":", 1)[0].strip().upper()
    return NOTE_ERROR_CODES.get(prefix)


def classify_field_error(
    field_annotation: dict[str, Any],
    real_ocr: dict[str, Any],
) -> dict[str, Any]:
    """Classify OCR evidence without turning downstream KIE errors into OCR errors."""
    status = field_annotation["annotation_status"]
    source_ids = list(field_annotation["source_block_ids"])
    expected_text = normalize_evidence_text(field_annotation.get("transcribed_value") or "")
    explicit_type = _note_error_type(field_annotation.get("annotator_note"))

    blocks_by_id = {block["block_id"]: block for block in real_ocr["blocks"]}
    missing_source_ids = [block_id for block_id in source_ids if block_id not in blocks_by_id]
    aligned_blocks = sorted(
        (blocks_by_id[block_id] for block_id in source_ids if block_id in blocks_by_id),
        key=lambda block: block["reading_order"],
    )
    observed_text = normalize_evidence_text(
        " ".join(block["text"] for block in aligned_blocks)
    )

    if explicit_type:
        error_type = explicit_type
        reason = "annotation adjudication code"
    elif status != "PRESENT":
        error_type = "not_an_ocr_error"
        reason = f"annotation status {status} is not a confirmed present field"
    elif missing_source_ids:
        error_type = "ocr_geometry_evidence"
        reason = "annotation references missing OCR evidence blocks"
    elif not source_ids:
        error_type = "ocr_omission"
        reason = "present field has no aligned OCR evidence"
    elif observed_text != expected_text:
        error_type = "ocr_substitution"
        reason = "aligned OCR text differs from verified transcription"
    else:
        error_type = "not_an_ocr_error"
        reason = "OCR evidence matches verified transcription"

    return {
        "error_type": error_type,
        "field_impacting": error_type != "not_an_ocr_error",
        "reason": reason,
        "expected_text": expected_text,
        "observed_text": observed_text,
        "source_block_ids": source_ids,
        "missing_source_block_ids": missing_source_ids,
    }


def _git_provenance() -> dict[str, Any]:
    try:
        sha = subprocess.run(
            ["git", "-c", f"safe.directory={PROJECT_ROOT.as_posix()}", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                [
                    "git",
                    "-c",
                    f"safe.directory={PROJECT_ROOT.as_posix()}",
                    "status",
                    "--porcelain",
                ],
                cwd=PROJECT_ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return {"git_commit_sha": sha, "git_worktree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit_sha": "unavailable", "git_worktree_dirty": None}


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def _manifest_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _portable_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(resolved)


def _aggregate(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        grouped[str(row[key])][row["error_type"]] += 1
    result = []
    for group in sorted(grouped):
        counts = grouped[group]
        result.append(
            {
                key: group,
                "evaluated_fields": sum(counts.values()),
                "field_impacting_errors": sum(
                    count
                    for error_type, count in counts.items()
                    if error_type != "not_an_ocr_error"
                ),
                "error_counts": {
                    error_type: counts.get(error_type, 0) for error_type in ERROR_TYPES
                },
            }
        )
    return result


def evaluate_field_errors(
    *,
    manifest_path: Path,
    report_path: Path,
    allow_examples: bool = False,
    run_command: str | None = None,
) -> dict[str, Any]:
    """Evaluate field-linked OCR evidence and write a reproducible JSON report."""
    manifest_path = manifest_path.resolve()
    manifest = _load_json(manifest_path)
    required = {"dataset_version", "annotation_qa_state", "example_only", "records"}
    missing = sorted(required - manifest.keys())
    if missing:
        raise ValueError(f"Field evaluation manifest missing: {', '.join(missing)}")
    if manifest["example_only"] and not allow_examples:
        raise ValueError("Example-only field data requires allow_examples=True")
    if not isinstance(manifest["records"], list):
        raise ValueError("Field evaluation manifest records must be an array")

    rows: list[dict[str, Any]] = []
    oracle_available_count = 0
    for record in manifest["records"]:
        annotation_path = _resolve(manifest_path, record["annotation_path"])
        real_ocr_path = _resolve(manifest_path, record["real_ocr_path"])
        annotation = _load_json(annotation_path)
        real_ocr = _load_json(real_ocr_path)
        _validate_annotation(annotation, annotation_path)
        validate_ocr_result(real_ocr)

        if annotation["receipt_id"] != real_ocr["receipt_id"]:
            raise ValueError(f"receipt_id mismatch for {record['test_id']}")
        if annotation["source_ocr_run_id"] != real_ocr["ocr_run_id"]:
            raise ValueError(f"source_ocr_run_id mismatch for {record['test_id']}")
        if annotation["example_only"] and not allow_examples:
            raise ValueError(f"Example annotation is not benchmark evidence: {annotation_path}")

        oracle_path_value = record.get("oracle_ocr_path")
        oracle_available = bool(oracle_path_value)
        if oracle_available:
            oracle_ocr = _load_json(_resolve(manifest_path, oracle_path_value))
            validate_ocr_result(oracle_ocr)
            if oracle_ocr["receipt_id"] != real_ocr["receipt_id"]:
                raise ValueError(f"Oracle receipt_id mismatch for {record['test_id']}")
            oracle_available_count += 1

        for field_name in CANONICAL_FIELDS:
            classification = classify_field_error(annotation["fields"][field_name], real_ocr)
            rows.append(
                {
                    "test_id": record["test_id"],
                    "selection_stratum": record.get("selection_stratum", "unspecified"),
                    "field_name": field_name,
                    "primary_research_field": field_name in PRIMARY_RESEARCH_FIELDS,
                    "annotation_status": annotation["fields"][field_name][
                        "annotation_status"
                    ],
                    "oracle_ocr_available": oracle_available,
                    **classification,
                }
            )

    field_summaries = []
    for field_name in CANONICAL_FIELDS:
        field_rows = [row for row in rows if row["field_name"] == field_name]
        present_count = sum(row["annotation_status"] == "PRESENT" for row in field_rows)
        omission_count = sum(row["error_type"] == "ocr_omission" for row in field_rows)
        field_summaries.append(
            {
                "field_name": field_name,
                "primary_research_field": field_name in PRIMARY_RESEARCH_FIELDS,
                "evaluated_count": len(field_rows),
                "present_count": present_count,
                "field_impacting_error_count": sum(
                    row["field_impacting"] for row in field_rows
                ),
                "ocr_omission_count": omission_count,
                "ocr_omission_rate": (
                    round(omission_count / present_count, 6) if present_count else None
                ),
                "error_counts": {
                    error_type: sum(
                        row["error_type"] == error_type for row in field_rows
                    )
                    for error_type in ERROR_TYPES
                },
            }
        )

    if manifest["example_only"]:
        status = "EXAMPLE_ONLY"
    elif not manifest["records"]:
        status = "WAITING_FOR_VERIFIED_FIELD_ANNOTATIONS"
    else:
        status = (
            "PROVISIONAL"
            if "pending" in manifest["annotation_qa_state"].lower()
            else "COMPLETE"
        )

    provenance = {
        **_git_provenance(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python_version": sys.version.split()[0],
        "ocr_engine": "paddleocr",
        "paddleocr_package_version": _package_version("paddleocr"),
        "paddlepaddle_package_version": _package_version("paddlepaddle"),
        "paddlex_package_version": _package_version("paddlex"),
        "model_family": OCR_MODEL_VERSION,
        "language": OCR_LANGUAGE,
        "dataset_version": manifest["dataset_version"],
        "manifest_sha256": _manifest_digest(manifest_path),
        "annotation_qa_state": manifest["annotation_qa_state"],
        "run_command": run_command or "programmatic evaluate_field_errors",
        "generated_report": _portable_path(report_path),
    }
    report = {
        "report_version": "1.0",
        "status": status,
        "example_only": manifest["example_only"],
        "canonical_fields": list(CANONICAL_FIELDS),
        "primary_research_fields": sorted(PRIMARY_RESEARCH_FIELDS),
        "error_taxonomy": list(ERROR_TYPES),
        "evaluated_receipt_count": len(manifest["records"]),
        "evaluated_field_count": len(rows),
        "oracle_ocr_available_count": oracle_available_count,
        "field_summaries": field_summaries,
        "sample_summaries": _aggregate(rows, "test_id"),
        "quality_stratum_summaries": _aggregate(rows, "selection_stratum"),
        "field_error_rows": rows,
        "provenance": provenance,
        "dependency_note": (
            None
            if manifest["records"]
            else (
                "KIE/Data must provide verified five-field annotations and oracle "
                "OCR evidence; OCR does not fabricate semantic gold labels."
            )
        ),
    }
    report_path = report_path.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return report

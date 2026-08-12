#!/usr/bin/env python3
"""Run positive, negative and cross-record contract tests without test fixtures."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_annotation_ocr import linkage_errors  # noqa: E402


ANNOTATION_SCHEMA = ROOT / "schemas" / "annotation-record.schema.json"
KIE_SCHEMA = ROOT / "schemas" / "kie-result.schema.json"
OCR_SCHEMA = ROOT / "schemas" / "ocr-result.schema.json"
ANNOTATION_EXAMPLE = ROOT / "examples" / "annotation-record.example.json"
KIE_EXAMPLE = ROOT / "examples" / "kie-result.json"
OCR_EXAMPLE = ROOT / "examples" / "ocr-result.json"

AJV_BASE = [
    "npx",
    "--yes",
    "--package=ajv-cli@5",
    "--package=ajv-formats@3",
    "ajv",
    "validate",
    "--spec=draft2020",
    "-c",
    "ajv-formats",
]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def ajv_accepts(schema: Path, data: Path) -> tuple[bool, str]:
    environment = os.environ.copy()
    environment["npm_config_cache"] = str(Path(tempfile.gettempdir()) / "vietreceipt_npm_cache")
    result = subprocess.run(
        [*AJV_BASE, "-s", str(schema), "-d", str(data)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
        check=False,
    )
    return result.returncode == 0, result.stdout


def assert_file_valid(label: str, schema: Path, data: Path) -> None:
    accepted, output = ajv_accepts(schema, data)
    if not accepted:
        raise AssertionError(f"{label} should be valid:\n{output}")


def assert_record(
    label: str,
    schema: Path,
    record: dict[str, Any],
    expected_valid: bool,
) -> None:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="utf-8", delete=False
    ) as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        path = Path(handle.name)

    try:
        accepted, output = ajv_accepts(schema, path)
    finally:
        path.unlink(missing_ok=True)

    if accepted != expected_valid:
        expectation = "valid" if expected_valid else "invalid"
        raise AssertionError(f"{label} should be {expectation}:\n{output}")


def changed(record: dict[str, Any], mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    mutator(result)
    return result


def set_not_present(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    field = record["fields"][field_name]
    field.update(
        annotation_status="NOT_PRESENT",
        evidence_status="NO_OCR_EVIDENCE",
        transcribed_value=None,
        normalized_value=None,
        source_block_ids=[],
        candidate_values=[],
        annotator_note=None,
    )


def set_unreadable(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    field = record["fields"][field_name]
    field.update(
        annotation_status="UNREADABLE",
        evidence_status="OCR_LINKED",
        transcribed_value=None,
        normalized_value=None,
        candidate_values=[],
        annotator_note="The image region is present but unreadable.",
    )


def set_ambiguous(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    field = record["fields"][field_name]
    field.update(
        annotation_status="AMBIGUOUS",
        evidence_status="OCR_LINKED",
        normalized_value=None,
        candidate_values=["WINMART", "WIN MART"],
        annotator_note="Two canonical readings remain plausible.",
    )


def set_unknown(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    field = record["fields"][field_name]
    field.update(
        annotation_status="UNKNOWN",
        evidence_status="NO_OCR_EVIDENCE",
        transcribed_value=None,
        normalized_value=None,
        source_block_ids=[],
        candidate_values=[],
        annotator_note="No reliable conclusion can be reached.",
    )


def set_ocr_omission(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    field = record["fields"][field_name]
    field.update(
        evidence_status="OCR_OMISSION",
        source_block_ids=[],
        annotator_note="OCR_OMISSION: value read directly from the image.",
    )


def main() -> int:
    annotation = read_json(ANNOTATION_EXAMPLE)
    kie = read_json(KIE_EXAMPLE)
    ocr = read_json(OCR_EXAMPLE)

    assert_file_valid("OCR example", OCR_SCHEMA, OCR_EXAMPLE)
    assert_file_valid("KIE example", KIE_SCHEMA, KIE_EXAMPLE)
    assert_file_valid("annotation example", ANNOTATION_SCHEMA, ANNOTATION_EXAMPLE)

    positive_annotations = [
        ("PRESENT + OCR_OMISSION", changed(annotation, set_ocr_omission)),
        ("NOT_PRESENT", changed(annotation, set_not_present)),
        ("UNREADABLE", changed(annotation, set_unreadable)),
        ("AMBIGUOUS", changed(annotation, set_ambiguous)),
        ("UNKNOWN", changed(annotation, set_unknown)),
    ]
    for label, record in positive_annotations:
        assert_record(label, ANNOTATION_SCHEMA, record, True)

    invalid_annotations: list[tuple[str, dict[str, Any]]] = []

    invalid_annotations.append((
        "PRESENT missing transcription",
        changed(annotation, lambda x: x["fields"]["merchant_name"].update(transcribed_value=None)),
    ))
    invalid_annotations.append((
        "PRESENT missing normalized value",
        changed(annotation, lambda x: x["fields"]["merchant_name"].update(normalized_value=None)),
    ))
    invalid_annotations.append((
        "PRESENT has candidate values",
        changed(annotation, lambda x: x["fields"]["merchant_name"].update(candidate_values=["WIN MART"])),
    ))

    not_present_with_text = changed(annotation, set_not_present)
    not_present_with_text["fields"]["merchant_name"]["transcribed_value"] = "WINMART+"
    invalid_annotations.append(("NOT_PRESENT has transcription", not_present_with_text))

    not_present_with_block = changed(annotation, set_not_present)
    not_present_with_block["fields"]["merchant_name"]["source_block_ids"] = ["block_0"]
    invalid_annotations.append(("NOT_PRESENT has source block", not_present_with_block))

    unreadable_without_note = changed(annotation, set_unreadable)
    unreadable_without_note["fields"]["merchant_name"]["annotator_note"] = None
    invalid_annotations.append(("UNREADABLE missing note", unreadable_without_note))

    ambiguous_without_candidates = changed(annotation, set_ambiguous)
    ambiguous_without_candidates["fields"]["merchant_name"]["candidate_values"] = []
    invalid_annotations.append(("AMBIGUOUS missing candidates", ambiguous_without_candidates))

    ambiguous_without_note = changed(annotation, set_ambiguous)
    ambiguous_without_note["fields"]["merchant_name"]["annotator_note"] = None
    invalid_annotations.append(("AMBIGUOUS missing note", ambiguous_without_note))

    unknown_without_note = changed(annotation, set_unknown)
    unknown_without_note["fields"]["merchant_name"]["annotator_note"] = None
    invalid_annotations.append(("UNKNOWN missing note", unknown_without_note))

    invalid_annotations.append((
        "actual record missing timestamp",
        changed(annotation, lambda x: x.update(example_only=False, annotated_at=None)),
    ))
    invalid_annotations.append((
        "total_amount normalized as string",
        changed(annotation, lambda x: x["fields"]["total_amount"].update(normalized_value="325000")),
    ))
    invalid_annotations.append((
        "invoice_id normalized as integer",
        changed(annotation, lambda x: x["fields"]["invoice_id"].update(normalized_value=1238)),
    ))

    omission_with_block = changed(annotation, set_ocr_omission)
    omission_with_block["fields"]["merchant_name"]["source_block_ids"] = ["block_0"]
    invalid_annotations.append(("OCR_OMISSION has source block", omission_with_block))

    invalid_annotations.append((
        "OCR_LINKED has no source block",
        changed(annotation, lambda x: x["fields"]["merchant_name"].update(source_block_ids=[])),
    ))

    for label, record in invalid_annotations:
        assert_record(label, ANNOTATION_SCHEMA, record, False)

    kie_without_source = changed(
        kie, lambda x: x["fields"]["merchant_name"].update(source_block_ids=[])
    )
    assert_record("KIE PRESENT missing source block", KIE_SCHEMA, kie_without_source, False)

    kie_without_reason = changed(
        kie, lambda x: x["fields"]["invoice_id"].update(review_reasons=[])
    )
    assert_record("KIE review flag missing reason", KIE_SCHEMA, kie_without_reason, False)

    if linkage_errors(annotation, ocr):
        raise AssertionError("linked annotation example should match OCR example")

    unknown_block = changed(
        annotation,
        lambda x: x["fields"]["merchant_address"].update(source_block_ids=["block_missing"]),
    )
    assert_record("unknown block remains shape-valid", ANNOTATION_SCHEMA, unknown_block, True)
    if not linkage_errors(unknown_block, ocr):
        raise AssertionError("cross-record validator accepted an unknown source block")

    wrong_receipt = changed(annotation, lambda x: x.update(receipt_id="00000000-0000-4000-8000-000000000099"))
    if not linkage_errors(wrong_receipt, ocr):
        raise AssertionError("cross-record validator accepted a mismatched receipt_id")

    wrong_run = changed(annotation, lambda x: x.update(source_ocr_run_id="00000000-0000-4000-8000-000000000098"))
    if not linkage_errors(wrong_run, ocr):
        raise AssertionError("cross-record validator accepted a mismatched OCR run")

    print("PASS: 8 positive schema examples")
    print(f"PASS: {len(invalid_annotations) + 2} negative schema cases rejected")
    print("PASS: cross-record receipt, OCR run and block linkage checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

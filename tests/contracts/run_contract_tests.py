#!/usr/bin/env python3
"""Run VietReceipt positive, negative and cross-record contract tests."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:
    print(
        "Missing contract dependency. Run: "
        "python3 -m pip install -r requirements-contracts.txt",
        file=sys.stderr,
    )
    raise SystemExit(2)


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_annotation_ocr import linkage_errors  # noqa: E402


ANNOTATION_SCHEMA = ROOT / "schemas" / "annotation-record.schema.json"
KIE_SCHEMA = ROOT / "schemas" / "kie-result.schema.json"
OCR_SCHEMA = ROOT / "schemas" / "ocr-result.schema.json"
ANNOTATION_EXAMPLE = ROOT / "examples" / "annotation-record.example.json"
KIE_EXAMPLE = ROOT / "examples" / "kie-result.json"
OCR_EXAMPLE = ROOT / "examples" / "ocr-result.json"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_validator(schema_path: Path) -> Draft202012Validator:
    schema = read_json(schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


VALIDATORS = {
    ANNOTATION_SCHEMA: build_validator(ANNOTATION_SCHEMA),
    KIE_SCHEMA: build_validator(KIE_SCHEMA),
    OCR_SCHEMA: build_validator(OCR_SCHEMA),
}


def validation_messages(schema: Path, record: dict[str, Any]) -> list[str]:
    errors = sorted(
        VALIDATORS[schema].iter_errors(record),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def assert_record(
    label: str,
    schema: Path,
    record: dict[str, Any],
    expected_valid: bool,
) -> None:
    errors = validation_messages(schema, record)
    accepted = not errors
    if accepted != expected_valid:
        expectation = "valid" if expected_valid else "invalid"
        details = "\n".join(errors) or "record was accepted"
        raise AssertionError(f"{label} should be {expectation}:\n{details}")


def changed(record: dict[str, Any], mutator: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    result = copy.deepcopy(record)
    mutator(result)
    return result


def set_not_present(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    record["fields"][field_name].update(
        annotation_status="NOT_PRESENT",
        transcribed_value=None,
        normalized_value=None,
        source_block_ids=[],
        candidate_values=[],
        annotator_note=None,
    )


def set_unreadable(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    record["fields"][field_name].update(
        annotation_status="UNREADABLE",
        transcribed_value=None,
        normalized_value=None,
        candidate_values=[],
        annotator_note="The image region is present but unreadable.",
    )


def set_ambiguous(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    record["fields"][field_name].update(
        annotation_status="AMBIGUOUS",
        normalized_value=None,
        candidate_values=["WINMART", "WIN MART"],
        annotator_note="Two canonical readings remain plausible.",
    )


def set_unknown(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    record["fields"][field_name].update(
        annotation_status="UNKNOWN",
        transcribed_value=None,
        normalized_value=None,
        source_block_ids=[],
        candidate_values=[],
        annotator_note="No reliable conclusion can be reached.",
    )


def set_ocr_omission(record: dict[str, Any], field_name: str = "merchant_name") -> None:
    record["fields"][field_name].update(
        source_block_ids=[],
        annotator_note="OCR_OMISSION",
    )


def set_kie_unknown(record: dict[str, Any], predicted_value: str | None) -> None:
    record["fields"]["merchant_name"].update(
        raw_text=None,
        predicted_value=predicted_value,
        normalized_value=None,
        normalization=None,
        value_status="UNKNOWN",
        confidence=0.0,
        machine_needs_review=True,
        review_reasons=["NO_CANDIDATE"],
        review_policy_version="kie-review-policy-v1.1",
        source_block_ids=[],
    )


def main() -> int:
    annotation = read_json(ANNOTATION_EXAMPLE)
    kie = read_json(KIE_EXAMPLE)
    ocr = read_json(OCR_EXAMPLE)

    assert_record("OCR example", OCR_SCHEMA, ocr, True)
    assert_record("KIE example", KIE_SCHEMA, kie, True)
    assert_record("annotation example", ANNOTATION_SCHEMA, annotation, True)

    positive_annotations = [
        ("PRESENT + OCR_OMISSION", changed(annotation, set_ocr_omission)),
        ("NOT_PRESENT", changed(annotation, set_not_present)),
        ("UNREADABLE", changed(annotation, set_unreadable)),
        ("AMBIGUOUS", changed(annotation, set_ambiguous)),
        ("UNKNOWN", changed(annotation, set_unknown)),
    ]
    for label, record in positive_annotations:
        assert_record(label, ANNOTATION_SCHEMA, record, True)

    invalid_annotations: list[tuple[str, dict[str, Any]]] = [
        (
            "PRESENT missing transcription",
            changed(annotation, lambda x: x["fields"]["merchant_name"].update(transcribed_value=None)),
        ),
        (
            "PRESENT missing normalized value",
            changed(annotation, lambda x: x["fields"]["merchant_name"].update(normalized_value=None)),
        ),
        (
            "PRESENT has candidate values",
            changed(annotation, lambda x: x["fields"]["merchant_name"].update(candidate_values=["WIN MART"])),
        ),
        (
            "PRESENT missing source without OCR_OMISSION",
            changed(annotation, lambda x: x["fields"]["merchant_name"].update(source_block_ids=[])),
        ),
        (
            "actual record missing timestamp",
            changed(annotation, lambda x: x.update(example_only=False, annotated_at=None)),
        ),
        (
            "total_amount normalized as string",
            changed(annotation, lambda x: x["fields"]["total_amount"].update(normalized_value="325000")),
        ),
        (
            "invoice_id normalized as integer",
            changed(annotation, lambda x: x["fields"]["invoice_id"].update(normalized_value=1238)),
        ),
    ]

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

    omission_with_block = changed(annotation, set_ocr_omission)
    omission_with_block["fields"]["merchant_name"]["source_block_ids"] = ["block_0"]
    invalid_annotations.append(("OCR_OMISSION has source block", omission_with_block))

    for label, record in invalid_annotations:
        assert_record(label, ANNOTATION_SCHEMA, record, False)

    invalid_kie: list[tuple[str, dict[str, Any]]] = [
        (
            "KIE PRESENT missing source block",
            changed(kie, lambda x: x["fields"]["merchant_name"].update(source_block_ids=[])),
        ),
        (
            "KIE review flag missing reason",
            changed(kie, lambda x: x["fields"]["invoice_id"].update(review_reasons=[])),
        ),
        (
            "KIE review flag missing policy version",
            changed(kie, lambda x: x["fields"]["invoice_id"].pop("review_policy_version")),
        ),
        (
            "KIE PRESENT missing normalization provenance",
            changed(kie, lambda x: x["fields"]["merchant_name"].pop("normalization")),
        ),
        (
            "KIE normalization missing rule",
            changed(kie, lambda x: x["fields"]["merchant_name"]["normalization"].pop("rule")),
        ),
        (
            "KIE source block with null raw_text",
            changed(kie, lambda x: x["fields"]["merchant_name"].update(raw_text=None)),
        ),
        (
            "KIE missing created_at",
            changed(kie, lambda x: x.pop("created_at")),
        ),
        (
            "KIE unapproved review reason",
            changed(kie, lambda x: x["fields"]["invoice_id"].update(review_reasons=["UNKNOWN"])),
        ),
        (
            "KIE UNKNOWN with predicted value",
            changed(kie, lambda x: set_kie_unknown(x, "invented candidate")),
        ),
    ]
    for label, record in invalid_kie:
        assert_record(label, KIE_SCHEMA, record, False)

    valid_unknown = changed(kie, lambda x: set_kie_unknown(x, None))
    assert_record("KIE UNKNOWN without prediction", KIE_SCHEMA, valid_unknown, True)

    if linkage_errors(annotation, ocr):
        raise AssertionError("linked annotation example should match OCR example")

    unknown_block = changed(
        annotation,
        lambda x: x["fields"]["merchant_address"].update(source_block_ids=["block_missing"]),
    )
    assert_record("unknown block remains shape-valid", ANNOTATION_SCHEMA, unknown_block, True)
    if not linkage_errors(unknown_block, ocr):
        raise AssertionError("cross-record validator accepted an unknown source block")

    wrong_receipt = changed(
        annotation,
        lambda x: x.update(receipt_id="00000000-0000-4000-8000-000000000099"),
    )
    if not linkage_errors(wrong_receipt, ocr):
        raise AssertionError("cross-record validator accepted a mismatched receipt_id")

    wrong_run = changed(
        annotation,
        lambda x: x.update(source_ocr_run_id="00000000-0000-4000-8000-000000000098"),
    )
    if not linkage_errors(wrong_run, ocr):
        raise AssertionError("cross-record validator accepted a mismatched OCR run")

    print("PASS: JSON Schemas are valid Draft 2020-12 schemas")
    print("PASS: 9 positive schema cases")
    print(f"PASS: {len(invalid_annotations) + len(invalid_kie)} negative schema cases rejected")
    print("PASS: cross-record receipt, OCR run and block linkage checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

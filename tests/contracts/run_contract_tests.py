#!/usr/bin/env python3
"""Run VietReceipt positive, negative and cross-record contract tests."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

try:
    from jsonschema import Draft202012Validator, FormatChecker
    from openapi_spec_validator import validate as validate_openapi
    import yaml
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
OPENAPI_SPEC = ROOT / "openapi" / "openapi.yaml"
STATE_MACHINE = ROOT / "docs" / "receipt-state-machine.md"

CANONICAL_RECEIPT_STATUSES = {
    "UPLOADED",
    "PROCESSING",
    "NEEDS_REVIEW",
    "VERIFIED",
    "FAILED",
}
CANONICAL_FIELD_NAMES = {
    "merchant_name",
    "receipt_date",
    "total_amount",
    "invoice_id",
    "merchant_address",
}
FIELD_SCHEMA_BY_NAME = {
    "merchant_name": "MerchantNameField",
    "receipt_date": "ReceiptDateField",
    "total_amount": "TotalAmountField",
    "invoice_id": "InvoiceIdField",
    "merchant_address": "MerchantAddressField",
}
FIELD_VALUE_SCHEMA_BY_NAME = {
    "merchant_name": "MerchantNameValue",
    "receipt_date": "ReceiptDateValue",
    "total_amount": "TotalAmountValue",
    "invoice_id": "InvoiceIdValue",
    "merchant_address": "MerchantAddressValue",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def openapi_component_errors(
    openapi: dict[str, Any],
    schema_name: str,
    instance: Any,
) -> list[str]:
    root_schema = copy.deepcopy(openapi)
    root_schema["$ref"] = f"#/components/schemas/{schema_name}"
    validator = Draft202012Validator(root_schema, format_checker=FormatChecker())
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: [str(part) for part in error.absolute_path],
    )
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
        f"{error.message}"
        for error in errors
    ]


def assert_openapi_component(
    label: str,
    openapi: dict[str, Any],
    schema_name: str,
    instance: Any,
    expected_valid: bool,
) -> None:
    errors = openapi_component_errors(openapi, schema_name, instance)
    accepted = not errors
    if accepted != expected_valid:
        expectation = "valid" if expected_valid else "invalid"
        details = "\n".join(errors) or "instance was accepted"
        raise AssertionError(f"{label} should be {expectation}:\n{details}")


def public_field(field_name: str, value: str | int) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "ocr_run_id": "00000000-0000-4000-8000-000000000001",
        "kie_run_id": "00000000-0000-4000-8000-000000000002",
        "raw_text": str(value),
        "predicted_value": str(value),
        "normalized_value": value,
        "normalization": {"rule": "contract_test", "version": "1.0"},
        "value_status": "PRESENT",
        "corrected_value": None,
        "corrected_status": None,
        "has_correction": False,
        "effective_value": value,
        "effective_status": "PRESENT",
        "confidence": 0.9,
        "machine_needs_review": False,
        "effective_needs_review": False,
        "review_reasons": [],
        "review_policy_version": None,
        "source_block_ids": ["block_0"],
        "verified": False,
        "updated_at": "2026-08-10T08:30:00Z",
    }


def canonical_public_fields() -> dict[str, Any]:
    return {
        "merchant_name": public_field("merchant_name", "WINMART"),
        "receipt_date": public_field("receipt_date", "2026-08-12"),
        "total_amount": public_field("total_amount", 325000),
        "invoice_id": public_field("invoice_id", "000123"),
        "merchant_address": public_field("merchant_address", "1 Test Street"),
    }


def assert_integration_consistency(openapi: dict[str, Any], kie_schema: dict[str, Any]) -> None:
    validate_openapi(openapi)

    schemas = openapi["components"]["schemas"]
    paths = openapi["paths"]

    if set(schemas["ReceiptStatus"]["enum"]) != CANONICAL_RECEIPT_STATUSES:
        raise AssertionError("OpenAPI ReceiptStatus is not the canonical five-state set")

    state_section = STATE_MACHINE.read_text(encoding="utf-8").split("## Valid transitions", 1)[0]
    documented_states = set(re.findall(r"^\| `([A-Z_]+)` \|", state_section, flags=re.MULTILINE))
    if documented_states != CANONICAL_RECEIPT_STATUSES:
        raise AssertionError("state-machine states differ from OpenAPI ReceiptStatus")

    kie_reasons = set(kie_schema["$defs"]["reviewReason"]["enum"])
    if set(schemas["ReviewReason"]["enum"]) != kie_reasons:
        raise AssertionError("OpenAPI ReviewReason differs from KIE reviewReason")

    if set(schemas["FieldName"]["enum"]) != CANONICAL_FIELD_NAMES:
        raise AssertionError("OpenAPI FieldName differs from the five canonical names")

    canonical_properties = schemas["CanonicalExtractedFields"]["properties"]
    for field_name, schema_name in FIELD_SCHEMA_BY_NAME.items():
        expected_ref = f"#/components/schemas/{schema_name}"
        if canonical_properties[field_name].get("$ref") != expected_ref:
            raise AssertionError(f"{field_name} is not pinned to {schema_name}")
        typed_overlay = schemas[schema_name]["allOf"][1]["properties"]
        if typed_overlay["field_name"].get("const") != field_name:
            raise AssertionError(f"{schema_name} does not lock embedded field_name")

    if any(path.endswith("/process") for path in paths):
        raise AssertionError("OpenAPI must not expose a public process endpoint")

    correction_path = "/receipts/{receipt_id}/fields/{field_name}/correction"
    correction_operation = paths.get(correction_path, {}).get("patch")
    if correction_operation is None:
        raise AssertionError("canonical field-name correction endpoint is missing")
    if "delete" in paths[correction_path]:
        raise AssertionError("correction clear must not use a second DELETE contract")

    correction_request = schemas["FieldCorrectionRequest"]
    correction_refs = {entry["$ref"] for entry in correction_request["oneOf"]}
    expected_refs = {
        "#/components/schemas/ApplyFieldCorrectionRequest",
        "#/components/schemas/ClearFieldCorrectionRequest",
    }
    if correction_refs != expected_refs:
        raise AssertionError("correction request must expose exactly APPLY and CLEAR shapes")
    operations = {
        schemas["ApplyFieldCorrectionRequest"]["properties"]["operation"]["const"],
        schemas["ClearFieldCorrectionRequest"]["properties"]["operation"]["const"],
    }
    if operations != {"APPLY", "CLEAR"}:
        raise AssertionError("correction operation values differ from APPLY/CLEAR")
    for request_name in ("ApplyFieldCorrectionRequest", "ClearFieldCorrectionRequest"):
        if "expected_updated_at" not in schemas[request_name]["required"]:
            raise AssertionError(f"{request_name} lacks optimistic concurrency")

    correction_value_mapping = schemas["ApplyFieldCorrectionRequest"].get(
        "x-field-value-schema-by-field-name",
        {},
    )
    expected_value_mapping = {
        field_name: f"#/components/schemas/{schema_name}"
        for field_name, schema_name in FIELD_VALUE_SCHEMA_BY_NAME.items()
    }
    if correction_value_mapping != expected_value_mapping:
        raise AssertionError("correction path/value schema mapping is incomplete or inconsistent")

    correction_response = correction_operation["responses"]["200"]["content"]["application/json"]["schema"]
    if correction_response.get("$ref") != "#/components/schemas/CanonicalExtractedField":
        raise AssertionError("correction response is not a canonical typed field")

    retry = paths["/receipts/{receipt_id}/retry"]["post"]
    retry_schema = retry["responses"]["202"]["content"]["application/json"]["schema"]
    if retry_schema.get("$ref") != "#/components/schemas/RetryAccepted":
        raise AssertionError("retry 202 still implies PROCESSING instead of scheduling acceptance")
    if "status" in schemas["RetryAccepted"].get("properties", {}):
        raise AssertionError("RetryAccepted must not claim a PROCESSING status before worker claim")

    error_stages = set(schemas["ProcessingError"]["properties"]["stage"]["enum"])
    if "SCHEDULING" not in error_stages:
        raise AssertionError("ProcessingError does not represent scheduling failure")
    if "SCHEDULING" in set(schemas["ProcessingStage"]["enum"]):
        raise AssertionError("SCHEDULING must not become a PROCESSING progress stage")

    state_text = STATE_MACHINE.read_text(encoding="utf-8")
    required_state_fragments = (
        "UPLOADED --> PROCESSING: Worker claims processing attempt",
        "UPLOADED --> FAILED: scheduling failed",
        "FAILED --> PROCESSING: Worker claims retry attempt",
    )
    for fragment in required_state_fragments:
        if fragment not in state_text:
            raise AssertionError(f"state-machine timing/failure semantics missing: {fragment}")

    fields_response = paths["/receipts/{receipt_id}/fields"]["get"]["responses"]["200"]
    fields_schema = fields_response["content"]["application/json"]["schema"]
    if fields_schema.get("$ref") != "#/components/schemas/CanonicalExtractedFields":
        raise AssertionError("fields response is not keyed by canonical field name")

    verify = paths["/receipts/{receipt_id}/verify"]["post"]
    verify_schema = verify["requestBody"]["content"]["application/json"]["schema"]
    if verify_schema.get("$ref") != "#/components/schemas/VerifyReceiptRequest":
        raise AssertionError("verify endpoint lacks the canonical request body")
    if "expected_updated_at" not in schemas["VerifyReceiptRequest"]["required"]:
        raise AssertionError("verify request lacks optimistic concurrency")


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
    openapi = read_yaml(OPENAPI_SPEC)

    assert_integration_consistency(openapi, read_json(KIE_SCHEMA))

    public_fields = canonical_public_fields()
    assert_openapi_component(
        "canonical public fields",
        openapi,
        "CanonicalExtractedFields",
        public_fields,
        True,
    )

    invalid_public_fields: list[tuple[str, dict[str, Any]]] = [
        (
            "public total_amount as string",
            changed(
                public_fields,
                lambda x: x["total_amount"].update(
                    normalized_value="325000",
                    effective_value="325000",
                ),
            ),
        ),
        (
            "public receipt_date non-ISO",
            changed(
                public_fields,
                lambda x: x["receipt_date"].update(
                    normalized_value="08/12/2026",
                    effective_value="08/12/2026",
                ),
            ),
        ),
        (
            "public invoice_id as integer",
            changed(
                public_fields,
                lambda x: x["invoice_id"].update(
                    normalized_value=123456,
                    effective_value=123456,
                ),
            ),
        ),
        (
            "public merchant_name as integer",
            changed(
                public_fields,
                lambda x: x["merchant_name"].update(
                    normalized_value=123,
                    effective_value=123,
                ),
            ),
        ),
        (
            "public merchant_address as integer",
            changed(
                public_fields,
                lambda x: x["merchant_address"].update(
                    normalized_value=123,
                    effective_value=123,
                ),
            ),
        ),
        (
            "public outer key / embedded field_name mismatch",
            changed(
                public_fields,
                lambda x: x["merchant_name"].update(field_name="total_amount"),
            ),
        ),
    ]
    for label, record in invalid_public_fields:
        assert_openapi_component(
            label,
            openapi,
            "CanonicalExtractedFields",
            record,
            False,
        )

    correction_cases = [
        ("total_amount string correction", "total_amount", "325000", False),
        ("total_amount integer correction", "total_amount", 325000, True),
        ("receipt_date non-ISO correction", "receipt_date", "08/12/2026", False),
        ("receipt_date ISO correction", "receipt_date", "2026-08-12", True),
        ("invoice_id integer correction", "invoice_id", 123456, False),
        ("invoice_id string correction", "invoice_id", "000123", True),
        ("merchant_name integer correction", "merchant_name", 123, False),
        ("merchant_address integer correction", "merchant_address", 123, False),
    ]
    for label, field_name, value, expected_valid in correction_cases:
        assert_openapi_component(
            label,
            openapi,
            FIELD_VALUE_SCHEMA_BY_NAME[field_name],
            value,
            expected_valid,
        )

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

    duplicate_block = changed(
        ocr,
        lambda x: x["blocks"][1].update(block_id=x["blocks"][0]["block_id"]),
    )
    if not linkage_errors(annotation, duplicate_block):
        raise AssertionError("OCR validator accepted duplicate block_id within one OCR run")

    duplicate_order = changed(
        ocr,
        lambda x: x["blocks"][1].update(reading_order=x["blocks"][0]["reading_order"]),
    )
    if not linkage_errors(annotation, duplicate_order):
        raise AssertionError("OCR validator accepted duplicate reading_order within one OCR run")

    non_zero_based_order = changed(
        ocr,
        lambda x: [block.update(reading_order=index + 1) for index, block in enumerate(x["blocks"])],
    )
    if not linkage_errors(annotation, non_zero_based_order):
        raise AssertionError("OCR validator accepted non-zero-based reading_order")

    print("PASS: JSON Schemas are valid Draft 2020-12 schemas")
    print("PASS: OpenAPI 3.1 document is valid")
    print("PASS: OpenAPI, state machine, KIE reasons and canonical fields are consistent")
    print("PASS: field-specific public API types and embedded field_name invariants")
    print("PASS: correction path/value types reject mismatches")
    print("PASS: scheduling, retry and queue-failure semantics are consistent")
    print("PASS: correction APPLY/CLEAR and verification concurrency contracts are consistent")
    print("PASS: 9 positive schema cases")
    print(f"PASS: {len(invalid_annotations) + len(invalid_kie)} negative schema cases rejected")
    print("PASS: cross-record receipt, OCR run and block linkage checks")
    print("PASS: OCR block_id and zero-based reading_order are unique within one OCR run")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

from dataclasses import replace
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "infra"
    / "scripts"
    / "processing-smoke.py"
)


def _load_processing_smoke_module():
    spec = spec_from_file_location(
        "processing_smoke_under_test",
        SCRIPT_PATH,
    )
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_processing_smoke_is_import_safe():
    module = _load_processing_smoke_module()

    assert callable(module.main)


def _successful_evidence(module):
    receipt_id = "00000000-0000-0000-0000-000000000001"
    attempt_id = "00000000-0000-0000-0000-000000000002"
    ocr_run_id = "00000000-0000-0000-0000-000000000003"
    kie_run_id = "00000000-0000-0000-0000-000000000004"
    field_names = (
        "merchant_name",
        "receipt_date",
        "total_amount",
        "invoice_id",
        "merchant_address",
    )
    fields = tuple(
        module.FieldEvidence(
            field_name=field_name,
            receipt_id=receipt_id,
            ocr_run_id=ocr_run_id,
            kie_run_id=kie_run_id,
        )
        for field_name in field_names
    )
    return module.ProcessingEvidence(
        receipt_id=receipt_id,
        receipt_status="NEEDS_REVIEW",
        receipt_error=None,
        latest_ocr_run_id=ocr_run_id,
        latest_kie_run_id=kie_run_id,
        attempt_id=attempt_id,
        attempt_status="SUCCEEDED",
        attempt_stage="PERSISTING",
        attempt_ocr_run_id=ocr_run_id,
        attempt_kie_run_id=kie_run_id,
        attempt_error=None,
        ocr_record_id=ocr_run_id,
        ocr_attempt_id=attempt_id,
        ocr_receipt_id=receipt_id,
        kie_record_id=kie_run_id,
        kie_attempt_id=attempt_id,
        kie_receipt_id=receipt_id,
        kie_source_ocr_run_id=ocr_run_id,
        fields=fields,
    )


def test_success_evidence_requires_complete_canonical_linkage():
    module = _load_processing_smoke_module()
    evidence = _successful_evidence(module)

    assert module.validation_errors(evidence) == ()


def test_success_evidence_rejects_missing_canonical_field():
    module = _load_processing_smoke_module()
    evidence = _successful_evidence(module)
    evidence = replace(evidence, fields=evidence.fields[:-1])

    assert module.validation_errors(evidence) == (
        "canonical_field_count=4 expected=5",
        "canonical_fields missing=merchant_address unexpected=-",
    )


def test_success_evidence_rejects_field_run_mismatch():
    module = _load_processing_smoke_module()
    evidence = _successful_evidence(module)
    mismatched_field = replace(
        evidence.fields[0],
        kie_run_id="00000000-0000-0000-0000-000000000099",
    )
    evidence = replace(
        evidence,
        fields=(mismatched_field, *evidence.fields[1:]),
    )

    assert module.validation_errors(evidence) == (
        "extracted_fields linkage does not match receipt/OCR/KIE runs",
    )


def test_success_output_contains_review_evidence():
    module = _load_processing_smoke_module()
    evidence = _successful_evidence(module)

    assert module.format_success_lines(evidence) == (
        "PASS processing E2E",
        "receipt_id=00000000-0000-0000-0000-000000000001",
        "attempt_id=00000000-0000-0000-0000-000000000002",
        "ocr_run_id=00000000-0000-0000-0000-000000000003",
        "kie_run_id=00000000-0000-0000-0000-000000000004",
        "status=NEEDS_REVIEW",
        "attempt_status=SUCCEEDED",
        "attempt_stage=PERSISTING",
        "latest_ocr_run_id=00000000-0000-0000-0000-000000000003",
        "latest_kie_run_id=00000000-0000-0000-0000-000000000004",
        "canonical_field_count=5",
    )


def test_failure_output_omits_raw_error_message():
    module = _load_processing_smoke_module()
    evidence = replace(
        _successful_evidence(module),
        receipt_status="FAILED",
        attempt_status="FAILED",
        attempt_stage="OCR",
        attempt_error={
            "stage": "OCR",
            "code": "OCR_FAILED",
            "message": "secret-token-must-not-appear",
            "retryable": False,
        },
    )

    output = "\n".join(
        module.format_failure_lines(evidence, reason="receipt failed")
    )

    assert "error_stage=OCR" in output
    assert "error_code=OCR_FAILED" in output
    assert "error_retryable=False" in output
    assert "secret-token-must-not-appear" not in output


def test_failure_output_uses_receipt_error_without_attempt():
    module = _load_processing_smoke_module()
    evidence = module.build_evidence(
        "00000000-0000-0000-0000-000000000001",
        {
            "receipt_status": "FAILED",
            "receipt_error": {
                "stage": "SCHEDULING",
                "code": "PROCESSING_SCHEDULING_FAILED",
                "message": "secret-token-must-not-appear",
                "retryable": True,
            },
        },
        (),
    )

    output = "\n".join(
        module.format_failure_lines(evidence, reason="receipt failed")
    )

    assert "attempt_id=-" in output
    assert "error_stage=SCHEDULING" in output
    assert "error_code=PROCESSING_SCHEDULING_FAILED" in output
    assert "error_retryable=True" in output
    assert "secret-token-must-not-appear" not in output


def test_build_evidence_maps_database_rows_and_uuid_values():
    module = _load_processing_smoke_module()
    expected = _successful_evidence(module)
    receipt_row = {
        "receipt_status": expected.receipt_status,
        "receipt_error": expected.receipt_error,
        "latest_ocr_run_id": expected.latest_ocr_run_id,
        "latest_kie_run_id": expected.latest_kie_run_id,
        "attempt_id": expected.attempt_id,
        "attempt_status": expected.attempt_status,
        "attempt_stage": expected.attempt_stage,
        "attempt_ocr_run_id": expected.attempt_ocr_run_id,
        "attempt_kie_run_id": expected.attempt_kie_run_id,
        "attempt_error": expected.attempt_error,
        "ocr_record_id": expected.ocr_record_id,
        "ocr_attempt_id": expected.ocr_attempt_id,
        "ocr_receipt_id": expected.ocr_receipt_id,
        "kie_record_id": expected.kie_record_id,
        "kie_attempt_id": expected.kie_attempt_id,
        "kie_receipt_id": expected.kie_receipt_id,
        "kie_source_ocr_run_id": expected.kie_source_ocr_run_id,
    }
    field_rows = [
        {
            "field_name": field.field_name,
            "receipt_id": field.receipt_id,
            "ocr_run_id": field.ocr_run_id,
            "kie_run_id": field.kie_run_id,
        }
        for field in expected.fields
    ]

    actual = module.build_evidence(
        expected.receipt_id,
        receipt_row,
        field_rows,
    )

    assert actual == expected

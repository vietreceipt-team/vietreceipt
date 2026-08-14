from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.enums import FieldName, ValueStatus
from backend.app.domain.errors import InvalidFieldValue
from backend.app.domain.models import (
    ExtractedField,
    NormalizationProvenance,
)
from backend.app.domain.validation import (
    is_resolved_status,
    validate_canonical_value,
)


NOW = datetime(2026, 8, 14, 5, 0, tzinfo=timezone.utc)
RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
OCR_RUN_ID = UUID("00000000-0000-4000-8000-000000000002")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000003")


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (FieldName.MERCHANT_NAME, "WINMART"),
        (FieldName.RECEIPT_DATE, "2026-08-14"),
        (FieldName.TOTAL_AMOUNT, 325000),
        (FieldName.INVOICE_ID, "000123"),
        (FieldName.MERCHANT_ADDRESS, "1 Test Street"),
    ],
)
def test_accepts_canonical_present_value(
    field_name: FieldName,
    value: str | int,
) -> None:
    validate_canonical_value(
        field_name,
        ValueStatus.PRESENT,
        value,
    )


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        (FieldName.MERCHANT_NAME, 123),
        (FieldName.RECEIPT_DATE, "14/08/2026"),
        (FieldName.TOTAL_AMOUNT, "325000"),
        (FieldName.INVOICE_ID, 123),
        (FieldName.MERCHANT_ADDRESS, 123),
    ],
)
def test_rejects_invalid_canonical_present_value(
    field_name: FieldName,
    value: str | int,
) -> None:
    with pytest.raises(InvalidFieldValue):
        validate_canonical_value(
            field_name,
            ValueStatus.PRESENT,
            value,
        )


def test_non_present_status_requires_null() -> None:
    with pytest.raises(InvalidFieldValue):
        validate_canonical_value(
            FieldName.TOTAL_AMOUNT,
            ValueStatus.NOT_PRESENT,
            0,
        )


def make_total_field(
    **overrides: object,
) -> ExtractedField:
    data: dict[str, object] = {
        "receipt_id": RECEIPT_ID,
        "field_name": FieldName.TOTAL_AMOUNT,
        "ocr_run_id": OCR_RUN_ID,
        "kie_run_id": KIE_RUN_ID,
        "raw_text": "325.000",
        "predicted_value": "325000",
        "normalized_value": 325000,
        "normalization": NormalizationProvenance(
            rule="vnd_integer",
            version="1.0",
        ),
        "value_status": ValueStatus.PRESENT,
        "corrected_value": None,
        "corrected_status": None,
        "has_correction": False,
        "effective_value": 325000,
        "effective_status": ValueStatus.PRESENT,
        "confidence": 0.95,
        "machine_needs_review": False,
        "effective_needs_review": False,
        "review_reasons": (),
        "review_policy_version": None,
        "source_block_ids": ("block_1",),
        "verified": False,
        "updated_at": NOW,
    }
    data.update(overrides)
    return ExtractedField(**data)


def test_effective_value_cannot_fallback_to_prediction() -> None:
    with pytest.raises(ValidationError):
        make_total_field(
            normalized_value=None,
            value_status=ValueStatus.UNKNOWN,
            effective_value="325000",
            effective_status=ValueStatus.PRESENT,
        )


def test_machine_review_requires_provenance() -> None:
    with pytest.raises(ValidationError):
        make_total_field(
            machine_needs_review=True,
            review_reasons=(),
            review_policy_version=None,
        )


def test_resolved_status_helper() -> None:
    assert is_resolved_status(ValueStatus.PRESENT)
    assert is_resolved_status(ValueStatus.NOT_PRESENT)
    assert is_resolved_status(ValueStatus.UNREADABLE)
    assert not is_resolved_status(ValueStatus.AMBIGUOUS)
    assert not is_resolved_status(ValueStatus.UNKNOWN)

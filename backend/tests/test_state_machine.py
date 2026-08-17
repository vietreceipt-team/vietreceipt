import pytest

from backend.app.domain.enums import (
    ErrorStage,
    FieldName,
    ProcessingStage,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.errors import InvalidReceiptState
from backend.app.domain.state_machine import (
    can_transition,
    ensure_transition_allowed,
)


VALID_TRANSITIONS = [
    (ReceiptStatus.UPLOADED, ReceiptStatus.PROCESSING),
    (ReceiptStatus.UPLOADED, ReceiptStatus.FAILED),
    (ReceiptStatus.PROCESSING, ReceiptStatus.NEEDS_REVIEW),
    (ReceiptStatus.PROCESSING, ReceiptStatus.FAILED),
    (ReceiptStatus.FAILED, ReceiptStatus.PROCESSING),
    (ReceiptStatus.NEEDS_REVIEW, ReceiptStatus.VERIFIED),
]


INVALID_TRANSITIONS = [
    (ReceiptStatus.UPLOADED, ReceiptStatus.VERIFIED),
    (ReceiptStatus.PROCESSING, ReceiptStatus.VERIFIED),
    (ReceiptStatus.NEEDS_REVIEW, ReceiptStatus.PROCESSING),
    (ReceiptStatus.VERIFIED, ReceiptStatus.NEEDS_REVIEW),
    (ReceiptStatus.FAILED, ReceiptStatus.VERIFIED),
    (ReceiptStatus.UPLOADED, ReceiptStatus.UPLOADED),
]


def test_receipt_statuses_match_canonical_contract() -> None:
    assert {status.value for status in ReceiptStatus} == {
        "UPLOADED",
        "PROCESSING",
        "NEEDS_REVIEW",
        "VERIFIED",
        "FAILED",
    }


def test_field_names_match_canonical_contract() -> None:
    assert {field.value for field in FieldName} == {
        "merchant_name",
        "receipt_date",
        "total_amount",
        "invoice_id",
        "merchant_address",
    }


def test_value_statuses_match_canonical_contract() -> None:
    assert {status.value for status in ValueStatus} == {
        "PRESENT",
        "NOT_PRESENT",
        "UNREADABLE",
        "AMBIGUOUS",
        "UNKNOWN",
    }


def test_scheduling_is_error_stage_not_processing_stage() -> None:
    assert ErrorStage.SCHEDULING.value == "SCHEDULING"
    assert "SCHEDULING" not in {stage.value for stage in ProcessingStage}


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    VALID_TRANSITIONS,
)
def test_allows_canonical_transition(
    current_status: ReceiptStatus,
    target_status: ReceiptStatus,
) -> None:
    assert can_transition(current_status, target_status)
    ensure_transition_allowed(current_status, target_status)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    INVALID_TRANSITIONS,
)
def test_rejects_invalid_transition(
    current_status: ReceiptStatus,
    target_status: ReceiptStatus,
) -> None:
    assert not can_transition(current_status, target_status)

    with pytest.raises(InvalidReceiptState) as captured:
        ensure_transition_allowed(current_status, target_status)

    error = captured.value
    assert error.code == "RECEIPT_STATE_CONFLICT"
    assert error.current_status is current_status
    assert error.target_status is target_status
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.models import (
    AuditEvent,
    CorrectionHistory,
    Receipt,
)


NOW = datetime(2026, 8, 14, 3, 30, tzinfo=timezone.utc)
RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
EVENT_ID = UUID("00000000-0000-4000-8000-000000000002")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000003")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000004")


def make_receipt() -> Receipt:
    return Receipt(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=ReceiptStatus.UPLOADED,
        image_width_px=1000,
        image_height_px=1500,
        created_at=NOW,
        updated_at=NOW,
    )


def test_receipt_preserves_measurement_timestamps() -> None:
    receipt = make_receipt()

    assert receipt.created_at == NOW
    assert receipt.updated_at == NOW
    assert receipt.review_started_at is None
    assert receipt.verified_at is None


def test_domain_models_are_immutable() -> None:
    receipt = make_receipt()

    with pytest.raises(ValidationError):
        receipt.status = ReceiptStatus.PROCESSING


def test_domain_models_reject_unknown_properties() -> None:
    with pytest.raises(ValidationError):
        Receipt(
            receipt_id=RECEIPT_ID,
            original_filename="receipt.jpg",
            status=ReceiptStatus.UPLOADED,
            image_width_px=1000,
            image_height_px=1500,
            created_at=NOW,
            updated_at=NOW,
            analytics_score=0.9,
        )


def test_correction_audit_event_preserves_measurement_data() -> None:
    event = AuditEvent(
        event_id=EVENT_ID,
        receipt_id=RECEIPT_ID,
        event_type=AuditEventType.CORRECTION_APPLIED,
        field_name=FieldName.TOTAL_AMOUNT,
        operation=CorrectionOperation.APPLY,
        actor_id=ACTOR_ID,
        occurred_at=NOW,
    )

    assert event.field_name is FieldName.TOTAL_AMOUNT
    assert event.operation is CorrectionOperation.APPLY
    assert event.actor_id == ACTOR_ID
    assert event.occurred_at == NOW


def test_correction_event_rejects_mismatched_operation() -> None:
    with pytest.raises(ValidationError):
        AuditEvent(
            event_id=EVENT_ID,
            receipt_id=RECEIPT_ID,
            event_type=AuditEventType.CORRECTION_CLEARED,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            occurred_at=NOW,
        )


def test_review_started_event_allows_missing_actor() -> None:
    event = AuditEvent(
        event_id=EVENT_ID,
        receipt_id=RECEIPT_ID,
        event_type=AuditEventType.REVIEW_STARTED,
        actor_id=None,
        occurred_at=NOW,
    )

    assert event.actor_id is None
    assert event.field_name is None
    assert event.operation is None


def test_correction_history_is_append_only_record_shape() -> None:
    history = CorrectionHistory(
        correction_id=EVENT_ID,
        receipt_id=RECEIPT_ID,
        field_name=FieldName.TOTAL_AMOUNT,
        operation=CorrectionOperation.APPLY,
        kie_run_id=KIE_RUN_ID,
        old_value=320000,
        new_value=325000,
        old_status=ValueStatus.PRESENT,
        new_status=ValueStatus.PRESENT,
        changed_by=ACTOR_ID,
        changed_at=NOW,
    )

    assert history.old_value == 320000
    assert history.new_value == 325000
    assert history.changed_by == ACTOR_ID
    assert history.changed_at == NOW

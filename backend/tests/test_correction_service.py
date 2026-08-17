import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.errors import (
    InvalidFieldValue,
    InvalidReceiptState,
    StaleUpdate,
)
from backend.app.domain.models import (
    ExtractedField,
    NormalizationProvenance,
    Receipt,
)
from backend.app.services.correction_service import (
    CorrectionService,
)
from backend.tests.fakes import FakeUnitOfWork, FixedClock


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
OCR_RUN_ID = UUID("00000000-0000-4000-8000-000000000002")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000003")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000004")

HISTORY_ID = UUID("00000000-0000-4000-8000-000000000010")
AUDIT_ID = UUID("00000000-0000-4000-8000-000000000011")
REVIEW_ID = UUID("00000000-0000-4000-8000-000000000012")
SECOND_HISTORY_ID = UUID(
    "00000000-0000-4000-8000-000000000013"
)
SECOND_AUDIT_ID = UUID(
    "00000000-0000-4000-8000-000000000014"
)

CREATED_AT = datetime(
    2026, 8, 14, 5, 0, tzinfo=timezone.utc
)
CORRECTED_AT = datetime(
    2026, 8, 14, 5, 5, tzinfo=timezone.utc
)
CLEARED_AT = datetime(
    2026, 8, 14, 5, 10, tzinfo=timezone.utc
)


class SequenceIdGenerator:
    def __init__(self, *identifiers: UUID) -> None:
        self.identifiers = list(identifiers)

    def new_id(self) -> UUID:
        if not self.identifiers:
            raise AssertionError("No test identifier remains.")

        return self.identifiers.pop(0)


def make_receipt(
    status: ReceiptStatus = ReceiptStatus.NEEDS_REVIEW,
) -> Receipt:
    return Receipt(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=status,
        image_width_px=1000,
        image_height_px=1500,
        latest_ocr_run_id=OCR_RUN_ID,
        latest_kie_run_id=KIE_RUN_ID,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def make_total_field() -> ExtractedField:
    return ExtractedField(
        receipt_id=RECEIPT_ID,
        field_name=FieldName.TOTAL_AMOUNT,
        ocr_run_id=OCR_RUN_ID,
        kie_run_id=KIE_RUN_ID,
        raw_text="325.000",
        predicted_value="325000",
        normalized_value=325000,
        normalization=NormalizationProvenance(
            rule="vnd_integer",
            version="1.0",
        ),
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value=325000,
        effective_status=ValueStatus.PRESENT,
        confidence=0.7,
        machine_needs_review=True,
        effective_needs_review=True,
        review_reasons=("LOW_CONFIDENCE",),
        review_policy_version="1.0",
        source_block_ids=("block_1",),
        verified=False,
        updated_at=CREATED_AT,
    )


def make_service(
    unit_of_work: FakeUnitOfWork,
    clock: FixedClock,
    *identifiers: UUID,
) -> CorrectionService:
    return CorrectionService(
        unit_of_work_factory=lambda: unit_of_work,
        clock=clock,
        id_generator=SequenceIdGenerator(*identifiers),
    )


def test_apply_correction_updates_field_history_and_audit() -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    clock = FixedClock(CORRECTED_AT)
    service = make_service(
        unit_of_work,
        clock,
        HISTORY_ID,
        AUDIT_ID,
        REVIEW_ID,
    )

    result = asyncio.run(
        service.update_correction(
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            value=330000,
            value_status=ValueStatus.PRESENT,
            expected_updated_at=CREATED_AT,
            actor_id=ACTOR_ID,
        )
    )

    assert result.has_correction is True
    assert result.corrected_value == 330000
    assert result.effective_value == 330000
    assert result.effective_needs_review is False
    assert result.updated_at == CORRECTED_AT

    assert len(unit_of_work.correction_history.records) == 1
    history = unit_of_work.correction_history.records[0]
    assert history.old_value == 325000
    assert history.new_value == 330000
    assert history.changed_by == ACTOR_ID
    assert history.changed_at == CORRECTED_AT

    event_types = [
        event.event_type
        for event in unit_of_work.audit_events.events
    ]
    assert event_types == [
        AuditEventType.REVIEW_STARTED,
        AuditEventType.CORRECTION_APPLIED,
    ]

    stored_receipt = unit_of_work.receipts.items[RECEIPT_ID]
    assert stored_receipt.review_started_at == CORRECTED_AT
    assert stored_receipt.updated_at == CORRECTED_AT
    assert unit_of_work.commit_count == 1


@pytest.mark.parametrize(
    ("value", "value_status"),
    [
        ("330000", ValueStatus.PRESENT),
        (0, ValueStatus.NOT_PRESENT),
    ],
)
def test_apply_rejects_invalid_field_value(
    value: str | int,
    value_status: ValueStatus,
) -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    service = make_service(
        unit_of_work,
        FixedClock(CORRECTED_AT),
    )

    with pytest.raises(InvalidFieldValue):
        asyncio.run(
            service.update_correction(
                receipt_id=RECEIPT_ID,
                field_name=FieldName.TOTAL_AMOUNT,
                operation=CorrectionOperation.APPLY,
                value=value,
                value_status=value_status,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0
    assert unit_of_work.correction_history.records == []


def test_apply_accepts_explicit_not_present() -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    service = make_service(
        unit_of_work,
        FixedClock(CORRECTED_AT),
        HISTORY_ID,
        AUDIT_ID,
        REVIEW_ID,
    )

    result = asyncio.run(
        service.update_correction(
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            value=None,
            value_status=ValueStatus.NOT_PRESENT,
            expected_updated_at=CREATED_AT,
            actor_id=ACTOR_ID,
        )
    )

    assert result.has_correction is True
    assert result.corrected_value is None
    assert result.corrected_status is ValueStatus.NOT_PRESENT
    assert result.effective_value is None
    assert result.effective_status is ValueStatus.NOT_PRESENT
    assert result.effective_needs_review is False


def test_clear_restores_normalized_value_and_keeps_history() -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    clock = FixedClock(CORRECTED_AT)
    service = make_service(
        unit_of_work,
        clock,
        HISTORY_ID,
        AUDIT_ID,
        REVIEW_ID,
        SECOND_HISTORY_ID,
        SECOND_AUDIT_ID,
    )

    applied = asyncio.run(
        service.update_correction(
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            value=330000,
            value_status=ValueStatus.PRESENT,
            expected_updated_at=CREATED_AT,
            actor_id=ACTOR_ID,
        )
    )

    clock.current = CLEARED_AT

    cleared = asyncio.run(
        service.update_correction(
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.CLEAR,
            expected_updated_at=applied.updated_at,
            actor_id=ACTOR_ID,
        )
    )

    assert cleared.has_correction is False
    assert cleared.corrected_value is None
    assert cleared.corrected_status is None
    assert cleared.effective_value == 325000
    assert cleared.effective_status is ValueStatus.PRESENT
    assert cleared.effective_needs_review is True

    history = unit_of_work.correction_history.records
    assert len(history) == 2
    assert [record.operation for record in history] == [
        CorrectionOperation.APPLY,
        CorrectionOperation.CLEAR,
    ]
    assert history[1].old_value == 330000
    assert history[1].new_value == 325000

    event_types = [
        event.event_type
        for event in unit_of_work.audit_events.events
    ]
    assert event_types == [
        AuditEventType.REVIEW_STARTED,
        AuditEventType.CORRECTION_APPLIED,
        AuditEventType.CORRECTION_CLEARED,
    ]


def test_stale_client_cannot_overwrite_newer_correction() -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    service = make_service(
        unit_of_work,
        FixedClock(CORRECTED_AT),
        HISTORY_ID,
        AUDIT_ID,
        REVIEW_ID,
    )

    client_a_token = field.updated_at
    client_b_token = field.updated_at

    asyncio.run(
        service.update_correction(
            receipt_id=RECEIPT_ID,
            field_name=FieldName.TOTAL_AMOUNT,
            operation=CorrectionOperation.APPLY,
            value=330000,
            value_status=ValueStatus.PRESENT,
            expected_updated_at=client_a_token,
            actor_id=ACTOR_ID,
        )
    )

    with pytest.raises(StaleUpdate):
        asyncio.run(
            service.update_correction(
                receipt_id=RECEIPT_ID,
                field_name=FieldName.TOTAL_AMOUNT,
                operation=CorrectionOperation.APPLY,
                value=340000,
                value_status=ValueStatus.PRESENT,
                expected_updated_at=client_b_token,
                actor_id=ACTOR_ID,
            )
        )

    assert len(unit_of_work.correction_history.records) == 1
    stored = unit_of_work.fields.items[
        (RECEIPT_ID, FieldName.TOTAL_AMOUNT)
    ]
    assert stored.effective_value == 330000


def test_correction_rejects_invalid_receipt_state() -> None:
    receipt = make_receipt(ReceiptStatus.VERIFIED)
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    service = make_service(
        unit_of_work,
        FixedClock(CORRECTED_AT),
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(
            service.update_correction(
                receipt_id=RECEIPT_ID,
                field_name=FieldName.TOTAL_AMOUNT,
                operation=CorrectionOperation.APPLY,
                value=330000,
                value_status=ValueStatus.PRESENT,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )


def test_clear_rejects_value_payload() -> None:
    receipt = make_receipt()
    field = make_total_field()
    unit_of_work = FakeUnitOfWork([receipt], [field])
    service = make_service(
        unit_of_work,
        FixedClock(CORRECTED_AT),
    )

    with pytest.raises(InvalidFieldValue):
        asyncio.run(
            service.update_correction(
                receipt_id=RECEIPT_ID,
                field_name=FieldName.TOTAL_AMOUNT,
                operation=CorrectionOperation.CLEAR,
                value=330000,
                value_status=ValueStatus.PRESENT,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )
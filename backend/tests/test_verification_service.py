import asyncio
from datetime import datetime, timezone
from uuid import UUID

import pytest

from backend.app.domain.enums import (
    AuditEventType,
    FieldName,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.errors import (
    FieldNotFound,
    InvalidReceiptState,
    ReceiptNotFound,
    StaleUpdate,
    VerificationFailure,
)
from backend.app.domain.models import (
    ExtractedField,
    Receipt,
)
from backend.app.services.verification_service import (
    VerificationService,
)
from backend.tests.fakes import FakeUnitOfWork, FixedClock


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000101")
OCR_RUN_ID = UUID("00000000-0000-4000-8000-000000000102")
KIE_RUN_ID = UUID("00000000-0000-4000-8000-000000000103")
ACTOR_ID = UUID("00000000-0000-4000-8000-000000000104")
REVIEW_EVENT_ID = UUID(
    "00000000-0000-4000-8000-000000000105"
)
VERIFIED_EVENT_ID = UUID(
    "00000000-0000-4000-8000-000000000106"
)

CREATED_AT = datetime(
    2026, 8, 14, 6, 0, tzinfo=timezone.utc
)
REVIEWED_AT = datetime(
    2026, 8, 14, 6, 5, tzinfo=timezone.utc
)
VERIFIED_AT = datetime(
    2026, 8, 14, 6, 10, tzinfo=timezone.utc
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
    *,
    review_started_at: datetime | None = None,
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
        review_started_at=review_started_at,
    )


def make_field(
    field_name: FieldName,
) -> ExtractedField:
    values: dict[FieldName, str | int] = {
        FieldName.MERCHANT_NAME: "VietReceipt Store",
        FieldName.RECEIPT_DATE: "2026-08-14",
        FieldName.TOTAL_AMOUNT: 325000,
        FieldName.INVOICE_ID: "INV-001",
        FieldName.MERCHANT_ADDRESS: "Ha Noi",
    }

    value = values[field_name]

    return ExtractedField(
        receipt_id=RECEIPT_ID,
        field_name=field_name,
        ocr_run_id=OCR_RUN_ID,
        kie_run_id=KIE_RUN_ID,
        raw_text=str(value),
        predicted_value=str(value),
        normalized_value=value,
        normalization=None,
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value=value,
        effective_status=ValueStatus.PRESENT,
        confidence=0.99,
        machine_needs_review=False,
        effective_needs_review=False,
        review_reasons=(),
        review_policy_version=None,
        source_block_ids=(
            f"block_{field_name.value}",
        ),
        verified=False,
        updated_at=CREATED_AT,
    )


def make_all_fields() -> list[ExtractedField]:
    return [
        make_field(field_name)
        for field_name in FieldName
    ]


def make_service(
    unit_of_work: FakeUnitOfWork,
    clock: FixedClock,
    *identifiers: UUID,
) -> VerificationService:
    return VerificationService(
        unit_of_work_factory=lambda: unit_of_work,
        clock=clock,
        id_generator=SequenceIdGenerator(*identifiers),
    )


def test_get_fields_is_read_only() -> None:
    receipt = make_receipt()
    fields = list(reversed(make_all_fields()))
    unit_of_work = FakeUnitOfWork([receipt], fields)
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )

    result = asyncio.run(
        service.get_fields(
            receipt_id=RECEIPT_ID,
            actor_id=ACTOR_ID,
        )
    )

    assert [
        field.field_name
        for field in result
    ] == list(FieldName)

    stored_receipt = unit_of_work.receipts.items[RECEIPT_ID]
    assert stored_receipt.review_started_at is None
    assert stored_receipt.updated_at == CREATED_AT
    assert unit_of_work.audit_events.events == []
    assert unit_of_work.commit_count == 0

def test_get_fields_rejects_missing_receipt() -> None:
    unit_of_work = FakeUnitOfWork()
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )

    with pytest.raises(ReceiptNotFound):
        asyncio.run(
            service.get_fields(
                receipt_id=RECEIPT_ID,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0


def test_get_fields_rejects_unreviewable_state() -> None:
    receipt = make_receipt(ReceiptStatus.PROCESSING)
    unit_of_work = FakeUnitOfWork(
        [receipt],
        make_all_fields(),
    )
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(
            service.get_fields(
                receipt_id=RECEIPT_ID,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0


def test_verify_marks_receipt_and_fields_verified() -> None:
    receipt = make_receipt()
    fields = make_all_fields()
    immutable_projection = {
        field.field_name: (
            field.ocr_run_id,
            field.kie_run_id,
            field.raw_text,
            field.predicted_value,
            field.normalized_value,
            field.value_status,
        )
        for field in fields
    }

    unit_of_work = FakeUnitOfWork([receipt], fields)
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
        REVIEW_EVENT_ID,
        VERIFIED_EVENT_ID,
    )

    result = asyncio.run(
        service.verify_receipt(
            receipt_id=RECEIPT_ID,
            expected_updated_at=CREATED_AT,
            actor_id=ACTOR_ID,
        )
    )

    assert result.status is ReceiptStatus.VERIFIED
    assert result.review_started_at == VERIFIED_AT
    assert result.verified_at == VERIFIED_AT
    assert result.updated_at == VERIFIED_AT

    stored_fields = list(
        unit_of_work.fields.items.values()
    )
    assert len(stored_fields) == 5

    for field in stored_fields:
        assert field.verified is True
        assert field.effective_needs_review is False
        assert field.updated_at == VERIFIED_AT

        assert (
            field.ocr_run_id,
            field.kie_run_id,
            field.raw_text,
            field.predicted_value,
            field.normalized_value,
            field.value_status,
        ) == immutable_projection[field.field_name]

    assert [
        event.event_type
        for event in unit_of_work.audit_events.events
    ] == [
        AuditEventType.REVIEW_STARTED,
        AuditEventType.RECEIPT_VERIFIED,
    ]
    assert all(
        event.actor_id == ACTOR_ID
        for event in unit_of_work.audit_events.events
    )
    assert unit_of_work.commit_count == 1


def test_verify_preserves_existing_review_start() -> None:
    receipt = make_receipt(
        review_started_at=REVIEWED_AT
    )
    unit_of_work = FakeUnitOfWork(
        [receipt],
        make_all_fields(),
    )
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
        VERIFIED_EVENT_ID,
    )

    result = asyncio.run(
        service.verify_receipt(
            receipt_id=RECEIPT_ID,
            expected_updated_at=CREATED_AT,
            actor_id=ACTOR_ID,
        )
    )

    assert result.review_started_at == REVIEWED_AT
    assert [
        event.event_type
        for event in unit_of_work.audit_events.events
    ] == [AuditEventType.RECEIPT_VERIFIED]


def test_verify_rejects_stale_receipt_token() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork(
        [receipt],
        make_all_fields(),
    )
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
    )
    stale_token = datetime(
        2026, 8, 14, 5, 59, tzinfo=timezone.utc
    )

    with pytest.raises(StaleUpdate):
        asyncio.run(
            service.verify_receipt(
                receipt_id=RECEIPT_ID,
                expected_updated_at=stale_token,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0
    assert unit_of_work.audit_events.events == []


def test_verify_rejects_missing_canonical_field() -> None:
    receipt = make_receipt()
    fields = make_all_fields()[:-1]
    unit_of_work = FakeUnitOfWork([receipt], fields)
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
    )

    with pytest.raises(VerificationFailure):
        asyncio.run(
            service.verify_receipt(
                receipt_id=RECEIPT_ID,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0
    assert unit_of_work.audit_events.events == []


def test_verify_rejects_unresolved_field() -> None:
    receipt = make_receipt()
    fields = make_all_fields()
    unresolved = fields[0]

    unresolved_data = unresolved.model_dump()
    unresolved_data.update(
        {
            "normalized_value": None,
            "value_status": ValueStatus.UNKNOWN,
            "effective_value": None,
            "effective_status": ValueStatus.UNKNOWN,
            "machine_needs_review": True,
            "effective_needs_review": True,
            "review_reasons": ("UNRESOLVED_VALUE",),
            "review_policy_version": "1.0",
        }
    )
    fields[0] = ExtractedField.model_validate(
        unresolved_data
    )

    unit_of_work = FakeUnitOfWork([receipt], fields)
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
    )

    with pytest.raises(VerificationFailure):
        asyncio.run(
            service.verify_receipt(
                receipt_id=RECEIPT_ID,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0
    assert unit_of_work.audit_events.events == []


def test_verify_rejects_invalid_receipt_state() -> None:
    receipt = make_receipt(ReceiptStatus.VERIFIED)
    unit_of_work = FakeUnitOfWork(
        [receipt],
        make_all_fields(),
    )
    service = make_service(
        unit_of_work,
        FixedClock(VERIFIED_AT),
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(
            service.verify_receipt(
                receipt_id=RECEIPT_ID,
                expected_updated_at=CREATED_AT,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0

def test_get_fields_accepts_explicit_kie_run_id() -> None:
    receipt = make_receipt(
        review_started_at=REVIEWED_AT
    )
    fields = make_all_fields()
    unit_of_work = FakeUnitOfWork([receipt], fields)
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )

    result = asyncio.run(
        service.get_fields(
            receipt_id=RECEIPT_ID,
            kie_run_id=KIE_RUN_ID,
            actor_id=ACTOR_ID,
        )
    )

    assert len(result) == 5
    assert {
        field.kie_run_id
        for field in result
    } == {KIE_RUN_ID}
    assert unit_of_work.commit_count == 0


def test_get_fields_rejects_unknown_kie_run_id() -> None:
    receipt = make_receipt(
        review_started_at=REVIEWED_AT
    )
    unit_of_work = FakeUnitOfWork(
        [receipt],
        make_all_fields(),
    )
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )
    unknown_kie_run_id = UUID(
        "00000000-0000-4000-8000-000000000199"
    )

    with pytest.raises(FieldNotFound):
        asyncio.run(
            service.get_fields(
                receipt_id=RECEIPT_ID,
                kie_run_id=unknown_kie_run_id,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0


def test_get_fields_rejects_incomplete_latest_projection() -> None:
    receipt = make_receipt(
        review_started_at=REVIEWED_AT
    )
    incomplete_fields = make_all_fields()[:-1]
    unit_of_work = FakeUnitOfWork(
        [receipt],
        incomplete_fields,
    )
    service = make_service(
        unit_of_work,
        FixedClock(REVIEWED_AT),
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(
            service.get_fields(
                receipt_id=RECEIPT_ID,
                actor_id=ACTOR_ID,
            )
        )

    assert unit_of_work.commit_count == 0
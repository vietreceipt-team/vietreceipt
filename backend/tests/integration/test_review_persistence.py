from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
    ProcessingStage,
    ReceiptStatus,
    ValueStatus,
)
from backend.app.domain.models import (
    ExtractedField,
    NormalizationProvenance,
    Receipt,
)
from backend.app.persistence.models import (
    Base,
    KIERunRecord,
    OCRRunRecord,
    ProcessingAttemptRecord,
    ReceiptRecord,
)
from backend.app.persistence.sqlalchemy_field_repository import (
    SQLAlchemyFieldRepository,
)
from backend.app.persistence.sqlalchemy_unit_of_work import (
    SQLAlchemyUnitOfWorkFactory,
)
from backend.app.services.correction_service import CorrectionService


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self._value = value

    def now(self) -> datetime:
        return self._value


class SequenceIdGenerator:
    def __init__(self, *values: UUID) -> None:
        self._values = list(values)

    def new_id(self) -> UUID:
        if not self._values:
            raise AssertionError("No configured UUID remains.")
        return self._values.pop(0)


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )
    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        engine.dispose()


def seed_review_receipt(session_factory):
    created_at = datetime(
        2026,
        9,
        3,
        1,
        0,
        tzinfo=timezone.utc,
    )

    receipt_id = uuid4()
    attempt_id = uuid4()
    ocr_run_id = uuid4()
    kie_run_id = uuid4()

    receipt = Receipt(
        receipt_id=receipt_id,
        original_filename="receipt.jpg",
        status=ReceiptStatus.NEEDS_REVIEW,
        processing_stage=None,
        image_width_px=1000,
        image_height_px=1600,
        latest_ocr_run_id=ocr_run_id,
        latest_kie_run_id=kie_run_id,
        last_error=None,
        created_at=created_at,
        updated_at=created_at,
        review_started_at=None,
        processed_at=created_at,
        verified_at=None,
    )

    field = ExtractedField(
        receipt_id=receipt_id,
        field_name=FieldName.MERCHANT_NAME,
        ocr_run_id=ocr_run_id,
        kie_run_id=kie_run_id,
        raw_text="ABC Strore",
        predicted_value="ABC Strore",
        normalized_value="ABC Strore",
        normalization=NormalizationProvenance(
            rule="identity",
            version="1",
        ),
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value="ABC Strore",
        effective_status=ValueStatus.PRESENT,
        confidence=0.70,
        machine_needs_review=True,
        effective_needs_review=True,
        review_reasons=("low_confidence",),
        review_policy_version="1",
        source_block_ids=("block-1",),
        verified=False,
        updated_at=created_at,
    )

    with session_factory() as session:
        session.add(
            ReceiptRecord.from_domain(
                receipt,
                storage_key=f"receipts/{receipt_id}.jpg",
                content_type="image/jpeg",
            )
        )

        session.add(
            ProcessingAttemptRecord(
                attempt_id=attempt_id,
                receipt_id=receipt_id,
                active_receipt_id=None,
                delivery_id="delivery-1",
                ocr_run_id=ocr_run_id,
                kie_run_id=kie_run_id,
                status="SUCCEEDED",
                stage=ProcessingStage.PERSISTING.value,
                started_at=created_at,
                finished_at=created_at,
                error=None,
            )
        )

        session.add(
            OCRRunRecord(
                ocr_run_id=ocr_run_id,
                attempt_id=attempt_id,
                receipt_id=receipt_id,
                payload={"text": "ABC Strore"},
                created_at=created_at,
            )
        )

        session.add(
            KIERunRecord(
                kie_run_id=kie_run_id,
                attempt_id=attempt_id,
                receipt_id=receipt_id,
                source_ocr_run_id=ocr_run_id,
                payload={"merchant_name": "ABC Strore"},
                created_at=created_at,
            )
        )

        field_repository = SQLAlchemyFieldRepository(session)
        field_repository.add_initial(field)

        session.commit()

    return receipt, field


@pytest.mark.asyncio
async def test_correction_service_persists_field_receipt_history_and_audit(
    session_factory,
):
    receipt, original_field = seed_review_receipt(
        session_factory
    )

    occurred_at = original_field.updated_at + timedelta(
        minutes=1
    )
    actor_id = uuid4()

    review_event_id = UUID(int=1)
    correction_event_id = UUID(int=2)
    correction_id = UUID(int=3)

    service = CorrectionService(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(
            session_factory
        ),
        clock=FixedClock(occurred_at),
        id_generator=SequenceIdGenerator(
            correction_id,
            correction_event_id,
            review_event_id,
        ),
    )

    saved = await service.update_correction(
        receipt_id=receipt.receipt_id,
        field_name=FieldName.MERCHANT_NAME,
        operation=CorrectionOperation.APPLY,
        expected_updated_at=original_field.updated_at,
        actor_id=actor_id,
        value="ABC Store",
        value_status=ValueStatus.PRESENT,
    )

    assert saved.has_correction is True
    assert saved.corrected_value == "ABC Store"
    assert saved.effective_value == "ABC Store"
    assert saved.effective_needs_review is False
    assert saved.updated_at == occurred_at

    uow_factory = SQLAlchemyUnitOfWorkFactory(
        session_factory
    )

    async with uow_factory() as uow:
        stored_receipt = await uow.receipts.get(
            receipt.receipt_id
        )
        stored_field = await uow.fields.get(
            receipt.receipt_id,
            FieldName.MERCHANT_NAME,
        )
        history = await uow.correction_history.list_for_receipt(
            receipt.receipt_id
        )
        events = await uow.audit_events.list_for_receipt(
            receipt.receipt_id
        )

    assert stored_receipt is not None
    assert stored_receipt.review_started_at == occurred_at
    assert stored_receipt.updated_at == occurred_at

    assert stored_field is not None
    assert stored_field == saved

    assert len(history) == 1
    assert history[0].correction_id == correction_id
    assert history[0].old_value == "ABC Strore"
    assert history[0].new_value == "ABC Store"
    assert history[0].changed_by == actor_id

    assert [event.event_type for event in events] == [
        AuditEventType.REVIEW_STARTED,
        AuditEventType.CORRECTION_APPLIED,
    ]
    assert {
        event.event_id
        for event in events
    } == {
        review_event_id,
        correction_event_id,
    }


def make_verifiable_field(
    *,
    receipt_id,
    ocr_run_id,
    kie_run_id,
    field_name,
    normalized_value,
    updated_at,
):
    return ExtractedField(
        receipt_id=receipt_id,
        field_name=field_name,
        ocr_run_id=ocr_run_id,
        kie_run_id=kie_run_id,
        raw_text=str(normalized_value),
        predicted_value=str(normalized_value),
        normalized_value=normalized_value,
        normalization=NormalizationProvenance(
            rule="identity",
            version="1",
        ),
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value=normalized_value,
        effective_status=ValueStatus.PRESENT,
        confidence=0.99,
        machine_needs_review=False,
        effective_needs_review=False,
        review_reasons=(),
        review_policy_version=None,
        source_block_ids=(
            f"block-{field_name.value}",
        ),
        verified=False,
        updated_at=updated_at,
    )


@pytest.mark.asyncio
async def test_verification_service_persists_verified_receipt_fields_and_audit(
    session_factory,
):
    from backend.app.services.verification_service import (
        VerificationService,
    )

    receipt, merchant_field = seed_review_receipt(
        session_factory
    )

    field_version = merchant_field.updated_at + timedelta(
        seconds=10
    )

    approved_merchant = merchant_field.model_copy(
        update={
            "confidence": 0.99,
            "machine_needs_review": False,
            "effective_needs_review": False,
            "review_reasons": (),
            "review_policy_version": None,
            "updated_at": field_version,
        }
    )

    fields = [
        make_verifiable_field(
            receipt_id=receipt.receipt_id,
            ocr_run_id=merchant_field.ocr_run_id,
            kie_run_id=merchant_field.kie_run_id,
            field_name=FieldName.RECEIPT_DATE,
            normalized_value="2026-09-03",
            updated_at=field_version,
        ),
        make_verifiable_field(
            receipt_id=receipt.receipt_id,
            ocr_run_id=merchant_field.ocr_run_id,
            kie_run_id=merchant_field.kie_run_id,
            field_name=FieldName.TOTAL_AMOUNT,
            normalized_value=125000,
            updated_at=field_version,
        ),
        make_verifiable_field(
            receipt_id=receipt.receipt_id,
            ocr_run_id=merchant_field.ocr_run_id,
            kie_run_id=merchant_field.kie_run_id,
            field_name=FieldName.INVOICE_ID,
            normalized_value="INV-001",
            updated_at=field_version,
        ),
        make_verifiable_field(
            receipt_id=receipt.receipt_id,
            ocr_run_id=merchant_field.ocr_run_id,
            kie_run_id=merchant_field.kie_run_id,
            field_name=FieldName.MERCHANT_ADDRESS,
            normalized_value="Hanoi",
            updated_at=field_version,
        ),
    ]

    with session_factory() as session:
        repository = SQLAlchemyFieldRepository(session)

        await repository.save(
            approved_merchant,
            expected_updated_at=merchant_field.updated_at,
        )

        for field in fields:
            repository.add_initial(field)

        session.commit()

    verified_at = field_version + timedelta(
        minutes=1
    )

    review_event_id = UUID(int=10)
    verified_event_id = UUID(int=11)

    service = VerificationService(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(
            session_factory
        ),
        clock=FixedClock(verified_at),
        id_generator=SequenceIdGenerator(
            review_event_id,
            verified_event_id,
        ),
    )

    saved_receipt = await service.verify_receipt(
        receipt_id=receipt.receipt_id,
        expected_updated_at=receipt.updated_at,
        actor_id=uuid4(),
    )

    assert saved_receipt.status is ReceiptStatus.VERIFIED
    assert saved_receipt.review_started_at == verified_at
    assert saved_receipt.verified_at == verified_at
    assert saved_receipt.updated_at == verified_at

    async with SQLAlchemyUnitOfWorkFactory(
        session_factory
    )() as uow:
        stored_fields = await uow.fields.list_for_receipt(
            receipt.receipt_id,
            kie_run_id=receipt.latest_kie_run_id,
        )
        events = await uow.audit_events.list_for_receipt(
            receipt.receipt_id
        )

    assert len(stored_fields) == 5
    assert all(field.verified for field in stored_fields)
    assert all(
        field.updated_at == verified_at
        for field in stored_fields
    )

    assert [
        event.event_type
        for event in events
    ] == [
        AuditEventType.REVIEW_STARTED,
        AuditEventType.RECEIPT_VERIFIED,
    ]

    assert {
        event.event_id
        for event in events
    } == {
        review_event_id,
        verified_event_id,
    }

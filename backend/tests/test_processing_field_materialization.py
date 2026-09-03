from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import (
    FieldName,
    ReceiptStatus,
)
from backend.app.persistence.models import (
    Base,
    ReceiptRecord,
)
from backend.app.persistence.sqlalchemy_field_repository import (
    SQLAlchemyFieldRepository,
)
from backend.app.persistence.sqlalchemy_processing_repository import (
    SQLAlchemyProcessingRepository,
)


def kie_payload(
    *,
    receipt_id,
    kie_run_id,
    ocr_run_id,
):
    return {
        "schema_version": "1.3",
        "receipt_id": str(receipt_id),
        "kie_run_id": str(kie_run_id),
        "source_ocr_run_id": str(ocr_run_id),
        "extractor": {
            "name": "test-kie",
            "version": "1",
        },
        "fields": {
            "merchant_name": {
                "raw_text": "ABC Store",
                "predicted_value": "ABC Store",
                "normalized_value": "ABC Store",
                "normalization": {
                    "rule": "identity",
                    "version": "1",
                },
                "value_status": "PRESENT",
                "confidence": 0.99,
                "machine_needs_review": False,
                "review_reasons": [],
                "source_block_ids": ["b1"],
            },
            "receipt_date": {
                "raw_text": "03/09/2026",
                "predicted_value": "03/09/2026",
                "normalized_value": "2026-09-03",
                "normalization": {
                    "rule": "date",
                    "version": "1",
                },
                "value_status": "PRESENT",
                "confidence": 0.98,
                "machine_needs_review": False,
                "review_reasons": [],
                "source_block_ids": ["b2"],
            },
            "total_amount": {
                "raw_text": "125,000",
                "predicted_value": "125,000",
                "normalized_value": 125000,
                "normalization": {
                    "rule": "vnd",
                    "version": "1",
                },
                "currency": "VND",
                "value_status": "PRESENT",
                "confidence": 0.97,
                "machine_needs_review": False,
                "review_reasons": [],
                "source_block_ids": ["b3"],
            },
            "invoice_id": {
                "raw_text": "INV-001",
                "predicted_value": "INV-001",
                "normalized_value": "INV-001",
                "normalization": {
                    "rule": "identity",
                    "version": "1",
                },
                "value_status": "PRESENT",
                "confidence": 0.96,
                "machine_needs_review": False,
                "review_reasons": [],
                "source_block_ids": ["b4"],
            },
            "merchant_address": {
                "raw_text": "Hanoi",
                "predicted_value": "Hanoi",
                "normalized_value": "Hanoi",
                "normalization": {
                    "rule": "identity",
                    "version": "1",
                },
                "value_status": "PRESENT",
                "confidence": 0.95,
                "machine_needs_review": False,
                "review_reasons": [],
                "source_block_ids": ["b5"],
            },
        },
        "duration_ms": 10,
        "created_at": "2026-09-03T01:00:00Z",
    }


@pytest.mark.asyncio
async def test_kie_completion_materializes_five_canonical_fields():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )
    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    started_at = datetime(
        2026,
        9,
        3,
        1,
        0,
        tzinfo=timezone.utc,
    )
    ocr_at = started_at + timedelta(seconds=1)
    completed_at = started_at + timedelta(seconds=2)

    receipt_id = uuid4()
    attempt_id = uuid4()
    ocr_run_id = uuid4()
    kie_run_id = uuid4()

    try:
        with factory() as session:
            session.add(
                ReceiptRecord(
                    receipt_id=receipt_id,
                    original_filename="receipt.jpg",
                    storage_key=f"receipts/{receipt_id}.jpg",
                    content_type="image/jpeg",
                    status=ReceiptStatus.UPLOADED.value,
                    processing_stage=None,
                    image_width_px=1000,
                    image_height_px=1600,
                    latest_ocr_run_id=None,
                    latest_kie_run_id=None,
                    last_error=None,
                    created_at=started_at,
                    updated_at=started_at,
                    review_started_at=None,
                    processed_at=None,
                    verified_at=None,
                )
            )
            session.commit()

            processing = SQLAlchemyProcessingRepository(
                session
            )

            attempt = await processing.claim(
                receipt_id,
                delivery_id="delivery-1",
                attempt_id=attempt_id,
                ocr_run_id=ocr_run_id,
                kie_run_id=kie_run_id,
                started_at=started_at,
            )

            assert attempt is not None

            await processing.append_ocr_output(
                attempt,
                {
                    "receipt_id": str(receipt_id),
                    "ocr_run_id": str(ocr_run_id),
                },
                created_at=ocr_at,
            )

            await processing.append_kie_output_and_complete(
                attempt,
                kie_payload(
                    receipt_id=receipt_id,
                    kie_run_id=kie_run_id,
                    ocr_run_id=ocr_run_id,
                ),
                completed_at=completed_at,
            )

            session.commit()

        with factory() as session:
            receipt = session.get(
                ReceiptRecord,
                receipt_id,
            )

            fields = await SQLAlchemyFieldRepository(
                session
            ).list_for_receipt(
                receipt_id,
                kie_run_id=kie_run_id,
            )

        assert receipt is not None
        assert receipt.status == ReceiptStatus.NEEDS_REVIEW.value

        assert len(fields) == 5
        assert {
            field.field_name
            for field in fields
        } == set(FieldName)

        by_name = {
            field.field_name: field
            for field in fields
        }

        merchant = by_name[FieldName.MERCHANT_NAME]
        assert merchant.normalized_value == "ABC Store"
        assert merchant.has_correction is False
        assert merchant.effective_value == "ABC Store"
        assert merchant.effective_needs_review is False
        assert merchant.verified is False
        assert merchant.updated_at == completed_at

        total = by_name[FieldName.TOTAL_AMOUNT]
        assert total.normalized_value == 125000
        assert isinstance(total.normalized_value, int)

    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_kie_completion_rolls_back_when_field_materialization_fails():
    from sqlalchemy import select

    from backend.app.domain.errors import PersistenceFailure
    from backend.app.persistence.models import (
        ExtractedFieldRecord,
        KIERunRecord,
        ProcessingAttemptRecord,
    )
    from backend.app.persistence.sqlalchemy_unit_of_work import (
        SQLAlchemyUnitOfWorkFactory,
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )
    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    started_at = datetime(
        2026,
        9,
        3,
        2,
        0,
        tzinfo=timezone.utc,
    )
    ocr_at = started_at + timedelta(seconds=1)
    completed_at = started_at + timedelta(seconds=2)

    receipt_id = uuid4()
    attempt_id = uuid4()
    ocr_run_id = uuid4()
    kie_run_id = uuid4()

    try:
        with factory() as session:
            session.add(
                ReceiptRecord(
                    receipt_id=receipt_id,
                    original_filename="receipt.jpg",
                    storage_key=f"receipts/{receipt_id}.jpg",
                    content_type="image/jpeg",
                    status=ReceiptStatus.UPLOADED.value,
                    processing_stage=None,
                    image_width_px=1000,
                    image_height_px=1600,
                    latest_ocr_run_id=None,
                    latest_kie_run_id=None,
                    last_error=None,
                    created_at=started_at,
                    updated_at=started_at,
                    review_started_at=None,
                    processed_at=None,
                    verified_at=None,
                )
            )
            session.commit()

            processing = SQLAlchemyProcessingRepository(
                session
            )

            attempt = await processing.claim(
                receipt_id,
                delivery_id="delivery-rollback",
                attempt_id=attempt_id,
                ocr_run_id=ocr_run_id,
                kie_run_id=kie_run_id,
                started_at=started_at,
            )

            assert attempt is not None

            await processing.append_ocr_output(
                attempt,
                {
                    "receipt_id": str(receipt_id),
                    "ocr_run_id": str(ocr_run_id),
                },
                created_at=ocr_at,
            )

            session.commit()

            # Seed one conflicting canonical field.
            # Materialization will try to insert the same
            # (receipt_id, field_name) primary key.
            session.add(
                ExtractedFieldRecord(
                    receipt_id=receipt_id,
                    field_name=FieldName.MERCHANT_NAME.value,
                    ocr_run_id=ocr_run_id,
                    kie_run_id=kie_run_id,
                    raw_text="existing",
                    predicted_value="existing",
                    normalized_value="existing",
                    normalization={
                        "rule": "identity",
                        "version": "1",
                    },
                    value_status="PRESENT",
                    corrected_value=None,
                    corrected_status=None,
                    has_correction=False,
                    effective_value="existing",
                    effective_status="PRESENT",
                    confidence=1.0,
                    machine_needs_review=False,
                    effective_needs_review=False,
                    review_reasons=[],
                    review_policy_version=None,
                    source_block_ids=["existing-block"],
                    verified=False,
                    updated_at=ocr_at,
                )
            )
            session.commit()

        uow_factory = SQLAlchemyUnitOfWorkFactory(
            factory
        )

        with pytest.raises(PersistenceFailure):
            async with uow_factory() as uow:
                await uow.processing.append_kie_output_and_complete(
                    attempt,
                    kie_payload(
                        receipt_id=receipt_id,
                        kie_run_id=kie_run_id,
                        ocr_run_id=ocr_run_id,
                    ),
                    completed_at=completed_at,
                )
                await uow.commit()

        with factory() as session:
            receipt = session.get(
                ReceiptRecord,
                receipt_id,
            )
            stored_attempt = session.get(
                ProcessingAttemptRecord,
                attempt_id,
            )
            kie_run = session.get(
                KIERunRecord,
                kie_run_id,
            )

            stored_fields = session.scalars(
                select(ExtractedFieldRecord).where(
                    ExtractedFieldRecord.receipt_id
                    == receipt_id
                )
            ).all()

        assert receipt is not None
        assert receipt.status == ReceiptStatus.PROCESSING.value
        assert receipt.latest_kie_run_id is None
        assert receipt.processed_at is None

        assert stored_attempt is not None
        assert stored_attempt.status == "ACTIVE"
        assert stored_attempt.active_receipt_id == receipt_id

        assert kie_run is None

        # Only the intentionally seeded conflicting row remains.
        assert len(stored_fields) == 1
        assert (
            stored_fields[0].field_name
            == FieldName.MERCHANT_NAME.value
        )

    finally:
        engine.dispose()

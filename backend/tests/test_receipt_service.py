import asyncio
from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest

from backend.app.domain.enums import (
    ErrorStage,
    ReceiptStatus,
)
from backend.app.domain.errors import (
    InvalidReceiptState,
    PersistenceFailure,
    ReceiptNotFound,
    SchedulingFailure,
)
from backend.app.domain.models import ProcessingError, Receipt
from backend.app.ports.persistence import ReceiptUpload
from backend.app.services.receipt_service import ReceiptService
from backend.tests.fakes import (
    FakeProcessingScheduler,
    FakeReceiptPersistenceService,
    FakeUnitOfWork,
    FixedClock,
)


RECEIPT_ID = UUID("00000000-0000-4000-8000-000000000001")
CREATED_AT = datetime(
    2026, 8, 14, 4, 0, tzinfo=timezone.utc
)
NEXT_TIME = datetime(
    2026, 8, 14, 4, 5, tzinfo=timezone.utc
)


def make_receipt(
    status: ReceiptStatus = ReceiptStatus.UPLOADED,
    *,
    retryable: bool = False,
) -> Receipt:
    last_error = None

    if status is ReceiptStatus.FAILED:
        last_error = ProcessingError(
            stage=ErrorStage.OCR,
            code="OCR_FAILED",
            message="OCR processing failed.",
            retryable=retryable,
            occurred_at=CREATED_AT,
        )

    return Receipt(
        receipt_id=RECEIPT_ID,
        original_filename="receipt.jpg",
        status=status,
        image_width_px=1000,
        image_height_px=1500,
        last_error=last_error,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def make_upload() -> ReceiptUpload:
    return ReceiptUpload(
        filename="receipt.jpg",
        content_type="image/jpeg",
        file=BytesIO(b"test-image"),
    )


def make_service(
    *,
    receipt: Receipt,
    unit_of_work: FakeUnitOfWork,
    scheduler: FakeProcessingScheduler,
    persistence_error: Exception | None = None,
) -> ReceiptService:
    persistence = FakeReceiptPersistenceService(
        receipt=receipt,
        repository=unit_of_work.receipts,
        error=persistence_error,
    )

    return ReceiptService(
        persistence=persistence,
        scheduler=scheduler,
        unit_of_work_factory=lambda: unit_of_work,
        clock=FixedClock(NEXT_TIME),
    )


def test_upload_success_returns_uploaded_receipt() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork()
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    result = asyncio.run(
        service.upload_receipt(make_upload())
    )

    assert result.status is ReceiptStatus.UPLOADED
    assert scheduler.enqueued_receipt_ids == [RECEIPT_ID]
    assert unit_of_work.receipts.items[RECEIPT_ID] == result


def test_enqueue_success_does_not_set_processing() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork()
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    result = asyncio.run(
        service.upload_receipt(make_upload())
    )

    assert result.status is ReceiptStatus.UPLOADED
    assert result.processing_stage is None
    assert unit_of_work.commit_count == 0


def test_initial_scheduling_failure_records_failed_receipt() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork()
    scheduler = FakeProcessingScheduler(should_fail=True)
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    result = asyncio.run(
        service.upload_receipt(make_upload())
    )

    assert result.status is ReceiptStatus.FAILED
    assert result.last_error is not None
    assert result.last_error.stage is ErrorStage.SCHEDULING
    assert result.last_error.retryable is True
    assert result.updated_at == NEXT_TIME
    assert unit_of_work.commit_count == 1
    assert unit_of_work.receipts.items[RECEIPT_ID] == result


def test_persistence_exception_is_translated() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork()
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
        persistence_error=RuntimeError("raw storage error"),
    )

    with pytest.raises(PersistenceFailure) as captured:
        asyncio.run(service.upload_receipt(make_upload()))

    assert captured.value.message == (
        "Receipt persistence failed."
    )
    assert isinstance(captured.value.__cause__, RuntimeError)


def test_retry_rejects_non_failed_receipt() -> None:
    receipt = make_receipt(ReceiptStatus.UPLOADED)
    unit_of_work = FakeUnitOfWork([receipt])
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(service.retry_receipt(RECEIPT_ID))


def test_retry_rejects_non_retryable_failure() -> None:
    receipt = make_receipt(
        ReceiptStatus.FAILED,
        retryable=False,
    )
    unit_of_work = FakeUnitOfWork([receipt])
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    with pytest.raises(InvalidReceiptState):
        asyncio.run(service.retry_receipt(RECEIPT_ID))


def test_retry_success_keeps_failed_until_worker_claim() -> None:
    receipt = make_receipt(
        ReceiptStatus.FAILED,
        retryable=True,
    )
    unit_of_work = FakeUnitOfWork([receipt])
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    accepted_receipt_id = asyncio.run(
        service.retry_receipt(RECEIPT_ID)
    )

    assert accepted_receipt_id == RECEIPT_ID
    assert scheduler.enqueued_receipt_ids == [RECEIPT_ID]
    stored = unit_of_work.receipts.items[RECEIPT_ID]
    assert stored.status is ReceiptStatus.FAILED


def test_retry_missing_receipt_returns_typed_error() -> None:
    receipt = make_receipt()
    unit_of_work = FakeUnitOfWork()
    scheduler = FakeProcessingScheduler()
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    with pytest.raises(ReceiptNotFound):
        asyncio.run(service.retry_receipt(RECEIPT_ID))


def test_retry_scheduling_failure_remains_failed() -> None:
    receipt = make_receipt(
        ReceiptStatus.FAILED,
        retryable=True,
    )
    unit_of_work = FakeUnitOfWork([receipt])
    scheduler = FakeProcessingScheduler(should_fail=True)
    service = make_service(
        receipt=receipt,
        unit_of_work=unit_of_work,
        scheduler=scheduler,
    )

    with pytest.raises(SchedulingFailure):
        asyncio.run(service.retry_receipt(RECEIPT_ID))

    stored = unit_of_work.receipts.items[RECEIPT_ID]
    assert stored.status is ReceiptStatus.FAILED
    assert stored.last_error is not None
    assert stored.last_error.stage is ErrorStage.SCHEDULING
    assert stored.last_error.retryable is True
    assert unit_of_work.commit_count == 1

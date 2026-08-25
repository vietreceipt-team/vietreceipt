import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.app.worker.celery_app as worker_module
from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import PersistenceFailure
from backend.app.domain.models import Receipt
from backend.app.persistence.models import ProcessingAttemptRecord
from backend.app.persistence.sqlalchemy_receipt_repository import (
    SQLAlchemyReceiptRepository,
)
from backend.app.persistence.sqlalchemy_unit_of_work import (
    SQLAlchemyUnitOfWorkFactory,
)
from backend.app.services.processing_recovery import (
    ProcessingRecoveryService,
)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class AlwaysFailingOrchestrator:
    async def process(self, receipt_id, *, delivery_id):
        raise PersistenceFailure("simulated persistent DB outage")


def setup_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'recovery.db'}",
        connect_args={"check_same_thread": False},
    )
    from backend.app.persistence.models import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    receipt_id = uuid4()
    now = datetime.now(timezone.utc)
    receipt = Receipt(
        receipt_id=receipt_id,
        original_filename="stale.png",
        status=ReceiptStatus.UPLOADED,
        image_width_px=20,
        image_height_px=20,
        created_at=now,
        updated_at=now,
    )

    session = factory()
    asyncio.run(
        SQLAlchemyReceiptRepository(session).create_with_storage(
            receipt,
            storage_key=f"receipts/{receipt_id}.png",
            content_type="image/png",
        )
    )
    session.commit()
    session.close()

    return factory, receipt_id


def test_reaper_recovers_receipt_after_celery_retry_exhaustion(
    tmp_path,
    monkeypatch,
):
    factory, receipt_id = setup_database(tmp_path)
    now = datetime.now(timezone.utc)
    old_started_at = now - timedelta(hours=1)

    async def create_active_attempt():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            attempt = await uow.processing.claim(
                receipt_id,
                delivery_id="exhausted-delivery",
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=old_started_at,
            )
            assert attempt is not None
            await uow.commit()
            return attempt

    attempt = asyncio.run(create_active_attempt())

    monkeypatch.setattr(
        worker_module,
        "_get_orchestrator",
        lambda: AlwaysFailingOrchestrator(),
    )

    worker_module.process_receipt.push_request(
        id="exhausted-delivery",
        retries=worker_module.process_receipt.max_retries,
        called_directly=False,
        is_eager=True,
    )
    try:
        with pytest.raises(
            RuntimeError,
            match="transient processing persistence failure",
        ):
            worker_module.process_receipt.run(str(receipt_id))
    finally:
        worker_module.process_receipt.pop_request()

    session = factory()
    before_receipt = asyncio.run(
        SQLAlchemyReceiptRepository(session).get(receipt_id)
    )
    before_attempt = session.get(
        ProcessingAttemptRecord,
        attempt.attempt_id,
    )

    assert before_receipt.status is ReceiptStatus.PROCESSING
    assert before_attempt.status == "ACTIVE"
    session.close()

    recovery = ProcessingRecoveryService(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(factory),
        clock=FixedClock(now),
        stale_after=timedelta(minutes=15),
    )

    assert asyncio.run(
        recovery.recover_stale_attempts()
    ) == 1

    session = factory()
    receipt = asyncio.run(
        SQLAlchemyReceiptRepository(session).get(receipt_id)
    )
    attempt_record = session.get(
        ProcessingAttemptRecord,
        attempt.attempt_id,
    )

    assert receipt.status is ReceiptStatus.FAILED
    assert receipt.last_error.code == "PROCESSING_ATTEMPT_EXPIRED"
    assert receipt.last_error.retryable is True
    assert attempt_record.status == "FAILED"
    assert attempt_record.active_receipt_id is None
    session.close()

    async def claim_retry():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            retry = await uow.processing.claim(
                receipt_id,
                delivery_id="new-delivery-after-recovery",
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=now + timedelta(seconds=1),
            )
            assert retry is not None
            await uow.commit()
            return retry

    retry = asyncio.run(claim_retry())
    assert retry.attempt_id != attempt.attempt_id


def test_reaper_does_not_touch_fresh_active_attempt(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    now = datetime.now(timezone.utc)

    async def create_active_attempt():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            attempt = await uow.processing.claim(
                receipt_id,
                delivery_id="fresh-delivery",
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=now - timedelta(minutes=5),
            )
            assert attempt is not None
            await uow.commit()
            return attempt

    attempt = asyncio.run(create_active_attempt())

    recovery = ProcessingRecoveryService(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(factory),
        clock=FixedClock(now),
        stale_after=timedelta(minutes=15),
    )

    assert asyncio.run(
        recovery.recover_stale_attempts()
    ) == 0

    session = factory()
    attempt_record = session.get(
        ProcessingAttemptRecord,
        attempt.attempt_id,
    )
    receipt = asyncio.run(
        SQLAlchemyReceiptRepository(session).get(receipt_id)
    )

    assert attempt_record.status == "ACTIVE"
    assert receipt.status is ReceiptStatus.PROCESSING
    session.close()

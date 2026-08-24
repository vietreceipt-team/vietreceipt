from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from backend.app.adapters.celery_scheduler import CeleryProcessingScheduler
from backend.app.domain.enums import ErrorStage, ReceiptStatus
from backend.app.domain.errors import StaleUpdate
from backend.app.domain.models import ProcessingError, Receipt
from backend.app.persistence.models import (
    Base,
    KIERunRecord,
    OCRRunRecord,
    ProcessingAttemptRecord,
)
from backend.app.persistence.sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository
from backend.app.persistence.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWorkFactory
from backend.app.ports.clock import SystemClock
from backend.app.ports.ids import UUID4Generator
from backend.app.services.processing_orchestrator import ProcessingOrchestrator, ProcessingOutcome


ROOT = Path(__file__).resolve().parents[2]


class ImageLoader:
    async def load(self, receipt_id: UUID) -> bytes:
        return b"image"


class OCR:
    def __init__(self, *, invalid: bool = False, fail: bool = False) -> None:
        self.invalid = invalid
        self.fail = fail
        self.calls = 0

    def __call__(self, image, *, receipt_id, ocr_run_id):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret provider detail")
        payload = json.loads((ROOT / "examples/ocr-result.json").read_text())
        payload["receipt_id"] = str(receipt_id)
        payload["ocr_run_id"] = str(ocr_run_id)
        if self.invalid:
            payload.pop("blocks")
        return payload


class KIE:
    def __init__(self, *, invalid: bool = False, fail: bool = False) -> None:
        self.invalid = invalid
        self.fail = fail
        self.calls = 0

    def __call__(self, ocr_result, *, kie_run_id):
        self.calls += 1
        if self.fail:
            raise RuntimeError("secret provider detail")
        payload = json.loads((ROOT / "examples/kie-result.json").read_text())
        payload["receipt_id"] = ocr_result["receipt_id"]
        payload["kie_run_id"] = str(kie_run_id)
        payload["source_ocr_run_id"] = ocr_result["ocr_run_id"]
        if self.invalid:
            payload["fields"].pop("merchant_name")
        return payload


def setup_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'processing.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    receipt_id = uuid4()
    now = datetime.now(timezone.utc)
    receipt = Receipt(
        receipt_id=receipt_id,
        original_filename="receipt.png",
        status=ReceiptStatus.UPLOADED,
        image_width_px=100,
        image_height_px=100,
        created_at=now,
        updated_at=now,
    )
    session = factory()
    asyncio.run(
        SQLAlchemyReceiptRepository(session).create_with_storage(
            receipt, storage_key=f"receipts/{receipt_id}.png", content_type="image/png"
        )
    )
    session.commit()
    session.close()
    return factory, receipt_id


def orchestrator(factory, ocr=None, kie=None):
    return ProcessingOrchestrator(
        unit_of_work_factory=SQLAlchemyUnitOfWorkFactory(factory),
        image_loader=ImageLoader(),
        ocr_provider=ocr or OCR(),
        kie_provider=kie or KIE(),
        id_generator=UUID4Generator(),
        clock=SystemClock(),
    )


def counts(factory):
    session = factory()
    result = (
        session.scalar(select(func.count()).select_from(ProcessingAttemptRecord)),
        session.scalar(select(func.count()).select_from(OCRRunRecord)),
        session.scalar(select(func.count()).select_from(KIERunRecord)),
    )
    session.close()
    return result


def test_scheduler_payload_contains_only_receipt_id():
    class CelerySpy:
        def __init__(self):
            self.calls = []

        def send_task(self, name, *, args):
            self.calls.append((name, args))

    spy = CelerySpy()
    receipt_id = uuid4()
    asyncio.run(CeleryProcessingScheduler(spy).enqueue_receipt(receipt_id))
    assert spy.calls == [("vietreceipt.process_receipt", [str(receipt_id)])]


def test_duplicate_delivery_creates_one_attempt(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    service = orchestrator(factory)
    first = asyncio.run(service.process(receipt_id, delivery_id="delivery-1"))
    second = asyncio.run(service.process(receipt_id, delivery_id="delivery-2"))
    assert first.outcome is ProcessingOutcome.SUCCEEDED
    assert second.outcome is ProcessingOutcome.NOT_CLAIMED
    assert counts(factory) == (1, 1, 1)
    session = factory()
    receipt = asyncio.run(SQLAlchemyReceiptRepository(session).get(receipt_id))
    session.close()
    assert receipt.status is ReceiptStatus.NEEDS_REVIEW
    assert receipt.latest_ocr_run_id is not None
    assert receipt.latest_kie_run_id is not None


def test_two_workers_race_only_one_claims(tmp_path):
    factory, receipt_id = setup_database(tmp_path)

    def claim(delivery):
        async def run():
            async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
                item = await uow.processing.claim(
                    receipt_id,
                    delivery_id=delivery,
                    attempt_id=uuid4(),
                    ocr_run_id=uuid4(),
                    kie_run_id=uuid4(),
                    started_at=datetime.now(timezone.utc),
                )
                if item:
                    await uow.commit()
                return item
        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["race-a", "race-b"]))
    assert sum(item is not None for item in results) == 1
    assert counts(factory)[0] == 1


def test_redelivery_resumes_persisted_ocr_without_new_attempt(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    first_ocr = OCR()
    failing_kie = KIE(fail=True)
    first = asyncio.run(
        orchestrator(factory, first_ocr, failing_kie).process(
            receipt_id, delivery_id="same-celery-id"
        )
    )
    assert first.outcome is ProcessingOutcome.FAILED
    # A Celery retry is a new attempt because the old attempt is terminal.
    second_ocr = OCR()
    second = asyncio.run(
        orchestrator(factory, second_ocr, KIE()).process(
            receipt_id, delivery_id="same-celery-id"
        )
    )
    assert second.outcome is ProcessingOutcome.SUCCEEDED
    assert counts(factory) == (2, 2, 1)
    session = factory()
    attempts = session.scalars(select(ProcessingAttemptRecord)).all()
    session.close()
    assert len({item.ocr_run_id for item in attempts}) == 2
    assert len({item.kie_run_id for item in attempts}) == 2


def test_worker_restart_redelivery_resumes_active_attempt(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    delivery_id = "redelivered-celery-task"

    async def persist_checkpoint():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            attempt = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )
            assert attempt is not None
            payload = OCR()(b"image", receipt_id=receipt_id, ocr_run_id=attempt.ocr_run_id)
            await uow.processing.append_ocr_output(
                attempt, payload, created_at=datetime.now(timezone.utc)
            )
            await uow.commit()

    asyncio.run(persist_checkpoint())
    must_not_run = OCR(fail=True)
    result = asyncio.run(
        orchestrator(factory, must_not_run, KIE()).process(
            receipt_id, delivery_id=delivery_id
        )
    )
    assert result.outcome is ProcessingOutcome.SUCCEEDED
    assert must_not_run.calls == 0
    assert counts(factory) == (1, 1, 1)


def test_invalid_ocr_schema_is_not_persisted_as_success(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    result = asyncio.run(
        orchestrator(factory, OCR(invalid=True), KIE()).process(
            receipt_id, delivery_id="invalid-ocr"
        )
    )
    assert result.outcome is ProcessingOutcome.FAILED
    assert result.retryable is False
    assert counts(factory) == (1, 0, 0)


def test_provider_exception_is_persisted_as_typed_safe_error(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    result = asyncio.run(
        orchestrator(factory, OCR(fail=True), KIE()).process(
            receipt_id, delivery_id="provider-error"
        )
    )
    assert result.outcome is ProcessingOutcome.FAILED
    assert result.retryable is True
    session = factory()
    receipt = asyncio.run(SQLAlchemyReceiptRepository(session).get(receipt_id))
    session.close()
    assert receipt.last_error.code == "OCR_PROVIDER_FAILED"
    assert receipt.last_error.message == "OCR processing failed."
    assert "secret" not in receipt.last_error.message


def test_invalid_kie_schema_keeps_ocr_but_not_kie(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    result = asyncio.run(
        orchestrator(factory, OCR(), KIE(invalid=True)).process(
            receipt_id, delivery_id="invalid-kie"
        )
    )
    assert result.outcome is ProcessingOutcome.FAILED
    assert result.retryable is False
    assert counts(factory) == (1, 1, 0)

def test_same_delivery_id_reuses_same_active_attempt(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    delivery_id = "shared-delivery-id"

    async def claim_twice():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            first = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )
            assert first is not None
            await uow.commit()

        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            second = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )
            assert second is not None
            await uow.commit()

        return first, second

    first, second = asyncio.run(claim_twice())

    assert second.attempt_id == first.attempt_id
    assert second.ocr_run_id == first.ocr_run_id
    assert second.kie_run_id == first.kie_run_id
    assert counts(factory)[0] == 1


def test_stale_worker_cannot_overwrite_terminal_transition(tmp_path):
    factory, receipt_id = setup_database(tmp_path)
    delivery_id = "shared-terminal-delivery"

    async def prepare_terminal_attempt():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            active = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )
            assert active is not None
            await uow.commit()

        # Simulate a second worker holding the same delivery/attempt identity.
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            stale = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=uuid4(),
                ocr_run_id=uuid4(),
                kie_run_id=uuid4(),
                started_at=datetime.now(timezone.utc),
            )
            assert stale is not None
            await uow.commit()

        assert stale.attempt_id == active.attempt_id

        ocr_payload = OCR()(
            b"image",
            receipt_id=receipt_id,
            ocr_run_id=active.ocr_run_id,
        )
        kie_payload = KIE()(
            ocr_payload,
            kie_run_id=active.kie_run_id,
        )

        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            await uow.processing.append_ocr_output(
                active,
                ocr_payload,
                created_at=datetime.now(timezone.utc),
            )
            await uow.processing.append_kie_output_and_complete(
                active,
                kie_payload,
                completed_at=datetime.now(timezone.utc),
            )
            await uow.commit()

        return stale, kie_payload

    stale, kie_payload = asyncio.run(prepare_terminal_attempt())

    async def stale_success():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            await uow.processing.append_kie_output_and_complete(
                stale,
                kie_payload,
                completed_at=datetime.now(timezone.utc),
            )

    try:
        asyncio.run(stale_success())
    except StaleUpdate:
        pass
    else:
        raise AssertionError(
            "Stale worker must not report a second successful completion."
        )

    error = ProcessingError(
        stage=ErrorStage.PERSISTING,
        code="STALE_WORKER",
        message="Stale worker must not overwrite terminal state.",
        retryable=True,
        occurred_at=datetime.now(timezone.utc),
    )

    async def stale_failure():
        async with SQLAlchemyUnitOfWorkFactory(factory)() as uow:
            await uow.processing.mark_failed(stale, error)

    try:
        asyncio.run(stale_failure())
    except StaleUpdate:
        pass
    else:
        raise AssertionError(
            "Stale worker must not overwrite SUCCEEDED with FAILED."
        )

    session = factory()
    attempt_record = session.get(
        ProcessingAttemptRecord,
        stale.attempt_id,
    )
    receipt = asyncio.run(
        SQLAlchemyReceiptRepository(session).get(receipt_id)
    )
    session.close()

    assert attempt_record.status == "SUCCEEDED"
    assert receipt.status is ReceiptStatus.NEEDS_REVIEW
    assert counts(factory) == (1, 1, 1)

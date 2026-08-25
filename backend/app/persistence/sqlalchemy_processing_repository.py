from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.domain.enums import ProcessingStage, ReceiptStatus
from backend.app.domain.errors import PersistenceFailure, StaleUpdate
from backend.app.domain.models import ProcessingAttempt, ProcessingError

from .models import KIERunRecord, OCRRunRecord, ProcessingAttemptRecord, ReceiptRecord


def _aware(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=timezone.utc)


def _to_domain(record: ProcessingAttemptRecord) -> ProcessingAttempt:
    return ProcessingAttempt(
        attempt_id=record.attempt_id,
        receipt_id=record.receipt_id,
        delivery_id=record.delivery_id,
        ocr_run_id=record.ocr_run_id,
        kie_run_id=record.kie_run_id,
        status=record.status,
        stage=ProcessingStage(record.stage),
        started_at=_aware(record.started_at),
        finished_at=_aware(record.finished_at),
        error=(ProcessingError.model_validate(record.error) if record.error else None),
    )


class SQLAlchemyProcessingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def claim(
        self,
        receipt_id: UUID,
        *,
        delivery_id: str,
        attempt_id: UUID,
        ocr_run_id: UUID,
        kie_run_id: UUID,
        started_at: datetime,
    ) -> ProcessingAttempt | None:
        try:
            # Celery redelivery keeps the task id. Resume the same immutable
            # attempt; a separately delivered duplicate has a different id.
            active = self._session.scalar(
                select(ProcessingAttemptRecord).where(
                    ProcessingAttemptRecord.active_receipt_id == receipt_id,
                    ProcessingAttemptRecord.delivery_id == delivery_id,
                    ProcessingAttemptRecord.status == "ACTIVE",
                )
            )
            if active is not None:
                return _to_domain(active)

            retryable_failure = and_(
                ReceiptRecord.status == ReceiptStatus.FAILED.value,
                ReceiptRecord.last_error.is_not(None),
                ReceiptRecord.last_error["retryable"].as_boolean().is_(True),
            )
            statement = (
                update(ReceiptRecord)
                .where(
                    ReceiptRecord.receipt_id == receipt_id,
                    or_(
                        ReceiptRecord.status == ReceiptStatus.UPLOADED.value,
                        retryable_failure,
                    ),
                )
                .values(
                    status=ReceiptStatus.PROCESSING.value,
                    processing_stage=ProcessingStage.PREPROCESSING.value,
                    last_error=None,
                    updated_at=started_at,
                )
            )
            if self._session.execute(statement).rowcount != 1:
                return None

            record = ProcessingAttemptRecord(
                attempt_id=attempt_id,
                receipt_id=receipt_id,
                active_receipt_id=receipt_id,
                delivery_id=delivery_id,
                ocr_run_id=ocr_run_id,
                kie_run_id=kie_run_id,
                status="ACTIVE",
                stage=ProcessingStage.PREPROCESSING.value,
                started_at=started_at,
            )
            self._session.add(record)
            self._session.flush()
            return _to_domain(record)
        except IntegrityError:
            # The unique active_receipt_id constraint is the final guard if
            # two database transactions pass a stale read concurrently.
            self._session.rollback()
            return None
        except SQLAlchemyError as exc:
            raise PersistenceFailure("Could not claim receipt processing.") from exc

    async def get_ocr_output(self, ocr_run_id: UUID) -> dict | None:
        try:
            record = self._session.get(OCRRunRecord, ocr_run_id)
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not load OCR run output."
            ) from exc
        return dict(record.payload) if record else None

    async def append_ocr_output(
        self,
        attempt: ProcessingAttempt,
        payload: dict,
        *,
        created_at: datetime,
    ) -> None:
        try:
            existing = self._session.get(
                OCRRunRecord,
                attempt.ocr_run_id,
            )
            if existing is not None:
                if (
                    existing.attempt_id != attempt.attempt_id
                    or existing.receipt_id != attempt.receipt_id
                ):
                    raise StaleUpdate(
                        "OCR run identity does not match processing attempt."
                    )
                return

            attempt_result = self._session.execute(
                update(ProcessingAttemptRecord)
                .where(
                    ProcessingAttemptRecord.attempt_id == attempt.attempt_id,
                    ProcessingAttemptRecord.status == "ACTIVE",
                )
                .values(stage=ProcessingStage.KIE.value)
            )
            if attempt_result.rowcount != 1:
                raise StaleUpdate(
                    "Processing attempt is no longer active "
                    "for OCR checkpoint."
                )

            receipt_result = self._session.execute(
                update(ReceiptRecord)
                .where(
                    ReceiptRecord.receipt_id == attempt.receipt_id,
                    ReceiptRecord.status == ReceiptStatus.PROCESSING.value,
                )
                .values(
                    processing_stage=ProcessingStage.KIE.value,
                    latest_ocr_run_id=attempt.ocr_run_id,
                    updated_at=created_at,
                )
            )
            if receipt_result.rowcount != 1:
                raise StaleUpdate(
                    "Receipt is no longer PROCESSING "
                    "for OCR checkpoint."
                )

            self._session.add(
                OCRRunRecord(
                    ocr_run_id=attempt.ocr_run_id,
                    attempt_id=attempt.attempt_id,
                    receipt_id=attempt.receipt_id,
                    payload=payload,
                    created_at=created_at,
                )
            )
            self._session.flush()
        except StaleUpdate:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not append OCR run output."
            ) from exc

    async def get_kie_output(self, kie_run_id: UUID) -> dict | None:
        try:
            record = self._session.get(KIERunRecord, kie_run_id)
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not load KIE run output."
            ) from exc
        return dict(record.payload) if record else None

    async def append_kie_output_and_complete(
        self,
        attempt: ProcessingAttempt,
        payload: dict,
        *,
        completed_at: datetime,
    ) -> None:
        try:
            attempt_result = self._session.execute(
                update(ProcessingAttemptRecord)
                .where(
                    ProcessingAttemptRecord.attempt_id == attempt.attempt_id,
                    ProcessingAttemptRecord.status == "ACTIVE",
                )
                .values(
                    status="SUCCEEDED",
                    stage=ProcessingStage.PERSISTING.value,
                    active_receipt_id=None,
                    finished_at=completed_at,
                )
            )
            if attempt_result.rowcount != 1:
                raise StaleUpdate(
                    "Processing attempt is no longer active "
                    "for successful completion."
                )

            receipt_result = self._session.execute(
                update(ReceiptRecord)
                .where(
                    ReceiptRecord.receipt_id == attempt.receipt_id,
                    ReceiptRecord.status == ReceiptStatus.PROCESSING.value,
                )
                .values(
                    status=ReceiptStatus.NEEDS_REVIEW.value,
                    processing_stage=None,
                    latest_ocr_run_id=attempt.ocr_run_id,
                    latest_kie_run_id=attempt.kie_run_id,
                    processed_at=completed_at,
                    updated_at=completed_at,
                    last_error=None,
                )
            )
            if receipt_result.rowcount != 1:
                raise StaleUpdate(
                    "Receipt is no longer PROCESSING "
                    "for successful completion."
                )

            existing = self._session.get(
                KIERunRecord,
                attempt.kie_run_id,
            )
            if existing is None:
                self._session.add(
                    KIERunRecord(
                        kie_run_id=attempt.kie_run_id,
                        attempt_id=attempt.attempt_id,
                        receipt_id=attempt.receipt_id,
                        source_ocr_run_id=attempt.ocr_run_id,
                        payload=payload,
                        created_at=completed_at,
                    )
                )
            elif (
                existing.attempt_id != attempt.attempt_id
                or existing.receipt_id != attempt.receipt_id
            ):
                raise StaleUpdate(
                    "KIE run identity does not match processing attempt."
                )

            self._session.flush()
        except StaleUpdate:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not append KIE run output."
            ) from exc

    async def mark_failed(
        self,
        attempt: ProcessingAttempt,
        error: ProcessingError,
    ) -> None:
        try:
            attempt_result = self._session.execute(
                update(ProcessingAttemptRecord)
                .where(
                    ProcessingAttemptRecord.attempt_id == attempt.attempt_id,
                    ProcessingAttemptRecord.status == "ACTIVE",
                )
                .values(
                    status="FAILED",
                    stage=error.stage.value,
                    active_receipt_id=None,
                    finished_at=error.occurred_at,
                    error=error.model_dump(mode="json"),
                )
            )
            if attempt_result.rowcount != 1:
                raise StaleUpdate(
                    "Processing attempt is no longer active "
                    "for failure transition."
                )

            receipt_result = self._session.execute(
                update(ReceiptRecord)
                .where(
                    ReceiptRecord.receipt_id == attempt.receipt_id,
                    ReceiptRecord.status == ReceiptStatus.PROCESSING.value,
                )
                .values(
                    status=ReceiptStatus.FAILED.value,
                    processing_stage=None,
                    last_error=error.model_dump(mode="json"),
                    updated_at=error.occurred_at,
                )
            )
            if receipt_result.rowcount != 1:
                raise StaleUpdate(
                    "Receipt is no longer PROCESSING "
                    "for failure transition."
                )

            self._session.flush()
        except StaleUpdate:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not persist processing failure."
            ) from exc

    async def reap_stale_attempts(
        self,
        *,
        stale_before: datetime,
        failed_at: datetime,
        error: ProcessingError,
    ) -> int:
        try:
            candidates = self._session.scalars(
                select(ProcessingAttemptRecord)
                .join(
                    ReceiptRecord,
                    ReceiptRecord.receipt_id
                    == ProcessingAttemptRecord.receipt_id,
                )
                .where(
                    ProcessingAttemptRecord.status == "ACTIVE",
                    ProcessingAttemptRecord.started_at <= stale_before,
                    ReceiptRecord.status
                    == ReceiptStatus.PROCESSING.value,
                )
                .with_for_update(skip_locked=True)
            ).all()

            recovered = 0
            error_payload = error.model_dump(mode="json")

            for record in candidates:
                attempt_result = self._session.execute(
                    update(ProcessingAttemptRecord)
                    .where(
                        ProcessingAttemptRecord.attempt_id
                        == record.attempt_id,
                        ProcessingAttemptRecord.status == "ACTIVE",
                        ProcessingAttemptRecord.started_at
                        <= stale_before,
                    )
                    .values(
                        status="FAILED",
                        stage=error.stage.value,
                        active_receipt_id=None,
                        finished_at=failed_at,
                        error=error_payload,
                    )
                    .execution_options(
                        synchronize_session=False
                    )
                )
                if attempt_result.rowcount != 1:
                    continue

                receipt_result = self._session.execute(
                    update(ReceiptRecord)
                    .where(
                        ReceiptRecord.receipt_id
                        == record.receipt_id,
                        ReceiptRecord.status
                        == ReceiptStatus.PROCESSING.value,
                    )
                    .values(
                        status=ReceiptStatus.FAILED.value,
                        processing_stage=None,
                        last_error=error_payload,
                        updated_at=failed_at,
                    )
                    .execution_options(
                        synchronize_session=False
                    )
                )
                if receipt_result.rowcount != 1:
                    raise StaleUpdate(
                        "Receipt changed while recovering stale "
                        "processing attempt."
                    )

                recovered += 1

            self._session.flush()
            return recovered
        except StaleUpdate:
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not recover stale processing attempts."
            ) from exc

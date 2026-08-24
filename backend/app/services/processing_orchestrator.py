from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any
from uuid import UUID

from backend.app.domain.enums import ErrorStage
from backend.app.domain.models import ProcessingAttempt, ProcessingError
from backend.app.ports.clock import Clock
from backend.app.ports.ids import IdGenerator
from backend.app.ports.processing import KIEProvider, OCRProvider, ReceiptImageLoader
from backend.app.repositories.protocols import UnitOfWorkFactory
from backend.app.services.canonical_validation import is_schema_valid


class ProcessingOutcome(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    NOT_CLAIMED = "NOT_CLAIMED"


@dataclass(frozen=True, slots=True)
class ProcessingResult:
    outcome: ProcessingOutcome
    receipt_id: UUID
    attempt_id: UUID | None = None
    retryable: bool = False


class ProcessingOrchestrator:
    def __init__(
        self,
        *,
        unit_of_work_factory: UnitOfWorkFactory,
        image_loader: ReceiptImageLoader,
        ocr_provider: OCRProvider,
        kie_provider: KIEProvider,
        id_generator: IdGenerator,
        clock: Clock,
    ) -> None:
        self._uow_factory = unit_of_work_factory
        self._image_loader = image_loader
        self._ocr_provider = ocr_provider
        self._kie_provider = kie_provider
        self._ids = id_generator
        self._clock = clock

    async def process(self, receipt_id: UUID, *, delivery_id: str) -> ProcessingResult:
        attempt = await self._claim(receipt_id, delivery_id)
        if attempt is None:
            return ProcessingResult(ProcessingOutcome.NOT_CLAIMED, receipt_id)

        ocr_result = await self._load_ocr(attempt)
        if ocr_result is None:
            try:
                image = await self._image_loader.load(receipt_id)
            except Exception:
                return await self._fail(
                    attempt,
                    stage=ErrorStage.PREPROCESSING,
                    code="RECEIPT_IMAGE_UNAVAILABLE",
                    message="Receipt image could not be loaded.",
                    retryable=True,
                )

            try:
                candidate = self._ocr_provider(
                    image,
                    receipt_id=receipt_id,
                    ocr_run_id=attempt.ocr_run_id,
                )
            except Exception:
                return await self._fail(
                    attempt,
                    stage=ErrorStage.OCR,
                    code="OCR_PROVIDER_FAILED",
                    message="OCR processing failed.",
                    retryable=True,
                )

            if not self._valid_ocr(candidate, attempt):
                return await self._fail(
                    attempt,
                    stage=ErrorStage.OCR,
                    code="OCR_SCHEMA_INVALID",
                    message="OCR returned an invalid canonical result.",
                    retryable=False,
                )
            ocr_result = candidate
            try:
                async with self._uow_factory() as uow:
                    await uow.processing.append_ocr_output(
                        attempt, ocr_result, created_at=self._clock.now()
                    )
                    await uow.commit()
            except Exception:
                return await self._fail(
                    attempt,
                    stage=ErrorStage.PERSISTING,
                    code="OCR_PERSISTENCE_FAILED",
                    message="OCR output could not be persisted.",
                    retryable=True,
                )

        kie_result = await self._load_kie(attempt)
        if kie_result is None:
            try:
                candidate = self._kie_provider(
                    ocr_result,
                    kie_run_id=attempt.kie_run_id,
                )
            except Exception:
                return await self._fail(
                    attempt,
                    stage=ErrorStage.KIE,
                    code="KIE_PROVIDER_FAILED",
                    message="KIE processing failed.",
                    retryable=True,
                )
            if not self._valid_kie(candidate, attempt):
                return await self._fail(
                    attempt,
                    stage=ErrorStage.KIE,
                    code="KIE_SCHEMA_INVALID",
                    message="KIE returned an invalid canonical result.",
                    retryable=False,
                )
            kie_result = candidate

        try:
            async with self._uow_factory() as uow:
                await uow.processing.append_kie_output_and_complete(
                    attempt, kie_result, completed_at=self._clock.now()
                )
                await uow.commit()
        except Exception:
            return await self._fail(
                attempt,
                stage=ErrorStage.PERSISTING,
                code="KIE_PERSISTENCE_FAILED",
                message="KIE output could not be persisted.",
                retryable=True,
            )
        return ProcessingResult(
            ProcessingOutcome.SUCCEEDED,
            receipt_id,
            attempt_id=attempt.attempt_id,
        )

    async def _claim(
        self, receipt_id: UUID, delivery_id: str
    ) -> ProcessingAttempt | None:
        now = self._clock.now()
        async with self._uow_factory() as uow:
            attempt = await uow.processing.claim(
                receipt_id,
                delivery_id=delivery_id,
                attempt_id=self._ids.new_id(),
                ocr_run_id=self._ids.new_id(),
                kie_run_id=self._ids.new_id(),
                started_at=now,
            )
            if attempt is not None:
                await uow.commit()
            return attempt

    async def _load_ocr(self, attempt: ProcessingAttempt) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.processing.get_ocr_output(attempt.ocr_run_id)

    async def _load_kie(self, attempt: ProcessingAttempt) -> dict[str, Any] | None:
        async with self._uow_factory() as uow:
            return await uow.processing.get_kie_output(attempt.kie_run_id)

    async def _fail(
        self,
        attempt: ProcessingAttempt,
        *,
        stage: ErrorStage,
        code: str,
        message: str,
        retryable: bool,
    ) -> ProcessingResult:
        error = ProcessingError(
            stage=stage,
            code=code,
            message=message,
            retryable=retryable,
            occurred_at=self._clock.now(),
        )
        async with self._uow_factory() as uow:
            await uow.processing.mark_failed(attempt, error)
            await uow.commit()
        return ProcessingResult(
            ProcessingOutcome.FAILED,
            attempt.receipt_id,
            attempt_id=attempt.attempt_id,
            retryable=retryable,
        )

    @staticmethod
    def _valid_ocr(payload: Any, attempt: ProcessingAttempt) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            return (
                is_schema_valid(payload, kind="ocr")
                and payload["receipt_id"] == str(attempt.receipt_id)
                and payload["ocr_run_id"] == str(attempt.ocr_run_id)
            )
        except (KeyError, TypeError, ValueError):
            return False

    @staticmethod
    def _valid_kie(payload: Any, attempt: ProcessingAttempt) -> bool:
        if not isinstance(payload, dict):
            return False
        try:
            return (
                is_schema_valid(payload, kind="kie")
                and payload["receipt_id"] == str(attempt.receipt_id)
                and payload["kie_run_id"] == str(attempt.kie_run_id)
                and payload["source_ocr_run_id"] == str(attempt.ocr_run_id)
            )
        except (KeyError, TypeError, ValueError):
            return False

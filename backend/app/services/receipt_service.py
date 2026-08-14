from backend.app.repositories.protocols import (
    UnitOfWork,
    UnitOfWorkFactory,
)
from uuid import UUID

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
from backend.app.ports.clock import Clock
from backend.app.ports.persistence import (
    ReceiptPersistenceService,
    ReceiptUpload,
)
from backend.app.ports.scheduler import ProcessingScheduler
from backend.app.repositories.protocols import UnitOfWork





class ReceiptService:
    def __init__(
        self,
        *,
        persistence: ReceiptPersistenceService,
        scheduler: ProcessingScheduler,
        unit_of_work_factory: UnitOfWorkFactory,
        clock: Clock,
    ) -> None:
        self._persistence = persistence
        self._scheduler = scheduler
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    async def upload_receipt(
        self,
        upload: ReceiptUpload,
    ) -> Receipt:
        try:
            receipt = await self._persistence.persist_upload(upload)
        except PersistenceFailure:
            raise
        except Exception as error:
            raise PersistenceFailure(
                "Receipt persistence failed."
            ) from error

        if receipt.status is not ReceiptStatus.UPLOADED:
            raise InvalidReceiptState(
                receipt.status,
                ReceiptStatus.UPLOADED,
            )

        try:
            await self._scheduler.enqueue_receipt(
                receipt.receipt_id
            )
        except Exception:
            return await self._record_scheduling_failure(
                receipt,
                code="INITIAL_SCHEDULING_FAILED",
                message="Receipt processing could not be scheduled.",
            )

        return receipt

    async def retry_receipt(self, receipt_id: UUID) -> UUID:
        async with self._unit_of_work_factory() as unit_of_work:
            receipt = await unit_of_work.receipts.get(receipt_id)

        if receipt is None:
            raise ReceiptNotFound(
                f"Receipt {receipt_id} was not found."
            )

        if receipt.status is not ReceiptStatus.FAILED:
            raise InvalidReceiptState(
                receipt.status,
                operation="retry",
            )

        if (
            receipt.last_error is None
            or not receipt.last_error.retryable
        ):
            raise InvalidReceiptState(
                receipt.status,
                operation="retry_non_retryable_failure",
            )

        try:
            await self._scheduler.enqueue_receipt(receipt_id)
        except Exception as error:
            failed_receipt = (
                await self._record_scheduling_failure(
                    receipt,
                    code="RETRY_SCHEDULING_FAILED",
                    message=(
                        "Receipt retry could not be scheduled."
                    ),
                )
            )

            scheduling_error = SchedulingFailure(
                "Receipt retry scheduling failed."
            )
            scheduling_error.receipt = failed_receipt
            raise scheduling_error from error

        # HTTP 202 means accepted for scheduling only.
        # The receipt remains FAILED until a worker claims the retry.
        return receipt_id

    async def _record_scheduling_failure(
        self,
        receipt: Receipt,
        *,
        code: str,
        message: str,
    ) -> Receipt:
        occurred_at = self._clock.now()

        scheduling_error = ProcessingError(
            stage=ErrorStage.SCHEDULING,
            code=code,
            message=message,
            retryable=True,
            occurred_at=occurred_at,
        )

        failed_receipt = receipt.model_copy(
            update={
                "status": ReceiptStatus.FAILED,
                "processing_stage": None,
                "last_error": scheduling_error,
                "updated_at": occurred_at,
            }
        )

        async with self._unit_of_work_factory() as unit_of_work:
            saved_receipt = await unit_of_work.receipts.save(
                failed_receipt,
                expected_updated_at=receipt.updated_at,
            )
            await unit_of_work.commit()

        return saved_receipt

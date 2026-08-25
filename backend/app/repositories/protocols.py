from datetime import datetime
from types import TracebackType
from typing import (
    Callable,
    Protocol,
    Self,
    Sequence,
    runtime_checkable,
)
from uuid import UUID

from backend.app.domain.enums import FieldName, ReceiptStatus
from backend.app.domain.models import (
    AuditEvent,
    CorrectionHistory,
    ExtractedField,
    Receipt,
    ProcessingAttempt,
)



@runtime_checkable
class ReceiptRepository(Protocol):
    async def create(self, receipt: Receipt) -> Receipt:
        ...

    async def get(self, receipt_id: UUID) -> Receipt | None:
        ...

    async def list_receipts(
        self,
        *,
        page: int,
        page_size: int,
        status: ReceiptStatus | None = None,
    ) -> Sequence[Receipt]:
        ...

    async def save(
        self,
        receipt: Receipt,
        *,
        expected_updated_at: datetime,
    ) -> Receipt:
        ...


@runtime_checkable
class ProcessingRepository(Protocol):
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
        ...

    async def get_ocr_output(self, ocr_run_id: UUID) -> dict | None:
        ...

    async def append_ocr_output(
        self,
        attempt: ProcessingAttempt,
        payload: dict,
        *,
        created_at: datetime,
    ) -> None:
        ...

    async def get_kie_output(self, kie_run_id: UUID) -> dict | None:
        ...

    async def append_kie_output_and_complete(
        self,
        attempt: ProcessingAttempt,
        payload: dict,
        *,
        completed_at: datetime,
    ) -> None:
        ...

    async def mark_failed(
        self,
        attempt: ProcessingAttempt,
        error: "ProcessingError",
    ) -> None:
        ...

    async def reap_stale_attempts(
        self,
        *,
        stale_before: datetime,
        failed_at: datetime,
        error: "ProcessingError",
    ) -> int:
        ...

@runtime_checkable
class FieldRepository(Protocol):
    async def get(
        self,
        receipt_id: UUID,
        field_name: FieldName,
    ) -> ExtractedField | None:
        ...

    async def list_for_receipt(
        self,
        receipt_id: UUID,
        *,
        kie_run_id: UUID | None = None,
    ) -> Sequence[ExtractedField]:
        ...

    async def save(
        self,
        field: ExtractedField,
        *,
        expected_updated_at: datetime,
    ) -> ExtractedField:
        ...

@runtime_checkable
class CorrectionHistoryRepository(Protocol):
    async def append(self, record: CorrectionHistory) -> None:
        ...

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> Sequence[CorrectionHistory]:
        ...


@runtime_checkable
class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> None:
        ...

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> Sequence[AuditEvent]:
        ...


@runtime_checkable
class UnitOfWork(Protocol):
    receipts: ReceiptRepository
    processing: ProcessingRepository
    fields: FieldRepository
    correction_history: CorrectionHistoryRepository
    audit_events: AuditEventRepository

    async def __aenter__(self) -> Self:
        ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...
UnitOfWorkFactory = Callable[[], UnitOfWork]

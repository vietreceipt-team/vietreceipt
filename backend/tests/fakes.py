from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Self
from uuid import UUID

from backend.app.domain.enums import FieldName, ReceiptStatus
from backend.app.domain.errors import StaleUpdate
from backend.app.domain.models import (
    AuditEvent,
    CorrectionHistory,
    ExtractedField,
    Receipt,
)
from backend.app.ports.persistence import ReceiptUpload


class FixedClock:
    def __init__(self, current: datetime) -> None:
        self.current = current

    def now(self) -> datetime:
        return self.current


class FakeProcessingScheduler:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.enqueued_receipt_ids: list[UUID] = []

    async def enqueue_receipt(self, receipt_id: UUID) -> None:
        if self.should_fail:
            raise RuntimeError("queue unavailable")

        self.enqueued_receipt_ids.append(receipt_id)


class FakeReceiptRepository:
    def __init__(
        self,
        receipts: Sequence[Receipt] = (),
    ) -> None:
        self.items = {
            receipt.receipt_id: receipt
            for receipt in receipts
        }

    async def create(self, receipt: Receipt) -> Receipt:
        self.items[receipt.receipt_id] = receipt
        return receipt

    async def get(self, receipt_id: UUID) -> Receipt | None:
        return self.items.get(receipt_id)

    async def list_receipts(
        self,
        *,
        page: int,
        page_size: int,
        status: ReceiptStatus | None = None,
    ) -> Sequence[Receipt]:
        receipts = list(self.items.values())

        if status is not None:
            receipts = [
                receipt
                for receipt in receipts
                if receipt.status is status
            ]

        start = (page - 1) * page_size
        return receipts[start:start + page_size]

    async def save(
        self,
        receipt: Receipt,
        *,
        expected_updated_at: datetime,
    ) -> Receipt:
        current = self.items.get(receipt.receipt_id)

        if (
            current is not None
            and current.updated_at != expected_updated_at
        ):
            raise StaleUpdate(
                "Receipt was updated by another request."
            )

        self.items[receipt.receipt_id] = receipt
        return receipt

class FakeFieldRepository:
    def __init__(
        self,
        fields: Sequence[ExtractedField] = (),
    ) -> None:
        self.items = {
            (field.receipt_id, field.field_name): field
            for field in fields
        }

    async def get(
        self,
        receipt_id: UUID,
        field_name: FieldName,
    ) -> ExtractedField | None:
        return self.items.get((receipt_id, field_name))

    async def list_for_receipt(
        self,
        receipt_id: UUID,
        *,
        kie_run_id: UUID | None = None,
    ) -> Sequence[ExtractedField]:
        fields = [
            field
            for field in self.items.values()
            if field.receipt_id == receipt_id
        ]

        if kie_run_id is not None:
            fields = [
                field
                for field in fields
                if field.kie_run_id == kie_run_id
            ]

        return fields

    async def save(
        self,
        field: ExtractedField,
        *,
        expected_updated_at: datetime,
    ) -> ExtractedField:
        key = (field.receipt_id, field.field_name)
        current = self.items.get(key)

        if (
            current is not None
            and current.updated_at != expected_updated_at
        ):
            raise StaleUpdate(
                "Field was updated by another request."
            )

        self.items[key] = field
        return field

class FakeCorrectionHistoryRepository:
    def __init__(self) -> None:
        self.records: list[CorrectionHistory] = []

    async def append(
        self,
        record: CorrectionHistory,
    ) -> None:
        self.records.append(record)

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> Sequence[CorrectionHistory]:
        return [
            record
            for record in self.records
            if record.receipt_id == receipt_id
        ]


class FakeAuditEventRepository:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def append(self, event: AuditEvent) -> None:
        self.events.append(event)

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> Sequence[AuditEvent]:
        return [
            event
            for event in self.events
            if event.receipt_id == receipt_id
        ]


class FakeUnitOfWork:
    def __init__(
        self,
        receipts: Sequence[Receipt] = (),
        fields: Sequence[ExtractedField] = (),
    ) -> None:
        self.receipts = FakeReceiptRepository(receipts)
        self.fields = FakeFieldRepository(fields)
        self.correction_history = (
            FakeCorrectionHistoryRepository()
        )
        self.audit_events = FakeAuditEventRepository()
        self.commit_count = 0
        self.rollback_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None:
            await self.rollback()

    async def commit(self) -> None:
        self.commit_count += 1

    async def rollback(self) -> None:
        self.rollback_count += 1


class FakeReceiptPersistenceService:
    def __init__(
        self,
        *,
        receipt: Receipt,
        repository: FakeReceiptRepository,
        error: Exception | None = None,
    ) -> None:
        self.receipt = receipt
        self.repository = repository
        self.error = error
        self.uploads: list[ReceiptUpload] = []

    async def persist_upload(
        self,
        upload: ReceiptUpload,
    ) -> Receipt:
        self.uploads.append(upload)

        if self.error is not None:
            raise self.error

        return await self.repository.create(self.receipt)

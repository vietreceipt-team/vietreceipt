from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import PersistenceFailure, StaleUpdate
from backend.app.domain.models import Receipt

from .models import ReceiptRecord


class SQLAlchemyReceiptRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def create(self, receipt: Receipt) -> Receipt:
        raise PersistenceFailure(
            "Receipt creation requires storage metadata; "
            "use create_with_storage() from the persistence adapter."
        )

    async def create_with_storage(
        self,
        receipt: Receipt,
        *,
        storage_key: str,
        content_type: str,
    ) -> Receipt:
        record = ReceiptRecord.from_domain(
            receipt,
            storage_key=storage_key,
            content_type=content_type,
        )
        try:
            self._session.add(record)
            self._session.flush()
            return record.to_domain()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not persist receipt metadata."
            ) from exc

    async def get(self, receipt_id: UUID) -> Receipt | None:
        try:
            record = self._session.get(ReceiptRecord, receipt_id)
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not read receipt metadata."
            ) from exc
        return record.to_domain() if record is not None else None

    async def get_storage_metadata(
        self,
        receipt_id: UUID,
    ) -> tuple[str, str] | None:
        try:
            record = self._session.get(ReceiptRecord, receipt_id)
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not read receipt storage metadata."
            ) from exc
        if record is None:
            return None
        return record.storage_key, record.content_type

    async def list_receipts(
        self,
        *,
        page: int,
        page_size: int,
        status: ReceiptStatus | None = None,
    ) -> list[Receipt]:
        statement = select(ReceiptRecord).order_by(
            ReceiptRecord.created_at.desc(),
            ReceiptRecord.receipt_id,
        )
        if status is not None:
            statement = statement.where(
                ReceiptRecord.status == status.value
            )
        statement = statement.offset((page - 1) * page_size).limit(page_size)

        try:
            records = self._session.scalars(statement).all()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not list receipt metadata."
            ) from exc
        return [record.to_domain() for record in records]

    async def save(
        self,
        receipt: Receipt,
        *,
        expected_updated_at: datetime,
    ) -> Receipt:
        try:
            record = self._session.get(ReceiptRecord, receipt.receipt_id)
            if record is None:
                raise PersistenceFailure(
                    f"Receipt {receipt.receipt_id} was not found for update."
                )
            record_updated_at = record.updated_at
            if record_updated_at.tzinfo is None:
                record_updated_at = record_updated_at.replace(tzinfo=timezone.utc)
            if record_updated_at != expected_updated_at:
                raise StaleUpdate(
                    "Receipt was updated by another request."
                )
            record.apply_domain(receipt)
            self._session.flush()
            return record.to_domain()
        except (PersistenceFailure, StaleUpdate):
            raise
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not update receipt metadata."
            ) from exc

    async def delete(self, receipt_id: UUID) -> bool:
        try:
            record = self._session.get(ReceiptRecord, receipt_id)
            if record is None:
                return False
            self._session.delete(record)
            self._session.flush()
            return True
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not delete receipt metadata."
            ) from exc

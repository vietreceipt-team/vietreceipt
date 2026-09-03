from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.domain.enums import (
    CorrectionOperation,
    FieldName,
    ValueStatus,
)
from backend.app.domain.errors import PersistenceFailure
from backend.app.domain.models import CorrectionHistory

from .models import CorrectionHistoryRecord


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_domain(
    record: CorrectionHistoryRecord,
) -> CorrectionHistory:
    return CorrectionHistory(
        correction_id=record.correction_id,
        receipt_id=record.receipt_id,
        field_name=FieldName(record.field_name),
        operation=CorrectionOperation(record.operation),
        kie_run_id=record.kie_run_id,
        old_value=record.old_value,
        new_value=record.new_value,
        old_status=(
            ValueStatus(record.old_status)
            if record.old_status is not None
            else None
        ),
        new_status=(
            ValueStatus(record.new_status)
            if record.new_status is not None
            else None
        ),
        changed_by=record.changed_by,
        changed_at=_aware(record.changed_at),
    )


class SQLAlchemyCorrectionHistoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def append(
        self,
        record: CorrectionHistory,
    ) -> None:
        persistence_record = CorrectionHistoryRecord(
            correction_id=record.correction_id,
            receipt_id=record.receipt_id,
            field_name=record.field_name.value,
            operation=record.operation.value,
            kie_run_id=record.kie_run_id,
            old_value=record.old_value,
            new_value=record.new_value,
            old_status=(
                record.old_status.value
                if record.old_status is not None
                else None
            ),
            new_status=(
                record.new_status.value
                if record.new_status is not None
                else None
            ),
            changed_by=record.changed_by,
            changed_at=record.changed_at,
        )

        try:
            self._session.add(persistence_record)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not append correction history."
            ) from exc

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> list[CorrectionHistory]:
        statement = (
            select(CorrectionHistoryRecord)
            .where(
                CorrectionHistoryRecord.receipt_id
                == receipt_id
            )
            .order_by(
                CorrectionHistoryRecord.changed_at,
                CorrectionHistoryRecord.correction_id,
            )
        )

        try:
            records = self._session.scalars(statement).all()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not list correction history."
            ) from exc

        return [_to_domain(record) for record in records]

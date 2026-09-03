from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
)
from backend.app.domain.errors import PersistenceFailure
from backend.app.domain.models import AuditEvent

from .models import AuditEventRecord


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _to_domain(record: AuditEventRecord) -> AuditEvent:
    return AuditEvent(
        event_id=record.event_id,
        receipt_id=record.receipt_id,
        event_type=AuditEventType(record.event_type),
        field_name=(
            FieldName(record.field_name)
            if record.field_name is not None
            else None
        ),
        operation=(
            CorrectionOperation(record.operation)
            if record.operation is not None
            else None
        ),
        actor_id=record.actor_id,
        occurred_at=_aware(record.occurred_at),
    )


class SQLAlchemyAuditEventRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    async def append(self, event: AuditEvent) -> None:
        persistence_record = AuditEventRecord(
            event_id=event.event_id,
            receipt_id=event.receipt_id,
            event_type=event.event_type.value,
            field_name=(
                event.field_name.value
                if event.field_name is not None
                else None
            ),
            operation=(
                event.operation.value
                if event.operation is not None
                else None
            ),
            actor_id=event.actor_id,
            occurred_at=event.occurred_at,
        )

        try:
            self._session.add(persistence_record)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not append audit event."
            ) from exc

    async def list_for_receipt(
        self,
        receipt_id: UUID,
    ) -> list[AuditEvent]:
        statement = (
            select(AuditEventRecord)
            .where(
                AuditEventRecord.receipt_id
                == receipt_id
            )
            .order_by(
                AuditEventRecord.occurred_at,
                AuditEventRecord.event_id,
            )
        )

        try:
            records = self._session.scalars(statement).all()
        except SQLAlchemyError as exc:
            raise PersistenceFailure(
                "Could not list audit events."
            ) from exc

        return [_to_domain(record) for record in records]

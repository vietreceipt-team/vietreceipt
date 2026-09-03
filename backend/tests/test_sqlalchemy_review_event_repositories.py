from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import (
    AuditEventType,
    CorrectionOperation,
    FieldName,
    ValueStatus,
)
from backend.app.domain.models import AuditEvent, CorrectionHistory
from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_audit_event_repository import (
    SQLAlchemyAuditEventRepository,
)
from backend.app.persistence.sqlalchemy_correction_history_repository import (
    SQLAlchemyCorrectionHistoryRepository,
)


@pytest.fixture()
def session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    try:
        yield factory
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_correction_history_append_and_list_are_ordered(
    session_factory,
):
    now = datetime.now(timezone.utc)
    receipt_id = uuid4()
    kie_run_id = uuid4()
    actor_id = uuid4()

    later = CorrectionHistory(
        correction_id=UUID(int=2),
        receipt_id=receipt_id,
        field_name=FieldName.MERCHANT_NAME,
        operation=CorrectionOperation.APPLY,
        kie_run_id=kie_run_id,
        old_value="Old Store",
        new_value="New Store",
        old_status=ValueStatus.PRESENT,
        new_status=ValueStatus.PRESENT,
        changed_by=actor_id,
        changed_at=now + timedelta(seconds=1),
    )

    earlier = CorrectionHistory(
        correction_id=UUID(int=1),
        receipt_id=receipt_id,
        field_name=FieldName.MERCHANT_NAME,
        operation=CorrectionOperation.APPLY,
        kie_run_id=kie_run_id,
        old_value=None,
        new_value="Old Store",
        old_status=ValueStatus.UNKNOWN,
        new_status=ValueStatus.PRESENT,
        changed_by=actor_id,
        changed_at=now,
    )

    with session_factory() as session:
        repository = SQLAlchemyCorrectionHistoryRepository(session)

        await repository.append(later)
        await repository.append(earlier)
        session.commit()

    with session_factory() as session:
        repository = SQLAlchemyCorrectionHistoryRepository(session)

        records = await repository.list_for_receipt(receipt_id)

    assert records == [earlier, later]


@pytest.mark.asyncio
async def test_audit_events_append_and_list_are_ordered(
    session_factory,
):
    now = datetime.now(timezone.utc)
    receipt_id = uuid4()
    actor_id = uuid4()

    later = AuditEvent(
        event_id=UUID(int=2),
        receipt_id=receipt_id,
        event_type=AuditEventType.RECEIPT_VERIFIED,
        actor_id=actor_id,
        occurred_at=now + timedelta(seconds=1),
    )

    earlier = AuditEvent(
        event_id=UUID(int=1),
        receipt_id=receipt_id,
        event_type=AuditEventType.REVIEW_STARTED,
        actor_id=actor_id,
        occurred_at=now,
    )

    with session_factory() as session:
        repository = SQLAlchemyAuditEventRepository(session)

        await repository.append(later)
        await repository.append(earlier)
        session.commit()

    with session_factory() as session:
        repository = SQLAlchemyAuditEventRepository(session)

        events = await repository.list_for_receipt(receipt_id)

    assert events == [earlier, later]

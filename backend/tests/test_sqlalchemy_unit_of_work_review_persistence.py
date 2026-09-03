from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_audit_event_repository import (
    SQLAlchemyAuditEventRepository,
)
from backend.app.persistence.sqlalchemy_correction_history_repository import (
    SQLAlchemyCorrectionHistoryRepository,
)
from backend.app.persistence.sqlalchemy_field_repository import (
    SQLAlchemyFieldRepository,
)
from backend.app.persistence.sqlalchemy_processing_repository import (
    SQLAlchemyProcessingRepository,
)
from backend.app.persistence.sqlalchemy_receipt_repository import (
    SQLAlchemyReceiptRepository,
)
from backend.app.persistence.sqlalchemy_unit_of_work import (
    SQLAlchemyUnitOfWork,
)


def test_sqlalchemy_unit_of_work_exposes_all_canonical_repositories():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    uow = SQLAlchemyUnitOfWork(factory)

    try:
        import asyncio

        async def check():
            async with uow:
                assert isinstance(
                    uow.receipts,
                    SQLAlchemyReceiptRepository,
                )
                assert isinstance(
                    uow.processing,
                    SQLAlchemyProcessingRepository,
                )
                assert isinstance(
                    uow.fields,
                    SQLAlchemyFieldRepository,
                )
                assert isinstance(
                    uow.correction_history,
                    SQLAlchemyCorrectionHistoryRepository,
                )
                assert isinstance(
                    uow.audit_events,
                    SQLAlchemyAuditEventRepository,
                )

        asyncio.run(check())
    finally:
        engine.dispose()


def test_sqlalchemy_unit_of_work_rolls_back_review_writes_on_error():
    import asyncio
    from datetime import datetime, timezone
    from uuid import uuid4

    import pytest
    from sqlalchemy import func, select

    from backend.app.domain.enums import (
        AuditEventType,
        CorrectionOperation,
        FieldName,
        ValueStatus,
    )
    from backend.app.domain.models import (
        AuditEvent,
        CorrectionHistory,
    )
    from backend.app.persistence.models import (
        AuditEventRecord,
        CorrectionHistoryRecord,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    receipt_id = uuid4()
    actor_id = uuid4()
    kie_run_id = uuid4()
    now = datetime.now(timezone.utc)

    history = CorrectionHistory(
        correction_id=uuid4(),
        receipt_id=receipt_id,
        field_name=FieldName.MERCHANT_NAME,
        operation=CorrectionOperation.APPLY,
        kie_run_id=kie_run_id,
        old_value=None,
        new_value="ABC Store",
        old_status=ValueStatus.UNKNOWN,
        new_status=ValueStatus.PRESENT,
        changed_by=actor_id,
        changed_at=now,
    )

    event = AuditEvent(
        event_id=uuid4(),
        receipt_id=receipt_id,
        event_type=AuditEventType.REVIEW_STARTED,
        actor_id=actor_id,
        occurred_at=now,
    )

    async def exercise():
        uow = SQLAlchemyUnitOfWork(factory)

        with pytest.raises(RuntimeError, match="force rollback"):
            async with uow:
                await uow.correction_history.append(history)
                await uow.audit_events.append(event)
                raise RuntimeError("force rollback")

    try:
        asyncio.run(exercise())

        with factory() as session:
            history_count = session.scalar(
                select(func.count()).select_from(
                    CorrectionHistoryRecord
                )
            )
            audit_count = session.scalar(
                select(func.count()).select_from(
                    AuditEventRecord
                )
            )

        assert history_count == 0
        assert audit_count == 0
    finally:
        engine.dispose()

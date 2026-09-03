from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import FieldName, ValueStatus
from backend.app.domain.errors import StaleUpdate
from backend.app.domain.models import (
    ExtractedField,
    NormalizationProvenance,
)
from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_field_repository import (
    SQLAlchemyFieldRepository,
)


def make_field(*, updated_at: datetime) -> ExtractedField:
    return ExtractedField(
        receipt_id=uuid4(),
        field_name=FieldName.MERCHANT_NAME,
        ocr_run_id=uuid4(),
        kie_run_id=uuid4(),
        raw_text="ABC Store",
        predicted_value="ABC Store",
        normalized_value="ABC Store",
        normalization=NormalizationProvenance(
            rule="identity",
            version="1",
        ),
        value_status=ValueStatus.PRESENT,
        corrected_value=None,
        corrected_status=None,
        has_correction=False,
        effective_value="ABC Store",
        effective_status=ValueStatus.PRESENT,
        confidence=0.95,
        machine_needs_review=False,
        effective_needs_review=False,
        review_reasons=(),
        review_policy_version=None,
        source_block_ids=("block-1",),
        verified=False,
        updated_at=updated_at,
    )


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
    )
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
async def test_field_repository_get_and_list(session_factory):
    now = datetime.now(timezone.utc)
    field = make_field(updated_at=now)

    with session_factory() as session:
        repository = SQLAlchemyFieldRepository(session)
        repository.add_initial(field)
        session.commit()

    with session_factory() as session:
        repository = SQLAlchemyFieldRepository(session)

        loaded = await repository.get(
            field.receipt_id,
            field.field_name,
        )
        listed = await repository.list_for_receipt(
            field.receipt_id,
            kie_run_id=field.kie_run_id,
        )

    assert loaded == field
    assert list(listed) == [field]


@pytest.mark.asyncio
async def test_field_repository_save_uses_atomic_updated_at_cas(
    session_factory,
):
    now = datetime.now(timezone.utc)
    field = make_field(updated_at=now)

    with session_factory() as session:
        repository = SQLAlchemyFieldRepository(session)
        repository.add_initial(field)
        session.commit()

    first_session = session_factory()
    second_session = session_factory()

    try:
        first_repository = SQLAlchemyFieldRepository(first_session)
        second_repository = SQLAlchemyFieldRepository(second_session)

        first_loaded = await first_repository.get(
            field.receipt_id,
            field.field_name,
        )
        second_loaded = await second_repository.get(
            field.receipt_id,
            field.field_name,
        )

        assert first_loaded is not None
        assert second_loaded is not None

        first_updated = first_loaded.model_copy(
            update={
                "verified": True,
                "updated_at": now + timedelta(seconds=1),
            }
        )

        saved = await first_repository.save(
            first_updated,
            expected_updated_at=first_loaded.updated_at,
        )
        first_session.commit()

        stale_updated = second_loaded.model_copy(
            update={
                "verified": True,
                "updated_at": now + timedelta(seconds=2),
            }
        )

        with pytest.raises(StaleUpdate):
            await second_repository.save(
                stale_updated,
                expected_updated_at=second_loaded.updated_at,
            )

        assert saved.updated_at == first_updated.updated_at
    finally:
        first_session.close()
        second_session.close()

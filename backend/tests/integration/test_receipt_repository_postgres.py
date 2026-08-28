from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import StaleUpdate
from backend.app.domain.models import Receipt
from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_receipt_repository import (
    SQLAlchemyReceiptRepository,
)


DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason="TEST_DATABASE_URL is required for PostgreSQL integration",
)


def test_two_independent_sessions_use_atomic_receipt_cas():
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    receipt_id = uuid4()
    initial = datetime.now(timezone.utc).replace(microsecond=0)

    try:
        seed = factory()
        seed_repo = SQLAlchemyReceiptRepository(seed)
        seed_repo_result = __import__("asyncio").run(
            seed_repo.create_with_storage(
                Receipt(
                    receipt_id=receipt_id,
                    original_filename="cas.png",
                    status=ReceiptStatus.UPLOADED,
                    image_width_px=10,
                    image_height_px=10,
                    created_at=initial,
                    updated_at=initial,
                ),
                storage_key=f"receipts/{receipt_id}.png",
                content_type="image/png",
            )
        )
        assert seed_repo_result.receipt_id == receipt_id
        seed.commit()
        seed.close()

        first_session = factory()
        second_session = factory()
        try:
            first_repo = SQLAlchemyReceiptRepository(first_session)
            second_repo = SQLAlchemyReceiptRepository(second_session)
            first_view = __import__("asyncio").run(first_repo.get(receipt_id))
            second_view = __import__("asyncio").run(second_repo.get(receipt_id))
            assert first_view is not None
            assert second_view is not None
            assert first_view.updated_at == second_view.updated_at == initial

            first_changed = first_view.model_copy(
                update={
                    "status": ReceiptStatus.PROCESSING,
                    "updated_at": initial + timedelta(seconds=1),
                }
            )
            second_changed = second_view.model_copy(
                update={
                    "status": ReceiptStatus.FAILED,
                    "updated_at": initial + timedelta(seconds=2),
                }
            )

            __import__("asyncio").run(
                first_repo.save(
                    first_changed,
                    expected_updated_at=initial,
                )
            )
            first_session.commit()

            with pytest.raises(StaleUpdate):
                __import__("asyncio").run(
                    second_repo.save(
                        second_changed,
                        expected_updated_at=initial,
                    )
                )
            second_session.rollback()
        finally:
            first_session.close()
            second_session.close()
    finally:
        cleanup = factory()
        cleanup.execute(
            __import__("sqlalchemy").delete(
                __import__("backend.app.persistence.models", fromlist=["ReceiptRecord"]).ReceiptRecord
            ).where(
                __import__("backend.app.persistence.models", fromlist=["ReceiptRecord"]).ReceiptRecord.receipt_id
                == receipt_id
            )
        )
        cleanup.commit()
        cleanup.close()
        engine.dispose()

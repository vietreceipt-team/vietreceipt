from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import StaleUpdate
from backend.app.domain.models import Receipt
from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_receipt_repository import (
    SQLAlchemyReceiptRepository,
)


def make_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def make_receipt():
    now = datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)
    return Receipt(
        receipt_id=uuid4(),
        original_filename="receipt.png",
        status=ReceiptStatus.UPLOADED,
        processing_stage=None,
        image_width_px=10,
        image_height_px=20,
        latest_ocr_run_id=None,
        latest_kie_run_id=None,
        last_error=None,
        created_at=now,
        updated_at=now,
        review_started_at=None,
        processed_at=None,
        verified_at=None,
    )


@pytest.mark.asyncio
async def test_create_get_list_save_and_delete():
    session = make_session()
    repo = SQLAlchemyReceiptRepository(session)
    receipt = make_receipt()

    created = await repo.create_with_storage(
        receipt,
        storage_key=f"receipts/{receipt.receipt_id}.png",
        content_type="image/png",
    )
    session.commit()

    assert (await repo.get(receipt.receipt_id)).receipt_id == receipt.receipt_id
    assert [item.receipt_id for item in await repo.list_receipts(page=1, page_size=10)] == [
        receipt.receipt_id
    ]

    updated_at = receipt.updated_at + timedelta(seconds=1)
    changed = created.model_copy(
        update={
            "status": ReceiptStatus.PROCESSING,
            "updated_at": updated_at,
        }
    )
    saved = await repo.save(
        changed,
        expected_updated_at=receipt.updated_at,
    )
    session.commit()
    assert saved.status is ReceiptStatus.PROCESSING

    with pytest.raises(StaleUpdate):
        await repo.save(
            changed,
            expected_updated_at=receipt.updated_at,
        )

    assert await repo.delete(receipt.receipt_id) is True
    session.commit()
    assert await repo.get(receipt.receipt_id) is None

    session.close()

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.models import Receipt
from backend.app.persistence.models import Base
from backend.app.persistence.sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository
from backend.app.persistence.sqlalchemy_unit_of_work import SQLAlchemyUnitOfWorkFactory


@pytest.fixture
def postgres_factory():
    url = os.getenv("TEST_DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        pytest.skip("TEST_DATABASE_URL must point to PostgreSQL")
    schema = "w3_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        url,
        connect_args={"options": f"-csearch_path={schema}"},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield sessionmaker(bind=engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def test_postgres_atomic_claim_allows_one_worker(postgres_factory):
    receipt_id = uuid4()
    now = datetime.now(timezone.utc)
    session = postgres_factory()
    asyncio.run(
        SQLAlchemyReceiptRepository(session).create_with_storage(
            Receipt(
                receipt_id=receipt_id,
                original_filename="race.png",
                status=ReceiptStatus.UPLOADED,
                image_width_px=20,
                image_height_px=20,
                created_at=now,
                updated_at=now,
            ),
            storage_key=f"receipts/{receipt_id}.png",
            content_type="image/png",
        )
    )
    session.commit()
    session.close()

    def claim(delivery_id):
        async def run():
            async with SQLAlchemyUnitOfWorkFactory(postgres_factory)() as uow:
                attempt = await uow.processing.claim(
                    receipt_id,
                    delivery_id=delivery_id,
                    attempt_id=uuid4(),
                    ocr_run_id=uuid4(),
                    kie_run_id=uuid4(),
                    started_at=datetime.now(timezone.utc),
                )
                if attempt:
                    await uow.commit()
                return attempt
        return asyncio.run(run())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["postgres-race-a", "postgres-race-b"]))
    assert sum(result is not None for result in results) == 1

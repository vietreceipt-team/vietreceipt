from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.domain.errors import PersistenceFailure
from backend.app.persistence.models import Base
from backend.app.persistence.receipt_upload_service import (
    SQLAlchemyReceiptPersistenceService,
)
from backend.app.ports.persistence import ReceiptUpload
from backend.app.storage.errors import ObjectNotFoundError
from backend.app.storage.validator import ReceiptImageValidator


class Storage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFoundError(key)
        return self.objects[key]

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


class Ids:
    def new_id(self) -> UUID:
        return UUID(int=1)


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 8, 28, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_delete_maps_sqlalchemy_commit_failure_to_persistence_failure(
    monkeypatch,
):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    storage = Storage()
    service = SQLAlchemyReceiptPersistenceService(
        validator=ReceiptImageValidator(),
        storage=storage,
        session_factory=factory,
        id_generator=Ids(),
        clock=Clock(),
    )

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="x.png",
            content_type="image/png",
            file=BytesIO(_image()),
        )
    )
    assert storage.objects

    def fail_commit(self):
        raise OperationalError(
            "DELETE receipt failed",
            {},
            RuntimeError("driver failure"),
        )

    monkeypatch.setattr("sqlalchemy.orm.Session.commit", fail_commit)

    with pytest.raises(PersistenceFailure):
        await service.delete_receipt(receipt.receipt_id)

    assert storage.objects == {}
    engine.dispose()


def _image() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (5, 5)).save(stream, format="PNG")
    return stream.getvalue()

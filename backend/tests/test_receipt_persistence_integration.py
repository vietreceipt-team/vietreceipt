from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from uuid import UUID

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.domain.enums import ReceiptStatus
from backend.app.domain.errors import PersistenceFailure
from backend.app.persistence.models import Base, ReceiptRecord
from backend.app.persistence.receipt_upload_service import (
    SQLAlchemyReceiptPersistenceService,
)
from backend.app.ports.persistence import ReceiptUpload
from backend.app.storage.errors import (
    ImageTooLargeError,
    InvalidImageError,
    ObjectNotFoundError,
    StorageUnavailableError,
)
from backend.app.storage.validator import ReceiptImageValidator


def make_image(fmt: str, size=(7, 5)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size).save(stream, format=fmt)
    return stream.getvalue()


class FixedIdGenerator:
    def __init__(self) -> None:
        self._next = 1

    def new_id(self) -> UUID:
        value = UUID(int=self._next)
        self._next += 1
        return value


class FixedClock:
    def now(self) -> datetime:
        return datetime(2026, 8, 18, 3, 0, tzinfo=timezone.utc)


class MemoryStorage:
    def __init__(
        self,
        *,
        fail_put: bool = False,
        fail_delete: bool = False,
    ) -> None:
        self.objects: dict[str, bytes] = {}
        self.content_types: dict[str, str] = {}
        self.fail_put = fail_put
        self.fail_delete = fail_delete
        self.delete_calls = 0

    def put(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_put:
            raise StorageUnavailableError("storage unavailable")

        self.objects[key] = data
        self.content_types[key] = content_type

    def get(self, key: str) -> bytes:
        if key not in self.objects:
            raise ObjectNotFoundError(key)

        return self.objects[key]

    def delete(self, key: str) -> None:
        self.delete_calls += 1

        if self.fail_delete:
            raise StorageUnavailableError("cleanup unavailable")

        if key not in self.objects:
            raise ObjectNotFoundError(key)

        del self.objects[key]
        self.content_types.pop(key, None)


@pytest.fixture
def session_factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def make_service(session_factory, storage=None):
    return SQLAlchemyReceiptPersistenceService(
        validator=ReceiptImageValidator(),
        storage=storage or MemoryStorage(),
        session_factory=session_factory,
        id_generator=FixedIdGenerator(),
        clock=FixedClock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("fmt", "content_type"),
    [
        ("JPEG", "image/jpeg"),
        ("PNG", "image/png"),
        ("WEBP", "image/webp"),
    ],
)
async def test_persist_upload_uses_validated_metadata(
    session_factory,
    fmt,
    content_type,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="../../client-name.exe",
            content_type="application/octet-stream",
            file=BytesIO(make_image(fmt)),
        )
    )

    assert receipt.status is ReceiptStatus.UPLOADED
    assert receipt.original_filename == "../../client-name.exe"
    assert receipt.image_width_px == 7
    assert receipt.image_height_px == 5

    with session_factory() as session:
        record = session.get(
            ReceiptRecord,
            receipt.receipt_id,
        )

        assert record is not None
        assert record.content_type == content_type
        assert "client-name" not in record.storage_key
        assert record.storage_key in storage.objects
        assert (
            storage.content_types[record.storage_key]
            == content_type
        )


@pytest.mark.asyncio
async def test_invalid_image_performs_no_storage_write(
    session_factory,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    with pytest.raises(InvalidImageError):
        await service.persist_upload(
            ReceiptUpload(
                filename="bad.jpg",
                content_type="image/jpeg",
                file=BytesIO(b"not an image"),
            )
        )

    assert storage.objects == {}


@pytest.mark.asyncio
async def test_storage_failure_creates_no_db_record(
    session_factory,
):
    storage = MemoryStorage(fail_put=True)
    service = make_service(session_factory, storage)

    with pytest.raises(StorageUnavailableError):
        await service.persist_upload(
            ReceiptUpload(
                filename="x.png",
                content_type="image/png",
                file=BytesIO(make_image("PNG")),
            )
        )

    with session_factory() as session:
        assert session.query(ReceiptRecord).count() == 0


@pytest.mark.asyncio
async def test_db_failure_attempts_storage_cleanup(
    session_factory,
    monkeypatch,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    def explode_commit(self):
        raise RuntimeError("db commit failed")

    monkeypatch.setattr(
        "sqlalchemy.orm.Session.commit",
        explode_commit,
    )

    with pytest.raises(PersistenceFailure):
        await service.persist_upload(
            ReceiptUpload(
                filename="x.png",
                content_type="image/png",
                file=BytesIO(make_image("PNG")),
            )
        )

    assert storage.delete_calls == 1
    assert storage.objects == {}


@pytest.mark.asyncio
async def test_cleanup_failure_is_observable(
    session_factory,
    monkeypatch,
    caplog,
):
    storage = MemoryStorage(fail_delete=True)
    service = make_service(session_factory, storage)

    def explode_commit(self):
        raise RuntimeError("db commit failed")

    monkeypatch.setattr(
        "sqlalchemy.orm.Session.commit",
        explode_commit,
    )

    with pytest.raises(
        PersistenceFailure,
        match="cleanup also failed",
    ):
        await service.persist_upload(
            ReceiptUpload(
                filename="x.png",
                content_type="image/png",
                file=BytesIO(make_image("PNG")),
            )
        )

    assert "storage cleanup failed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_delete_foundation_handles_missing_object(
    session_factory,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="x.png",
            content_type="image/png",
            file=BytesIO(make_image("PNG")),
        )
    )

    storage.objects.clear()
    storage.content_types.clear()

    assert (
        await service.delete_receipt(
            receipt.receipt_id
        )
        is True
    )

    with session_factory() as session:
        assert (
            session.get(
                ReceiptRecord,
                receipt.receipt_id,
            )
            is None
        )


@pytest.mark.asyncio
async def test_oversized_image_performs_no_storage_write(
    session_factory,
):
    storage = MemoryStorage()

    validator = ReceiptImageValidator(
        max_size_bytes=10,
    )

    service = SQLAlchemyReceiptPersistenceService(
        validator=validator,
        storage=storage,
        session_factory=session_factory,
        id_generator=FixedIdGenerator(),
        clock=FixedClock(),
    )

    with pytest.raises(ImageTooLargeError):
        await service.persist_upload(
            ReceiptUpload(
                filename="large.png",
                content_type="image/png",
                file=BytesIO(make_image("PNG")),
            )
        )

    assert storage.objects == {}


@pytest.mark.asyncio
async def test_decompression_bomb_performs_no_storage_write(
    session_factory,
    monkeypatch,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    def raise_bomb(*args, **kwargs):
        raise Image.DecompressionBombError(
            "synthetic decompression bomb"
        )

    monkeypatch.setattr(
        Image,
        "open",
        raise_bomb,
    )

    with pytest.raises(InvalidImageError):
        await service.persist_upload(
            ReceiptUpload(
                filename="bomb.png",
                content_type="image/png",
                file=BytesIO(make_image("PNG")),
            )
        )

    assert storage.objects == {}


@pytest.mark.asyncio
async def test_delete_existing_receipt_and_object(
    session_factory,
):
    storage = MemoryStorage()
    service = make_service(session_factory, storage)

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="x.png",
            content_type="image/png",
            file=BytesIO(make_image("PNG")),
        )
    )

    assert storage.objects

    result = await service.delete_receipt(
        receipt.receipt_id
    )

    assert result is True
    assert storage.objects == {}

    with session_factory() as session:
        assert (
            session.get(
                ReceiptRecord,
                receipt.receipt_id,
            )
            is None
        )


@pytest.mark.asyncio
async def test_delete_missing_receipt_returns_false(
    session_factory,
):
    service = make_service(
        session_factory,
        MemoryStorage(),
    )

    result = await service.delete_receipt(
        UUID(int=999)
    )

    assert result is False


@pytest.mark.asyncio
async def test_delete_storage_unavailable_preserves_db_record(
    session_factory,
):
    storage = MemoryStorage()
    service = make_service(
        session_factory,
        storage,
    )

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="x.png",
            content_type="image/png",
            file=BytesIO(make_image("PNG")),
        )
    )

    storage.fail_delete = True

    with pytest.raises(StorageUnavailableError):
        await service.delete_receipt(
            receipt.receipt_id
        )

    with session_factory() as session:
        assert (
            session.get(
                ReceiptRecord,
                receipt.receipt_id,
            )
            is not None
        )


@pytest.mark.asyncio
async def test_delete_database_failure_is_observable(
    session_factory,
    monkeypatch,
):
    storage = MemoryStorage()
    service = make_service(
        session_factory,
        storage,
    )

    receipt = await service.persist_upload(
        ReceiptUpload(
            filename="x.png",
            content_type="image/png",
            file=BytesIO(make_image("PNG")),
        )
    )

    def explode_commit(self):
        raise RuntimeError(
            "synthetic DB delete failure"
        )

    monkeypatch.setattr(
        "sqlalchemy.orm.Session.commit",
        explode_commit,
    )

    with pytest.raises(RuntimeError):
        await service.delete_receipt(
            receipt.receipt_id
        )
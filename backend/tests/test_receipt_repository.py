from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.persistence.models import Base, Receipt, ReceiptStatus
from app.persistence.sqlalchemy_receipt_repository import SQLAlchemyReceiptRepository


def make_repository():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return SQLAlchemyReceiptRepository(sessionmaker(bind=engine, expire_on_commit=False))


def test_repository_create_get_delete():
    repo = make_repository()
    receipt_id = uuid4()
    receipt = Receipt(
        receipt_id=receipt_id,
        user_id="user-1",
        original_filename="receipt.jpg",
        storage_key=f"receipts/{receipt_id}.jpg",
        content_type="image/jpeg",
        image_width_px=10,
        image_height_px=20,
        status=ReceiptStatus.UPLOADED,
    )

    created = repo.create(receipt)
    assert created.receipt_id == receipt_id
    assert repo.get_by_id(receipt_id).storage_key == receipt.storage_key
    assert repo.delete(receipt_id) is True
    assert repo.get_by_id(receipt_id) is None
    assert repo.delete(receipt_id) is False

from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ReceiptStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Receipt(Base):
    __tablename__ = "receipts"

    receipt_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    image_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height_px: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReceiptStatus] = mapped_column(
        SAEnum(ReceiptStatus, name="receipt_status", native_enum=False),
        nullable=False,
        default=ReceiptStatus.UPLOADED,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

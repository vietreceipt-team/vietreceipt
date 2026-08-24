from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.app.domain.enums import ProcessingStage, ReceiptStatus
from backend.app.domain.models import ProcessingError, Receipt


class Base(DeclarativeBase):
    pass


def _ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class ReceiptRecord(Base):
    __tablename__ = "receipts"

    receipt_id: Mapped[UUID] = mapped_column(primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Internal persistence metadata. These are intentionally not added to the
    # canonical public/domain Receipt model.
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[str] = mapped_column(String(32), nullable=False)
    processing_stage: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_width_px: Mapped[int] = mapped_column(Integer, nullable=False)
    image_height_px: Mapped[int] = mapped_column(Integer, nullable=False)

    latest_ocr_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    latest_kie_run_id: Mapped[UUID | None] = mapped_column(nullable=True)
    last_error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    review_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_domain(self) -> Receipt:
        return Receipt(
            receipt_id=self.receipt_id,
            original_filename=self.original_filename,
            status=ReceiptStatus(self.status),
            processing_stage=(
                ProcessingStage(self.processing_stage)
                if self.processing_stage is not None
                else None
            ),
            image_width_px=self.image_width_px,
            image_height_px=self.image_height_px,
            latest_ocr_run_id=self.latest_ocr_run_id,
            latest_kie_run_id=self.latest_kie_run_id,
            last_error=(
                ProcessingError.model_validate(self.last_error)
                if self.last_error is not None
                else None
            ),
            created_at=_ensure_aware(self.created_at),
            updated_at=_ensure_aware(self.updated_at),
            review_started_at=_ensure_aware(self.review_started_at),
            processed_at=_ensure_aware(self.processed_at),
            verified_at=_ensure_aware(self.verified_at),
        )

    @classmethod
    def from_domain(
        cls,
        receipt: Receipt,
        *,
        storage_key: str,
        content_type: str,
    ) -> "ReceiptRecord":
        return cls(
            receipt_id=receipt.receipt_id,
            original_filename=receipt.original_filename,
            storage_key=storage_key,
            content_type=content_type,
            status=receipt.status.value,
            processing_stage=(
                receipt.processing_stage.value
                if receipt.processing_stage is not None
                else None
            ),
            image_width_px=receipt.image_width_px,
            image_height_px=receipt.image_height_px,
            latest_ocr_run_id=receipt.latest_ocr_run_id,
            latest_kie_run_id=receipt.latest_kie_run_id,
            last_error=(
                receipt.last_error.model_dump(mode="json")
                if receipt.last_error is not None
                else None
            ),
            created_at=receipt.created_at,
            updated_at=receipt.updated_at,
            review_started_at=receipt.review_started_at,
            processed_at=receipt.processed_at,
            verified_at=receipt.verified_at,
        )

    def apply_domain(self, receipt: Receipt) -> None:
        self.original_filename = receipt.original_filename
        self.status = receipt.status.value
        self.processing_stage = (
            receipt.processing_stage.value
            if receipt.processing_stage is not None
            else None
        )
        self.image_width_px = receipt.image_width_px
        self.image_height_px = receipt.image_height_px
        self.latest_ocr_run_id = receipt.latest_ocr_run_id
        self.latest_kie_run_id = receipt.latest_kie_run_id
        self.last_error = (
            receipt.last_error.model_dump(mode="json")
            if receipt.last_error is not None
            else None
        )
        self.updated_at = receipt.updated_at
        self.review_started_at = receipt.review_started_at
        self.processed_at = receipt.processed_at
        self.verified_at = receipt.verified_at


class ProcessingAttemptRecord(Base):
    __tablename__ = "processing_attempts"
    __table_args__ = (
        UniqueConstraint("ocr_run_id"),
        UniqueConstraint("kie_run_id"),
        UniqueConstraint("active_receipt_id"),
    )

    attempt_id: Mapped[UUID] = mapped_column(primary_key=True)
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.receipt_id", ondelete="CASCADE"), nullable=False
    )
    # Equal to receipt_id only while ACTIVE. NULL on terminal attempts makes
    # this a portable single-active-attempt constraint.
    active_receipt_id: Mapped[UUID | None] = mapped_column(nullable=True)
    delivery_id: Mapped[str] = mapped_column(String(255), nullable=False)
    ocr_run_id: Mapped[UUID] = mapped_column(nullable=False)
    kie_run_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class OCRRunRecord(Base):
    __tablename__ = "ocr_runs"
    ocr_run_id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("processing_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.receipt_id", ondelete="CASCADE"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KIERunRecord(Base):
    __tablename__ = "kie_runs"
    kie_run_id: Mapped[UUID] = mapped_column(primary_key=True)
    attempt_id: Mapped[UUID] = mapped_column(
        ForeignKey("processing_attempts.attempt_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    receipt_id: Mapped[UUID] = mapped_column(
        ForeignKey("receipts.receipt_id", ondelete="CASCADE"), nullable=False
    )
    source_ocr_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ocr_runs.ocr_run_id"), nullable=False
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def uid():
    return str(uuid4())


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


class Invoice(Base):
    __tablename__ = "invoice_v2_receipts"
    receipt_id = Column(String(36), primary_key=True)
    original_filename = Column(String(255), nullable=False)
    content_type = Column(String(80), nullable=False)
    source_group = Column(String(32), nullable=False)
    storage_key = Column(String(255), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="UPLOADED", index=True)
    version = Column(Integer, nullable=False, default=1)
    processing_stage = Column(String(32))
    processing_error = Column(JSON)
    retry_count = Column(Integer, nullable=False, default=0)
    active_attempt_id = Column(String(36))
    latest_ocr_run_id = Column(String(36))
    latest_kie_run_id = Column(String(36))
    created_at = Column(String(40), nullable=False, default=timestamp, index=True)
    updated_at = Column(String(40), nullable=False, default=timestamp)
    verified_at = Column(String(40))
    __table_args__ = (
        CheckConstraint(
            "status IN ('UPLOADED','PROCESSING','NEEDS_REVIEW','VERIFIED','FAILED')",
            name="invoice_v2_status",
        ),
    )


class Attempt(Base):
    __tablename__ = "invoice_v2_attempts"
    attempt_id = Column(String(36), primary_key=True)
    receipt_id = Column(
        String(36), ForeignKey(Invoice.receipt_id), nullable=False, index=True
    )
    active_receipt_id = Column(String(36), unique=True)
    ocr_run_id = Column(String(36), nullable=False, unique=True)
    kie_run_id = Column(String(36), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="ACTIVE")
    stage = Column(String(32), nullable=False, default="DOCUMENT_READING")
    lease_until = Column(Float, nullable=False, index=True)
    created_at = Column(String(40), nullable=False, default=timestamp)
    finished_at = Column(String(40))
    error = Column(JSON)


class MachineRun(Base):
    __tablename__ = "invoice_v2_machine_runs"
    run_id = Column(String(36), primary_key=True)
    receipt_id = Column(
        String(36), ForeignKey(Invoice.receipt_id), nullable=False, index=True
    )
    attempt_id = Column(String(36), ForeignKey(Attempt.attempt_id), nullable=False)
    kind = Column(String(8), nullable=False)
    source_ocr_run_id = Column(String(36), ForeignKey("invoice_v2_machine_runs.run_id"))
    payload = Column(JSON, nullable=False)
    created_at = Column(String(40), nullable=False, default=timestamp)
    __table_args__ = (
        UniqueConstraint("attempt_id", "kind", name="uq_invoice_v2_attempt_kind"),
    )


class Cell(Base):
    """Structured row/cell projection; machine value and correction never share a column."""

    __tablename__ = "invoice_v2_cells"
    receipt_id = Column(String(36), ForeignKey(Invoice.receipt_id), primary_key=True)
    section = Column(String(8), primary_key=True)
    row_id = Column(String(128), primary_key=True)
    field = Column(String(64), primary_key=True)
    row_index = Column(Integer, nullable=False, default=0)
    kie_run_id = Column(
        String(36), ForeignKey(MachineRun.run_id), nullable=False, index=True
    )
    machine = Column(JSON, nullable=False)
    correction = Column(JSON)
    reviewed = Column(Boolean, nullable=False, default=False)


class Outbox(Base):
    __tablename__ = "invoice_v2_outbox"
    event_id = Column(String(36), primary_key=True, default=uid)
    receipt_id = Column(
        String(36), ForeignKey(Invoice.receipt_id), nullable=False, index=True
    )
    sent = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(String(40), nullable=False, default=timestamp)
    sent_at = Column(Float)


class Audit(Base):
    __tablename__ = "invoice_v2_audit"
    event_id = Column(String(36), primary_key=True, default=uid)
    receipt_id = Column(
        String(36), ForeignKey(Invoice.receipt_id), nullable=False, index=True
    )
    kind = Column(String(32), nullable=False)
    section = Column(String(8))
    row_id = Column(String(128))
    field = Column(String(64))
    old_value = Column(JSON)
    new_value = Column(JSON)
    actor = Column(String(64), nullable=False, default="demo-user")
    created_at = Column(String(40), nullable=False, default=timestamp)


@event.listens_for(MachineRun, "before_update")
@event.listens_for(MachineRun, "before_delete")
def forbid_run_mutation(mapper, connection, target):
    raise ValueError("Machine runs are immutable.")

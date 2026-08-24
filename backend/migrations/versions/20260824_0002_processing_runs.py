"""add durable immutable processing attempts and run outputs

Revision ID: 20260824_0002
Revises: 20260817_0001
"""

from alembic import op
import sqlalchemy as sa


revision = "20260824_0002"
down_revision = "20260817_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processing_attempts",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("active_receipt_id", sa.Uuid(), nullable=True),
        sa.Column("delivery_id", sa.String(length=255), nullable=False),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("kie_run_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("stage", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.receipt_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("attempt_id"),
        sa.UniqueConstraint("active_receipt_id"),
        sa.UniqueConstraint("ocr_run_id"),
        sa.UniqueConstraint("kie_run_id"),
    )
    op.create_table(
        "ocr_runs",
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["processing_attempts.attempt_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.receipt_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("ocr_run_id"),
        sa.UniqueConstraint("attempt_id"),
    )
    op.create_table(
        "kie_runs",
        sa.Column("kie_run_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("source_ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["attempt_id"], ["processing_attempts.attempt_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receipt_id"], ["receipts.receipt_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_ocr_run_id"], ["ocr_runs.ocr_run_id"]),
        sa.PrimaryKeyConstraint("kie_run_id"),
        sa.UniqueConstraint("attempt_id"),
    )


def downgrade() -> None:
    op.drop_table("kie_runs")
    op.drop_table("ocr_runs")
    op.drop_table("processing_attempts")

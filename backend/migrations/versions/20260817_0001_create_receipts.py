"""create receipts persistence table

Revision ID: 20260817_0001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "20260817_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("processing_stage", sa.String(length=32), nullable=True),
        sa.Column("image_width_px", sa.Integer(), nullable=False),
        sa.Column("image_height_px", sa.Integer(), nullable=False),
        sa.Column("latest_ocr_run_id", sa.Uuid(), nullable=True),
        sa.Column("latest_kie_run_id", sa.Uuid(), nullable=True),
        sa.Column("last_error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint("storage_key"),
    )


def downgrade() -> None:
    op.drop_table("receipts")

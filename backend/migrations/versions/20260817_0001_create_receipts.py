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
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("original_filename", sa.String(length=1024), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=64), nullable=False),
        sa.Column("image_width_px", sa.Integer(), nullable=False),
        sa.Column("image_height_px", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "UPLOADED", "PROCESSING", "NEEDS_REVIEW", "VERIFIED", "FAILED",
                name="receipt_status", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("receipt_id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index("ix_receipts_user_id", "receipts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_receipts_user_id", table_name="receipts")
    op.drop_table("receipts")

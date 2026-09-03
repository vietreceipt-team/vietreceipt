"""add canonical review persistence

Revision ID: 20260903_0003
Revises: 20260824_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260903_0003"
down_revision = "20260824_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "extracted_fields",
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column(
            "field_name",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column("ocr_run_id", sa.Uuid(), nullable=False),
        sa.Column("kie_run_id", sa.Uuid(), nullable=False),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.Column(
            "predicted_value",
            sa.String(),
            nullable=True,
        ),
        sa.Column(
            "normalized_value",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "normalization",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "value_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "corrected_value",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "corrected_status",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "has_correction",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "effective_value",
            sa.JSON(),
            nullable=True,
        ),
        sa.Column(
            "effective_status",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "machine_needs_review",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "effective_needs_review",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "review_reasons",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "review_policy_version",
            sa.String(length=255),
            nullable=True,
        ),
        sa.Column(
            "source_block_ids",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column(
            "verified",
            sa.Boolean(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.receipt_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ocr_run_id"],
            ["ocr_runs.ocr_run_id"],
        ),
        sa.ForeignKeyConstraint(
            ["kie_run_id"],
            ["kie_runs.kie_run_id"],
        ),
        sa.PrimaryKeyConstraint(
            "receipt_id",
            "field_name",
        ),
    )

    op.create_table(
        "correction_history",
        sa.Column(
            "correction_id",
            sa.Uuid(),
            nullable=False,
        ),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column(
            "field_name",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "operation",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column("kie_run_id", sa.Uuid(), nullable=False),
        sa.Column("old_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column(
            "old_status",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "new_status",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column("changed_by", sa.Uuid(), nullable=False),
        sa.Column(
            "changed_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.receipt_id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["kie_run_id"],
            ["kie_runs.kie_run_id"],
        ),
        sa.PrimaryKeyConstraint("correction_id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("receipt_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "field_name",
            sa.String(length=64),
            nullable=True,
        ),
        sa.Column(
            "operation",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["receipt_id"],
            ["receipts.receipt_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("correction_history")
    op.drop_table("extracted_fields")

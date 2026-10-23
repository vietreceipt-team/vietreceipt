"""Store actual worker config/runtime and stage timing separately from AI payloads."""

from alembic import op
import sqlalchemy as sa

revision = "20261023_provenance"
down_revision = "20260921_v2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "invoice_v2_attempts", sa.Column("provenance", sa.JSON(), nullable=True)
    )


def downgrade():
    op.drop_column("invoice_v2_attempts", "provenance")

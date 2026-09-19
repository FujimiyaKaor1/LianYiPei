"""Add durable external callback idempotency receipts."""
from alembic import op
import sqlalchemy as sa

from migrations._compat import table_exists

revision = "c6e9a4b5d215"
down_revision = "b5d8f2a3c104"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("external_callback_receipts"):
        op.create_table(
            "external_callback_receipts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("provider", sa.String(length=40), nullable=False),
            sa.Column("event_key", sa.String(length=160), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("response_body", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("provider", "event_key", name="uq_external_callback_provider_event"),
        )


def downgrade():
    op.drop_table("external_callback_receipts")

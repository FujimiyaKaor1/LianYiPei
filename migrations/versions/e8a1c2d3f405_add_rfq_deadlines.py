"""Add bounded supplier reply windows to Chain XiaoYi RFQs."""

from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, drop_marker, index_exists, table_exists

revision = "e8a1c2d3f405"
down_revision = "d7f0b6c8e321"
branch_labels = None
depends_on = None


def upgrade():
    if table_exists("chain_xiaoyi_tasks", op) and not column_exists("chain_xiaoyi_tasks", "quote_deadline_at", op):
        op.add_column(
            "chain_xiaoyi_tasks",
            sa.Column("quote_deadline_at", sa.DateTime(), nullable=True),
        )
    if table_exists("chain_xiaoyi_tasks", op) and not index_exists("chain_xiaoyi_tasks", "ix_chain_xiaoyi_tasks_quote_deadline_at", op):
        op.create_index(
            "ix_chain_xiaoyi_tasks_quote_deadline_at",
            "chain_xiaoyi_tasks",
            ["quote_deadline_at"],
        )
    if table_exists("chain_xiaoyi_outbound_records", op) and not column_exists("chain_xiaoyi_outbound_records", "rejected_at", op):
        op.add_column(
            "chain_xiaoyi_outbound_records",
            sa.Column("rejected_at", sa.DateTime(), nullable=True),
        )
    if table_exists("chain_xiaoyi_outbound_records", op) and not column_exists("chain_xiaoyi_outbound_records", "timed_out_at", op):
        op.add_column(
            "chain_xiaoyi_outbound_records",
            sa.Column("timed_out_at", sa.DateTime(), nullable=True),
        )
    # The marker is only needed while traversing the legacy history.  Removing
    # it at the head leaves a normal Alembic database with no compatibility
    # tables visible to the application.
    drop_marker(op)


def downgrade():
    op.drop_column("chain_xiaoyi_outbound_records", "timed_out_at")
    op.drop_column("chain_xiaoyi_outbound_records", "rejected_at")
    op.drop_index("ix_chain_xiaoyi_tasks_quote_deadline_at", table_name="chain_xiaoyi_tasks")
    op.drop_column("chain_xiaoyi_tasks", "quote_deadline_at")

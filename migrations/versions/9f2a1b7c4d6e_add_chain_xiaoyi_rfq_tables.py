"""Add immutable candidate snapshots and idempotent RFQ audit records."""
from alembic import op
import sqlalchemy as sa

from migrations._compat import index_exists, table_exists

revision = "9f2a1b7c4d6e"
down_revision = "5e4d2a1b9c80"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("chain_xiaoyi_candidate_snapshots"):
        op.create_table(
            "chain_xiaoyi_candidate_snapshots",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("chain_xiaoyi_tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("enterprises.id"), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    if not index_exists("chain_xiaoyi_candidate_snapshots", "ix_chain_xiaoyi_candidate_snapshots_task_id"):
        op.create_index("ix_chain_xiaoyi_candidate_snapshots_task_id", "chain_xiaoyi_candidate_snapshots", ["task_id"])
    if not index_exists("chain_xiaoyi_candidate_snapshots", "ix_chain_xiaoyi_candidate_snapshots_supplier_id"):
        op.create_index("ix_chain_xiaoyi_candidate_snapshots_supplier_id", "chain_xiaoyi_candidate_snapshots", ["supplier_id"])
    if not table_exists("chain_xiaoyi_outbound_records"):
        op.create_table(
            "chain_xiaoyi_outbound_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("task_id", sa.Integer(), sa.ForeignKey("chain_xiaoyi_tasks.id", ondelete="CASCADE"), nullable=False),
            sa.Column("supplier_id", sa.Integer(), sa.ForeignKey("enterprises.id"), nullable=False),
            sa.Column("intent_quote_id", sa.Integer(), sa.ForeignKey("intent_quotes.id"), nullable=True),
            sa.Column("status", sa.String(length=24), nullable=False),
            sa.Column("channel", sa.String(length=24), nullable=False, server_default="site"),
            sa.Column("channel_status_json", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("replied_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("task_id", "supplier_id", name="uq_chain_xiaoyi_outbound_task_supplier"),
        )
    if not index_exists("chain_xiaoyi_outbound_records", "ix_chain_xiaoyi_outbound_records_task_id"):
        op.create_index("ix_chain_xiaoyi_outbound_records_task_id", "chain_xiaoyi_outbound_records", ["task_id"])
    if not index_exists("chain_xiaoyi_outbound_records", "ix_chain_xiaoyi_outbound_records_supplier_id"):
        op.create_index("ix_chain_xiaoyi_outbound_records_supplier_id", "chain_xiaoyi_outbound_records", ["supplier_id"])


def downgrade():
    op.drop_table("chain_xiaoyi_outbound_records")
    op.drop_table("chain_xiaoyi_candidate_snapshots")

"""add privacy-preserving Chain XiaoYi guest trials

Revision ID: 5e4d2a1b9c80
Revises: 8d7b7b9d2c31
"""
from alembic import op
import sqlalchemy as sa

revision = "5e4d2a1b9c80"
down_revision = "8d7b7b9d2c31"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("chain_xiaoyi_sessions") as batch:
        batch.add_column(sa.Column("anonymous_expires_at", sa.DateTime(), nullable=True))
    op.create_table(
        "chain_xiaoyi_guest_trials",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("browser_token_hash", sa.String(length=64), nullable=False),
        sa.Column("ip_hmac_hash", sa.String(length=64), nullable=False),
        sa.Column("match_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minute_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("minute_started_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("browser_token_hash"),
    )
    op.create_index("ix_chain_xiaoyi_guest_trials_browser_token_hash", "chain_xiaoyi_guest_trials", ["browser_token_hash"])
    op.create_index("ix_chain_xiaoyi_guest_trials_ip_hmac_hash", "chain_xiaoyi_guest_trials", ["ip_hmac_hash"])


def downgrade():
    op.drop_index("ix_chain_xiaoyi_guest_trials_ip_hmac_hash", table_name="chain_xiaoyi_guest_trials")
    op.drop_index("ix_chain_xiaoyi_guest_trials_browser_token_hash", table_name="chain_xiaoyi_guest_trials")
    op.drop_table("chain_xiaoyi_guest_trials")
    with op.batch_alter_table("chain_xiaoyi_sessions") as batch:
        batch.drop_column("anonymous_expires_at")

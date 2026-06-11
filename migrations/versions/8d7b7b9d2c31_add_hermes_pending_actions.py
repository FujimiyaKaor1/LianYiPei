"""add hermes pending actions

Revision ID: 8d7b7b9d2c31
Revises: 0e5ab26f3a6b
Create Date: 2026-06-11 01:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "8d7b7b9d2c31"
down_revision = "0e5ab26f3a6b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "hermes_pending_actions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.String(length=120), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hermes_pending_actions_alert_id",
        "hermes_pending_actions",
        ["alert_id"],
    )
    op.create_index(
        "ix_hermes_pending_actions_status_expires",
        "hermes_pending_actions",
        ["status", "expires_at"],
    )


def downgrade():
    op.drop_index("ix_hermes_pending_actions_status_expires", table_name="hermes_pending_actions")
    op.drop_index("ix_hermes_pending_actions_alert_id", table_name="hermes_pending_actions")
    op.drop_table("hermes_pending_actions")

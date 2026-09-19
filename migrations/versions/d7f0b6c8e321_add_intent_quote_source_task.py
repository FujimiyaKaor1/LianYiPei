"""Scope Agent quote idempotency to one RFQ task and supplier."""
from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, index_exists, table_exists, unique_constraint_exists

revision = "d7f0b6c8e321"
down_revision = "c6e9a4b5d215"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("intent_quotes", op):
        return
    # SQLite cannot ALTER an existing table to add constraints. Batch mode
    # performs the copy-and-move operation while remaining portable to MySQL.
    needs_column = not column_exists("intent_quotes", "source_rfq_task_id", op)
    needs_index = not index_exists("intent_quotes", "ix_intent_quotes_source_rfq_task_id", op)
    needs_unique = not unique_constraint_exists("intent_quotes", {"source_rfq_task_id", "seller_id"}, op)
    if not (needs_column or needs_index or needs_unique):
        return
    with op.batch_alter_table("intent_quotes", recreate="auto") as batch_op:
        if needs_column:
            batch_op.add_column(sa.Column("source_rfq_task_id", sa.Integer(), nullable=True))
        # The foreign key may already be present on a schema produced by the
        # ORM bootstrap.  SQLite's inspector exposes it reliably after the
        # batch copy, so only add it for the historical path.
        if needs_column and table_exists("chain_xiaoyi_tasks", op):
            batch_op.create_foreign_key(
                "fk_intent_quote_source_rfq_task",
                "chain_xiaoyi_tasks",
                ["source_rfq_task_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if needs_index:
            batch_op.create_index("ix_intent_quotes_source_rfq_task_id", ["source_rfq_task_id"], unique=False)
        if needs_unique:
            batch_op.create_unique_constraint(
                "uq_intent_quote_source_task_seller",
                ["source_rfq_task_id", "seller_id"],
            )


def downgrade():
    with op.batch_alter_table("intent_quotes", recreate="auto") as batch_op:
        batch_op.drop_constraint("uq_intent_quote_source_task_seller", type_="unique")
        batch_op.drop_index("ix_intent_quotes_source_rfq_task_id")
        batch_op.drop_constraint("fk_intent_quote_source_rfq_task", type_="foreignkey")
        batch_op.drop_column("source_rfq_task_id")

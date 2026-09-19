"""Add structured supplier quote details."""
from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, table_exists

revision = "b5d8f2a3c104"
down_revision = "a4c7e9f1b203"
branch_labels = None
depends_on = None


def upgrade():
    if table_exists("intent_quotes") and not column_exists("intent_quotes", "seller_reply_details"):
        op.add_column("intent_quotes", sa.Column("seller_reply_details", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("intent_quotes", "seller_reply_details")

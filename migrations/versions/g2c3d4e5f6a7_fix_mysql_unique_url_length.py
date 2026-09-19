"""Bound the unique canonical URL to MySQL's utf8mb4 index limit."""

from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, table_exists


revision = "g2c3d4e5f6a7"
down_revision = "f1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("industry_news_articles", op):
        return
    if not column_exists("industry_news_articles", "canonical_url", op):
        return
    # ``batch_alter_table`` is portable across SQLite (used by local tests)
    # and MySQL (used by production).  The existing unique constraint remains
    # attached to the column while only its bounded length changes.
    with op.batch_alter_table("industry_news_articles") as batch:
        batch.alter_column(
            "canonical_url",
            existing_type=sa.String(length=1000),
            type_=sa.String(length=700),
            existing_nullable=False,
        )


def downgrade():
    if not table_exists("industry_news_articles", op):
        return
    if not column_exists("industry_news_articles", "canonical_url", op):
        return
    with op.batch_alter_table("industry_news_articles") as batch:
        batch.alter_column(
            "canonical_url",
            existing_type=sa.String(length=700),
            type_=sa.String(length=1000),
            existing_nullable=False,
        )

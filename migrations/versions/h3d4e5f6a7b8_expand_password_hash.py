"""Allow current Werkzeug password hashes in MySQL."""

from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, table_exists


revision = "h3d4e5f6a7b8"
down_revision = "g2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("enterprises", op) or not column_exists("enterprises", "password_hash", op):
        return
    with op.batch_alter_table("enterprises") as batch:
        batch.alter_column(
            "password_hash",
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=True,
        )


def downgrade():
    # A shrink would truncate valid scrypt hashes already written after this
    # migration.  Keep the wider column on downgrade rather than risking
    # silent credential corruption; a fresh schema at the old revision can
    # still be created from the historical migration.
    return

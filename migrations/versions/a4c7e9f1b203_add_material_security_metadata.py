"""Add encrypted material storage and malware scan metadata."""
from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, table_exists

revision = "a4c7e9f1b203"
down_revision = "9f2a1b7c4d6e"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("chain_xiaoyi_file_imports"):
        return
    for name, column in (
        ("storage_key", sa.Column("storage_key", sa.String(length=512), nullable=True)),
        ("scan_status", sa.Column("scan_status", sa.String(length=24), nullable=True)),
        ("scan_engine", sa.Column("scan_engine", sa.String(length=60), nullable=True)),
    ):
        if not column_exists("chain_xiaoyi_file_imports", name):
            op.add_column("chain_xiaoyi_file_imports", column)


def downgrade():
    op.drop_column("chain_xiaoyi_file_imports", "scan_engine")
    op.drop_column("chain_xiaoyi_file_imports", "scan_status")
    op.drop_column("chain_xiaoyi_file_imports", "storage_key")

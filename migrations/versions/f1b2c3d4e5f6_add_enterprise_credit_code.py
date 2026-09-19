"""Store the enterprise unified social credit code as a unique fact."""

from alembic import op
import sqlalchemy as sa

from migrations._compat import column_exists, index_exists, table_exists


revision = "f1b2c3d4e5f6"
down_revision = "e8a1c2d3f405"
branch_labels = None
depends_on = None


def upgrade():
    if not table_exists("enterprises", op):
        return
    if not column_exists("enterprises", "unified_social_credit_code", op):
        op.add_column(
            "enterprises",
            sa.Column("unified_social_credit_code", sa.String(length=18), nullable=True),
        )
    # Existing rows are NULL because the old schema kept this value in JSON;
    # a unique nullable index permits those legacy rows while preventing every
    # new verified code from being registered twice.
    if not index_exists("enterprises", "ix_enterprises_unified_social_credit_code", op):
        op.create_index(
            "ix_enterprises_unified_social_credit_code",
            "enterprises",
            ["unified_social_credit_code"],
            unique=True,
        )


def downgrade():
    if not table_exists("enterprises", op):
        return
    if index_exists("enterprises", "ix_enterprises_unified_social_credit_code", op):
        op.drop_index("ix_enterprises_unified_social_credit_code", table_name="enterprises")
    if column_exists("enterprises", "unified_social_credit_code", op):
        op.drop_column("enterprises", "unified_social_credit_code")

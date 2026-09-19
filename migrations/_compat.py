"""Small, dialect-neutral helpers for resilient production migrations.

The repository historically shipped an initial migration generated from an
already-populated development database.  A fresh production database therefore
needs a safe bootstrap path, while an older database may already contain some
of the newer Agent tables.  These helpers keep migrations additive and make
that distinction explicit without exposing application secrets.
"""

from __future__ import annotations

from alembic import op
from flask import current_app
import sqlalchemy as sa
from sqlalchemy import inspect


BOOTSTRAP_MARKER = "lianyipei_schema_bootstrap"


def bind(operation=None):
    # Tests can replace a revision module's ``op`` with a concrete Operations
    # instance.  Accepting it explicitly keeps these helpers usable both from
    # Alembic's proxy and from direct migration unit tests.
    return (operation or op).get_bind()


def inspector(operation=None):
    return inspect(bind(operation))


def table_exists(table_name: str, operation=None) -> bool:
    return table_name in inspector(operation).get_table_names()


def column_exists(table_name: str, column_name: str, operation=None) -> bool:
    if not table_exists(table_name, operation):
        return False
    return column_name in {column["name"] for column in inspector(operation).get_columns(table_name)}


def index_exists(table_name: str, index_name: str, operation=None) -> bool:
    if not table_exists(table_name, operation):
        return False
    return index_name in {index.get("name") for index in inspector(operation).get_indexes(table_name)}


def unique_constraint_exists(table_name: str, columns: set[str], operation=None) -> bool:
    if not table_exists(table_name, operation):
        return False
    wanted = set(columns)
    return any(set(item.get("column_names") or []) == wanted for item in inspector(operation).get_unique_constraints(table_name))


def marker_exists(operation=None) -> bool:
    return table_exists(BOOTSTRAP_MARKER, operation)


def _create_marker() -> None:
    if marker_exists():
        return
    op.create_table(
        BOOTSTRAP_MARKER,
        # A single row is enough; the marker is removed by the last migration.
        # Keeping it in the database, instead of process state, makes the
        # compatibility path deterministic across separate migration commands.
        sa.Column("id", sa.Integer(), primary_key=True),
    )
    op.bulk_insert(
        sa.table(BOOTSTRAP_MARKER, sa.column("id", sa.Integer())),
        [{"id": 1}],
    )


def bootstrap_current_schema() -> bool:
    """Bootstrap an empty/current ``db.create_all`` schema once.

    The old base revision was generated as a diff against an existing schema
    and cannot create a fresh database.  On an empty database (or one already
    created by the local demo), create the current ORM metadata and leave a
    marker so legacy destructive revisions become no-ops.  Later additive
    revisions still inspect and repair missing columns/constraints.
    """
    # Alembic creates its version table before invoking the first revision;
    # it must not make an otherwise empty database look populated.
    existing = set(inspector().get_table_names()) - {"alembic_version", BOOTSTRAP_MARKER}
    current_agent_tables = {
        "chain_xiaoyi_tasks",
        "chain_xiaoyi_file_imports",
        "chain_xiaoyi_outbound_records",
        "external_callback_receipts",
    }
    is_empty = not existing
    is_current_demo_schema = current_agent_tables.issubset(existing)
    if not (is_empty or is_current_demo_schema):
        return False

    if is_empty:
        db = current_app.extensions["migrate"].db
        db.metadata.create_all(bind=bind())
    _create_marker()
    return True


def drop_marker(operation=None) -> None:
    if marker_exists(operation):
        (operation or op).drop_table(BOOTSTRAP_MARKER)

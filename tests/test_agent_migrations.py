"""Database migration checks for the production Agent schema."""
from importlib import import_module

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_intent_quote_source_task_migration_round_trips_on_sqlite():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("chain_xiaoyi_tasks", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table(
        "intent_quotes",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("seller_id", sa.Integer, nullable=False),
    )
    metadata.create_all(engine)

    migration = import_module("migrations.versions.d7f0b6c8e321_add_intent_quote_source_task")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "source_rfq_task_id" in {column["name"] for column in inspector.get_columns("intent_quotes")}
        assert "ix_intent_quotes_source_rfq_task_id" in {index["name"] for index in inspector.get_indexes("intent_quotes")}
        assert "uq_intent_quote_source_task_seller" in {
            constraint["name"] for constraint in inspector.get_unique_constraints("intent_quotes")
        }
        assert "fk_intent_quote_source_rfq_task" in {
            constraint["name"] for constraint in inspector.get_foreign_keys("intent_quotes")
        }

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "source_rfq_task_id" not in {column["name"] for column in inspector.get_columns("intent_quotes")}


def test_rfq_deadline_migration_adds_terminal_timestamps_on_sqlite():
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("chain_xiaoyi_tasks", metadata, sa.Column("id", sa.Integer, primary_key=True))
    sa.Table("chain_xiaoyi_outbound_records", metadata, sa.Column("id", sa.Integer, primary_key=True))
    metadata.create_all(engine)

    migration = import_module("migrations.versions.e8a1c2d3f405_add_rfq_deadlines")
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        task_columns = {column["name"] for column in inspector.get_columns("chain_xiaoyi_tasks")}
        outbound_columns = {column["name"] for column in inspector.get_columns("chain_xiaoyi_outbound_records")}
        assert "quote_deadline_at" in task_columns
        assert {"rejected_at", "timed_out_at"}.issubset(outbound_columns)
        assert "ix_chain_xiaoyi_tasks_quote_deadline_at" in {
            index["name"] for index in inspector.get_indexes("chain_xiaoyi_tasks")
        }

        migration.downgrade()
        inspector = sa.inspect(connection)
        assert "quote_deadline_at" not in {column["name"] for column in inspector.get_columns("chain_xiaoyi_tasks")}

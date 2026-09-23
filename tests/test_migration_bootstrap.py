"""Production migration smoke tests.

The initial schema migration was historically generated from a populated
development database.  These tests exercise the actual Flask-Migrate command
against an empty SQLite database so a new deployment cannot regress to a
startup-only ``create_all`` assumption.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run_upgrade(database_url: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_URL": database_url,
            "AUTO_CREATE_SCHEMA": "0",
            "LIANYIPEI_SCHEDULER_ENABLED": "0",
            "DISABLE_API_AUTH": "1",
        }
    )
    return subprocess.run(
        [sys.executable, "-m", "flask", "--app", "wsgi:app", "db", "upgrade"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_empty_database_reaches_migration_head(tmp_path):
    database = tmp_path / "empty.sqlite"
    url = f"sqlite:///{database}"

    first = _run_upgrade(url)
    assert first.returncode == 0, first.stdout + first.stderr

    # A deployment retry must be safe and must not duplicate the compatibility
    # marker or any Agent constraints.
    second = _run_upgrade(url)
    assert second.returncode == 0, second.stdout + second.stderr

    connection = sqlite3.connect(database)
    try:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "lianyipei_schema_bootstrap" not in tables
        assert {
            "chain_xiaoyi_tasks",
            "chain_xiaoyi_candidate_snapshots",
            "chain_xiaoyi_outbound_records",
            "external_callback_receipts",
        }.issubset(tables)
        version = connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        assert version == "h3d4e5f6a7b8"
        canonical_columns = {
            row[1]: row[2]
            for row in connection.execute("PRAGMA table_info(industry_news_articles)")
        }
        assert canonical_columns["canonical_url"].upper() == "VARCHAR(700)"
        unique_indexes = connection.execute("PRAGMA index_list(intent_quotes)").fetchall()
        assert any(row[2] for row in unique_indexes), unique_indexes
    finally:
        connection.close()

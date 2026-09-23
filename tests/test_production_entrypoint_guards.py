"""Production must not execute destructive/demo bootstrap scripts."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("scripts/setup_and_start.py", "拒绝在 APP_ENV=production"),
        ("scripts/db/create_db.py", "拒绝在 APP_ENV=production"),
        ("scripts/db/create_test_accounts.py", "拒绝在 APP_ENV=production"),
        ("scripts/seed/seed_all_data.py", "拒绝在 APP_ENV=production"),
        ("scripts/seed/fresh_init.py", "拒绝在 APP_ENV=production"),
    ],
)
def test_destructive_bootstrap_scripts_fail_closed_in_production(script: str, expected: str):
    environment = dict(os.environ, APP_ENV="production")
    result = subprocess.run(
        [sys.executable, str(ROOT / script)],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=15,
    )

    assert result.returncode != 0
    assert expected in result.stdout + result.stderr

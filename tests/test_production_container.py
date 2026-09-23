from pathlib import Path
import os
import subprocess
import sys


def test_production_image_contains_bounded_pdf_ocr_runtime_dependencies():
    """The documented scanned-PDF path must exist in the production image."""
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "poppler-utils" in dockerfile
    assert "tesseract-ocr" in dockerfile
    assert "tesseract-ocr-chi-sim" in dockerfile


def test_production_compose_declares_clamav_platform_for_apple_silicon():
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.production.yml").read_text(encoding="utf-8")
    clamav_block = compose.split("\n  clamav:\n", 1)[1].split("\n  migrate:\n", 1)[0]
    assert "platform: linux/amd64" in clamav_block


def test_production_worker_runs_scheduler_as_module_from_image_workdir():
    """The split worker must keep /app on sys.path inside the image."""
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.production.yml").read_text(encoding="utf-8")
    worker_block = compose.split("\n  worker:\n", 1)[1]
    assert 'command: ["python", "-m", "scripts.run_scheduler"]' in worker_block
    assert "healthcheck:" in worker_block
    assert "disable: true" in worker_block


def test_production_compose_pins_runtime_dependency_digests():
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.production.yml").read_text(encoding="utf-8")
    for image in ("mysql@sha256:", "redis@sha256:", "clamav/clamav@sha256:", "quay.io/minio/minio@sha256:", "quay.io/minio/mc@sha256:"):
        assert image in compose


def test_production_compose_exposes_cloud_kill_switch_without_fake_key_requirement():
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.production.yml").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY: ${DEEPSEEK_API_KEY:-}" in compose
    assert 'CHAINXIAOYI_CLOUD_ENABLED: ${CHAINXIAOYI_CLOUD_ENABLED:-true}' in compose
    assert 'CHAINXIAOYI_CLOUD_REQUIRED: ${CHAINXIAOYI_CLOUD_REQUIRED:-true}' in compose


def test_production_compose_requires_trusted_browser_origins():
    compose = (Path(__file__).resolve().parents[1] / "docker-compose.production.yml").read_text(encoding="utf-8")
    assert "TRUSTED_ORIGINS: ${TRUSTED_ORIGINS:?set TRUSTED_ORIGINS}" in compose


def test_test_account_bootstrap_refuses_production_environment():
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, APP_ENV="production")
    result = subprocess.run(
        [sys.executable, "scripts/db/ensure_test_accounts.py"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "拒绝在 APP_ENV=production" in (result.stdout + result.stderr)

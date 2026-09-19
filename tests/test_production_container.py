from pathlib import Path


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

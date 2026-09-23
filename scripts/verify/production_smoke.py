"""Read-only production dependency smoke checks for Chain XiaoYi.

The normal admin readiness endpoint intentionally checks configuration without
contacting third parties. This command is the explicit operator step that
probes the configured dependencies before promotion. It never prints secret
values, and the DeepSeek request is opt-in because it consumes API quota.

Examples::

    ./.venv/bin/python scripts/verify/production_smoke.py --json
    ./.venv/bin/python scripts/verify/production_smoke.py --probe-deepseek
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def safe_error(error: BaseException) -> str:
    """Return an exception class only; messages may contain credentials/URLs."""
    return type(error).__name__


def _credential_present(value: Any) -> bool:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return False
    return not any(marker in candidate for marker in ("placeholder", "change-me", "changeme", "replace-me", "your-", "your_", "请填写", "请使用", "请从", "密钥管理系统"))


def _check(name: str, *, ok: bool, required: bool, started: float, reason: str | None = None, status: str | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "name": name,
        "ok": bool(ok),
        "required": bool(required),
        "status": status or ("ok" if ok else "failed"),
        "duration_ms": int((time.monotonic() - started) * 1000),
    }
    if reason:
        row["reason"] = reason
    return row


def probe_database(app, *, required: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    try:
        from app import db

        with app.app_context():
            db.session.execute(text("SELECT 1"))
            db.session.rollback()
        return _check("database", ok=True, required=required, started=started)
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("database", ok=False, required=required, started=started, reason=safe_error(error))


def probe_redis(app, *, required: bool = False) -> dict[str, Any]:
    started = time.monotonic()
    try:
        import redis

        url = str(app.config.get("REDIS_URL") or "").strip()
        if not url:
            return _check("redis", ok=False, required=required, started=started, reason="missing_url")
        redis.Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2).ping()
        return _check("redis", ok=True, required=required, started=started)
    except ImportError:
        return _check("redis", ok=False, required=required, started=started, reason="dependency_missing")
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("redis", ok=False, required=required, started=started, reason=safe_error(error))


def probe_clamav(app, *, required: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    host = str(app.config.get("CLAMAV_HOST") or "").strip()
    if host:
        try:
            from app.services.material_security import ping_clamd

            ok = ping_clamd(
                host=host,
                port=int(app.config.get("CLAMAV_PORT") or 3310),
                timeout=min(float(app.config.get("CLAMAV_TIMEOUT_SECONDS") or 30), 5.0),
            )
            return _check(
                "clamav",
                ok=ok,
                required=required,
                started=started,
                reason=None if ok else "clamd_unreachable",
            )
        except (TypeError, ValueError):
            return _check("clamav", ok=False, required=required, started=started, reason="invalid_tcp_config")
    command = str(app.config.get("CLAMAV_COMMAND") or "clamscan").strip()
    executable = shutil.which(command)
    if not executable:
        return _check("clamav", ok=False, required=required, started=started, reason="executable_missing")
    try:
        subprocess.run([executable, "--version"], check=True, capture_output=True, timeout=5)
        return _check("clamav", ok=True, required=required, started=started)
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("clamav", ok=False, required=required, started=started, reason=safe_error(error))


def probe_s3(app, *, required: bool = True) -> dict[str, Any]:
    started = time.monotonic()
    bucket = str(app.config.get("MATERIAL_S3_BUCKET") or "").strip()
    if not bucket:
        return _check("s3", ok=False, required=required, started=started, reason="missing_bucket")
    try:
        from app.services.material_storage import _s3_client

        with app.app_context():
            _s3_client().head_bucket(Bucket=bucket)
        return _check("s3", ok=True, required=required, started=started)
    except ImportError:
        return _check("s3", ok=False, required=required, started=started, reason="dependency_missing")
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("s3", ok=False, required=required, started=started, reason=safe_error(error))


def probe_worker(app, *, required: bool) -> dict[str, Any]:
    started = time.monotonic()
    try:
        from app.services.production_readiness import _queue_worker_configured

        with app.app_context():
            ok = bool(_queue_worker_configured())
        return _check("worker", ok=ok, required=required, started=started, reason=None if ok else "worker_not_detected")
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("worker", ok=False, required=required, started=started, reason=safe_error(error))


def probe_trusted_origins(app, *, required: bool) -> dict[str, Any]:
    """Check that browser write origins are explicit and HTTPS in production."""
    started = time.monotonic()
    try:
        from app.services.production_readiness import _browser_origins_ready

        production = str(app.config.get("APP_ENV") or "development").lower() == "production"
        ok = _browser_origins_ready(app.config.get("TRUSTED_ORIGINS"), require_https=production)
        return _check(
            "trusted_origins",
            ok=ok,
            required=required,
            started=started,
            reason=None if ok else "missing_or_invalid_origins",
        )
    except Exception as error:  # pragma: no cover - exercised by deployment
        return _check("trusted_origins", ok=False, required=required, started=started, reason=safe_error(error))


def probe_deepseek(app) -> dict[str, Any]:
    """Send one minimal non-business prompt without returning model content."""
    started = time.monotonic()
    if not _credential_present(os.getenv("DEEPSEEK_API_KEY")):
        return _check("deepseek", ok=False, required=bool(app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")), started=started, reason="missing_key")
    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from app.services.deepseek_client import create_deepseek_chat_model_from_env

        reply = create_deepseek_chat_model_from_env().invoke([
            SystemMessage(content="只回复 OK，不要输出其他内容。"),
            HumanMessage(content="生产连通性检查"),
        ])
        content = getattr(reply, "content", None)
        if not str(content or "").strip():
            return _check("deepseek", ok=False, required=bool(app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")), started=started, reason="empty_response")
        return _check("deepseek", ok=True, required=bool(app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")), started=started)
    except Exception as error:  # pragma: no cover - requires provider outage
        return _check("deepseek", ok=False, required=bool(app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")), started=started, reason=safe_error(error))


def run_smoke(app, *, probe_deepseek_enabled: bool = False) -> dict[str, Any]:
    """Run non-mutating checks and return a redacted JSON-serializable report."""
    production = str(app.config.get("APP_ENV") or "development").lower() == "production"
    checks = {
        "database": probe_database(app, required=True),
        "redis": probe_redis(app, required=production),
        "clamav": probe_clamav(app, required=production),
        "s3": probe_s3(app, required=production),
        "worker": probe_worker(app, required=production),
        "trusted_origins": probe_trusted_origins(app, required=production),
        "deepseek": probe_deepseek(app) if probe_deepseek_enabled else _check(
            "deepseek",
            # The normal smoke command is intentionally non-billable.  It
            # verifies that the required credential is present; only the
            # explicit --probe-deepseek flag performs a network request.
            ok=_credential_present(os.getenv("DEEPSEEK_API_KEY")),
            required=bool(app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")),
            started=time.monotonic(),
            status="skipped",
            reason="explicit_probe_required",
        ),
    }
    required_failures = [name for name, row in checks.items() if row["required"] and not row["ok"]]
    return {
        "ready": not required_failures,
        "environment": str(app.config.get("APP_ENV") or "development"),
        "checks": checks,
        "required_failures": required_failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="链小易生产依赖只读验收")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    parser.add_argument("--probe-deepseek", action="store_true", help="显式发送一次最小 DeepSeek 请求（消耗少量配额）")
    args = parser.parse_args()
    try:
        from app import create_app

        app = create_app()
        report = run_smoke(app, probe_deepseek_enabled=args.probe_deepseek)
    except Exception as error:
        report = {"ready": False, "environment": os.getenv("APP_ENV", "unknown"), "checks": {}, "required_failures": ["application_startup"], "startup_error": safe_error(error)}
    print(json.dumps(report, ensure_ascii=False, indent=None if args.json else 2, sort_keys=True))
    return 0 if report.get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())

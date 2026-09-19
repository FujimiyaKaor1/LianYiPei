"""Production readiness checks that are safe to expose to administrators.

The report intentionally contains provider names and boolean state only. Secret
values, URLs containing credentials, and configuration values are never
returned so it is safe to render in an operations dashboard.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from flask import current_app
from sqlalchemy import inspect

from app import db


def _present(value: Any) -> bool:
    return bool(str(value or "").strip())


def _enabled_flag(value: Any) -> bool:
    """Interpret process flags explicitly so ``0``/``false`` cannot pass.

    Deployment manifests commonly inject both ``..._ENABLED=1`` and
    ``..._ENABLED=0``.  Treating any non-empty string as enabled would make a
    web-only process look like it had a durable worker.
    """
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


_PLACEHOLDER_MARKERS = (
    "placeholder",
    "change-me",
    "changeme",
    "replace-me",
    "your-",
    "your_",
    "请填写",
    "请使用",
    "请从",
    "密钥管理系统",
)


def _credential_present(value: Any) -> bool:
    """Return true only for an injected credential, not a template prompt.

    Production env templates intentionally contain human-readable prompts. A
    non-empty prompt must not make readiness claim that an integration is
    configured. The function returns only a boolean and never exposes the
    credential or its contents in the readiness report.
    """
    if not _present(value):
        return False
    candidate = str(value).strip().lower()
    return not any(marker.lower() in candidate for marker in _PLACEHOLDER_MARKERS)


def _provider_url_safe(value: Any, *, require_https: bool) -> bool:
    """Validate an integration URL without returning the configured value."""
    raw = str(value or "").strip()
    if not raw:
        return False
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    return not require_https or parsed.scheme == "https"


def _external_interface_ready(raw: Any, *, require_https: bool) -> bool:
    """Check a configured business-data provider without exposing secrets."""
    if not isinstance(raw, dict) or not bool(raw.get("is_enabled")):
        return False
    if not _provider_url_safe(raw.get("base_url"), require_https=require_https):
        return False
    auth_type = str(raw.get("auth_type") or "").strip().lower()
    if auth_type == "api_key":
        return _credential_present(raw.get("api_key"))
    if auth_type == "oauth2":
        return _credential_present(raw.get("client_id")) and _credential_present(raw.get("client_secret"))
    return auth_type in {"none", ""}


def _check(configured: bool, *, required: bool, provider: str | None = None, reason: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "configured": bool(configured),
        "required": bool(required),
        "status": "ok" if configured else ("required_missing" if required else "optional_missing"),
    }
    if provider:
        result["provider"] = provider
    if reason:
        result["reason"] = reason
    return result


def _fernet_configured() -> bool:
    raw = current_app.config.get("MATERIAL_ENCRYPTION_KEY")
    if not _credential_present(raw):
        return False
    try:
        Fernet(str(raw).encode("ascii"))
        return True
    except (ValueError, TypeError):
        return False


def _queue_worker_configured() -> bool:
    """Check whether a process can actually drain durable Agent jobs.

    The explicit worker/broker flags cover a split production deployment. A
    running in-process scheduler is valid for the local single-process demo,
    but merely enabling the scheduler setting is not enough when another
    process owns the lock.
    """
    if _enabled_flag(os.getenv("LIANYIPEI_WORKER_ENABLED")) or _credential_present(os.getenv("CELERY_BROKER_URL")):
        return True
    try:
        from app.services import scheduler as scheduler_module

        if scheduler_module.scheduler and scheduler_module.scheduler.running:
            return True
    except Exception:
        pass

    # In the recommended split deployment the web process cannot see the
    # scheduler object, so use its lock file as a narrow liveness signal. Do
    # not use this shortcut in tests, where a developer's local lock must not
    # affect deterministic assertions.
    if current_app.testing:
        return False
    lock_path = str(current_app.config.get("SCHEDULER_LOCK_FILE") or "").strip()
    if not lock_path:
        return False
    try:
        with open(lock_path, "r", encoding="ascii") as lock_file:
            raw_pid = lock_file.read().strip()
        pid = int(raw_pid)
        if pid <= 0:
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ValueError):
        return False


def _agent_schema_ready() -> bool:
    """Verify only the minimum durable Agent schema without exposing names."""
    try:
        inspector = inspect(db.engine)
        required_tables = {
            "chain_xiaoyi_tasks",
            "chain_xiaoyi_candidate_snapshots",
            "chain_xiaoyi_outbound_records",
            "external_callback_receipts",
            "intent_quotes",
        }
        tables = set(inspector.get_table_names())
        if not required_tables.issubset(tables):
            return False
        quote_columns = {column["name"] for column in inspector.get_columns("intent_quotes")}
        callback_columns = {column["name"] for column in inspector.get_columns("external_callback_receipts")}
        columns_ready = {"seller_reply_details", "source_rfq_task_id"}.issubset(quote_columns) and {
            "provider",
            "event_key",
            "status",
            "response_body",
        }.issubset(callback_columns)
        expected_unique_sets = {
            "intent_quotes": {"source_rfq_task_id", "seller_id"},
            "external_callback_receipts": {"provider", "event_key"},
            "chain_xiaoyi_outbound_records": {"task_id", "supplier_id"},
        }
        uniqueness_ready = all(
            any(set(constraint.get("column_names") or []) == expected for constraint in inspector.get_unique_constraints(table))
            for table, expected in expected_unique_sets.items()
        )
        return columns_ready and uniqueness_ready
    except Exception:
        return False


def build_readiness_report() -> dict[str, Any]:
    """Build a redacted readiness report without contacting external systems."""
    cfg = current_app.config
    # This endpoint answers “can this deployment be promoted to production?”
    # even when called from development or CI, so production prerequisites are
    # always evaluated as required. Optional business integrations remain
    # informational and do not block the result.
    required = True

    ext = cfg.get("EXTERNAL_INTERFACES") or {}
    inbound_callback_url = str(cfg.get("INBOUND_EMAIL_CALLBACK_URL") or "").strip()
    inbound_url_safe = bool(inbound_callback_url) and (
        str(cfg.get("APP_ENV") or "development").lower() != "production"
        or urlparse(inbound_callback_url).scheme == "https"
    )
    production_environment = str(cfg.get("APP_ENV") or "development").lower() == "production"
    econtract_provider = str(cfg.get("ECONTRACT_PROVIDER") or "disabled").strip().lower()
    econtract_configured = (
        econtract_provider != "disabled"
        and _credential_present(cfg.get("ECONTRACT_API_KEY"))
        and _provider_url_safe(cfg.get("ECONTRACT_BASE_URL"), require_https=production_environment)
    )
    checks = {
        "secret_key": _check(
            not bool(cfg.get("SECRET_KEY_IS_DEFAULT"))
            and _credential_present(cfg.get("SECRET_KEY"))
            and len(str(cfg.get("SECRET_KEY") or "")) >= 32,
            required=required,
            provider="application_secret",
        ),
        "authentication": _check(not bool(cfg.get("DISABLE_API_AUTH")), required=required, provider="session_auth"),
        "mock_api_disabled": _check(not bool(cfg.get("ENABLE_MOCK_API")), required=required, provider="production_routes"),
        "explicit_approval": _check(bool(cfg.get("CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL")), required=required, provider="chain_xiaoyi_approval"),
        "deepseek": _check(
            _credential_present(os.getenv("DEEPSEEK_API_KEY")),
            required=bool(cfg.get("CHAINXIAOYI_CLOUD_REQUIRED")),
            provider="deepseek",
        ),
        "database": _check(bool(cfg.get("DATABASE_URL_CONFIGURED")), required=required, provider="configured_database"),
        "agent_schema": _check(_agent_schema_ready(), required=required, provider="durable_agent_schema"),
        "material_antivirus": _check(str(cfg.get("MATERIAL_AV_MODE") or "").lower() == "clamav", required=required, provider=str(cfg.get("MATERIAL_AV_MODE") or "unset")),
        "material_storage": _check(str(cfg.get("MATERIAL_STORAGE_BACKEND") or "").lower() == "s3" and _credential_present(cfg.get("MATERIAL_S3_BUCKET")), required=required, provider=str(cfg.get("MATERIAL_STORAGE_BACKEND") or "unset")),
        "material_encryption": _check(_fernet_configured(), required=required, provider="fernet"),
        "econtract": _check(econtract_configured, required=False, provider=econtract_provider),
        "payment": _check(_credential_present(os.getenv("PAYMENT_PROVIDER")) and _credential_present(os.getenv("PAYMENT_API_KEY")) and _credential_present(os.getenv("PAYMENT_BASE_URL")), required=False, provider=os.getenv("PAYMENT_PROVIDER") or "disabled"),
        "smtp": _check(all(_credential_present(cfg.get(name)) for name in ("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD", "SMTP_FROM_EMAIL")), required=False, provider="smtp"),
        "rfq_delivery_callbacks": _check(_credential_present(cfg.get("RFQ_DELIVERY_CALLBACK_SECRET")), required=False, provider="hmac_callback"),
        "rfq_quote_callbacks": _check(_credential_present(cfg.get("RFQ_QUOTE_CALLBACK_SECRET")), required=False, provider="hmac_quote_callback"),
        "rfq_email_inbound": _check(
            _credential_present(cfg.get("RFQ_EMAIL_INBOUND_SECRET")) or _credential_present(os.getenv("RFQ_EMAIL_INBOUND_SECRET")),
            required=False,
            provider="hmac_email_inbound",
        ),
        "fulfillment_callbacks": _check(
            _credential_present(cfg.get("FULFILLMENT_CALLBACK_SECRET")) or _credential_present(os.getenv("FULFILLMENT_CALLBACK_SECRET")),
            required=False,
            provider="hmac_fulfillment_event",
        ),
        "inbound_email_worker": _check(
            not bool(cfg.get("INBOUND_EMAIL_ENABLED"))
            or all(
                _credential_present(cfg.get(name))
                for name in (
                    "INBOUND_IMAP_HOST",
                    "INBOUND_IMAP_USERNAME",
                    "INBOUND_IMAP_PASSWORD",
                    "RFQ_EMAIL_INBOUND_SECRET",
                )
            ) and inbound_url_safe,
            required=False,
            provider="imap_email_quote_worker",
            reason="disabled" if not cfg.get("INBOUND_EMAIL_ENABLED") else None,
        ),
        "work_wechat": _check(all(_credential_present(cfg.get(name)) for name in ("WORK_WECHAT_CORPID", "WORK_WECHAT_CORPSECRET", "WORK_WECHAT_AGENTID", "WORK_WECHAT_CALLBACK_TOKEN", "WORK_WECHAT_ENCODING_AES_KEY")), required=False, provider="wecom"),
        "business_data": _check(_external_interface_ready(ext.get("industrial_commerce_api"), require_https=production_environment), required=False, provider="business_registry"),
        "tax_data": _check(_external_interface_ready(ext.get("tax_api"), require_https=production_environment), required=False, provider="tax_api"),
        "power_data": _check(_external_interface_ready(ext.get("power_api"), require_https=production_environment), required=False, provider="power_api"),
        # A split deployment intentionally disables APScheduler in the web
        # process and runs the durable queue in a dedicated worker. Requiring
        # both flags made the documented production topology report a false
        # negative, so scheduler is informational while ``worker`` below is
        # the actual background-execution gate.
        "scheduler": _check(bool(cfg.get("SCHEDULER_ENABLED")), required=False, provider="scheduler"),
        "worker": _check(
            _queue_worker_configured(),
            required=str(cfg.get("APP_ENV") or "development").lower() == "production",
            provider="worker_or_scheduler",
        ),
    }
    required_failures = [name for name, value in checks.items() if value["required"] and not value["configured"]]
    return {
        "ready": not required_failures,
        "environment": str(cfg.get("APP_ENV") or "development"),
        "checks": checks,
        "required_failures": required_failures,
    }

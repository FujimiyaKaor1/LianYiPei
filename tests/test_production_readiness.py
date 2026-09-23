import os

import pytest
from cryptography.fernet import Fernet
from flask_login import login_user

from app.services.production_readiness import build_readiness_report


@pytest.mark.unit
def test_readiness_report_never_contains_secret_values(app, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "super-secret-deepseek-key")
    with app.app_context():
        report = build_readiness_report()
    rendered = repr(report)
    assert "super-secret-deepseek-key" not in rendered
    assert report["checks"]["deepseek"]["configured"] is True
    assert "DEEPSEEK_API_KEY" not in report["checks"]["deepseek"]


@pytest.mark.unit
def test_readiness_can_require_deepseek_in_production(app, monkeypatch):
    monkeypatch.setitem(app.config, "CHAINXIAOYI_CLOUD_REQUIRED", True)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["deepseek"]["required"] is True
    assert "deepseek" in report["required_failures"]


@pytest.mark.unit
def test_readiness_rejects_placeholder_provider_credentials(app, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "请从密钥管理系统注入")
    monkeypatch.setitem(app.config, "MATERIAL_ENCRYPTION_KEY", "请从密钥管理系统注入Fernet密钥")
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["deepseek"]["configured"] is False
    assert report["checks"]["material_encryption"]["configured"] is False
    rendered = repr(report)
    assert "密钥管理系统" not in rendered


@pytest.mark.unit
def test_readiness_reports_email_quote_inbound_secret_without_leaking_it(app, monkeypatch):
    monkeypatch.setenv("RFQ_EMAIL_INBOUND_SECRET", "inbound-secret-value")
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["rfq_email_inbound"]["configured"] is True
    assert "inbound-secret-value" not in repr(report)
    assert "RFQ_EMAIL_INBOUND_SECRET" not in repr(report["checks"]["rfq_email_inbound"])


@pytest.mark.integration
def test_readiness_endpoint_requires_admin(client, test_enterprise, test_admin):
    assert client.get("/api/admin/production-readiness").status_code == 401
    with client:
        with client.session_transaction() as session:
            login_user(test_enterprise)
        assert client.get("/api/admin/production-readiness").status_code == 403
    with client:
        with client.session_transaction() as session:
            login_user(test_admin)
        response = client.get("/api/admin/production-readiness")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "checks" in payload["data"]
    assert "DEEPSEEK_API_KEY" not in repr(payload)


@pytest.mark.unit
def test_production_required_checks_are_not_ready_by_default(app):
    with app.app_context():
        report = build_readiness_report()
    assert report["environment"] == "development"
    assert report["ready"] is False
    assert report["required_failures"]


@pytest.mark.integration
def test_readiness_checks_auth_mock_secret_and_agent_schema(app, _db, monkeypatch):
    monkeypatch.setitem(app.config, "SECRET_KEY", "x" * 48)
    monkeypatch.setitem(app.config, "SECRET_KEY_IS_DEFAULT", False)
    monkeypatch.setitem(app.config, "DISABLE_API_AUTH", False)
    monkeypatch.setitem(app.config, "ENABLE_MOCK_API", False)

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["secret_key"]["configured"] is True
    assert report["checks"]["authentication"]["configured"] is True
    assert report["checks"]["mock_api_disabled"]["configured"] is True
    assert report["checks"]["agent_schema"]["configured"] is True
    assert "source_rfq_task_id" not in repr(report["checks"]["agent_schema"])


@pytest.mark.unit
def test_production_readiness_requires_https_browser_origin(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "TRUSTED_ORIGINS", ["http://localhost:3000"])

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["trusted_origins"]["configured"] is False
    assert "trusted_origins" in report["required_failures"]


@pytest.mark.unit
def test_production_readiness_rejects_origin_template_placeholder(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "TRUSTED_ORIGINS", ["https://your-domain.example"])

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["trusted_origins"]["configured"] is False


@pytest.mark.unit
def test_production_readiness_rejects_demo_public_data_label(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "PUBLIC_DATA_MODE", "demo")

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["public_data_mode"]["required"] is True
    assert report["checks"]["public_data_mode"]["configured"] is False
    assert "public_data_mode" in report["required_failures"]


@pytest.mark.unit
def test_readiness_requires_explicit_rfq_approval(app, monkeypatch):
    monkeypatch.setitem(app.config, "CHAINXIAOYI_REQUIRE_EXPLICIT_APPROVAL", False)
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["explicit_approval"]["required"] is True
    assert "explicit_approval" in report["required_failures"]


@pytest.mark.unit
def test_readiness_accepts_a_valid_material_encryption_key(app, monkeypatch):
    monkeypatch.setitem(app.config, "MATERIAL_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["material_encryption"]["configured"] is True
    assert report["checks"]["material_encryption"]["status"] == "ok"


@pytest.mark.unit
def test_production_readiness_requires_a_real_background_worker(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "SCHEDULER_ENABLED", False)
    monkeypatch.delenv("LIANYIPEI_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["worker"]["required"] is True
    assert report["checks"]["worker"]["configured"] is False
    assert "worker" in report["required_failures"]


@pytest.mark.unit
def test_worker_flag_alone_does_not_claim_a_background_worker(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "SCHEDULER_ENABLED", False)
    monkeypatch.setenv("LIANYIPEI_WORKER_ENABLED", "1")
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["scheduler"]["required"] is False
    assert report["checks"]["scheduler"]["configured"] is False
    assert report["checks"]["worker"]["configured"] is False
    assert "worker" in report["required_failures"]


@pytest.mark.unit
def test_worker_flag_zero_does_not_claim_a_background_worker(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "SCHEDULER_ENABLED", False)
    monkeypatch.setenv("LIANYIPEI_WORKER_ENABLED", "0")
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)

    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["worker"]["configured"] is False
    assert "worker" in report["required_failures"]


@pytest.mark.unit
def test_split_worker_heartbeat_is_visible_across_pid_namespaces(app, monkeypatch):
    import sys
    import types

    class _RedisClient:
        def get(self, key):
            assert key == "lianyipei:worker:heartbeat"
            return b"worker-host:123"

    fake_redis = types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *args, **kwargs: _RedisClient()))
    monkeypatch.setitem(sys.modules, "redis", fake_redis)
    # This test intentionally models the production process rather than the
    # Flask test isolation path below.
    monkeypatch.setitem(app.config, "TESTING", False)
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "SCHEDULER_ENABLED", False)
    monkeypatch.delenv("LIANYIPEI_WORKER_ENABLED", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    with app.app_context():
        report = build_readiness_report()

    assert report["checks"]["worker"]["configured"] is True
    assert "worker" not in report["required_failures"]


@pytest.mark.unit
def test_readiness_detects_incomplete_enabled_email_worker(app, monkeypatch):
    monkeypatch.setitem(app.config, "INBOUND_EMAIL_ENABLED", True)
    for name in (
        "INBOUND_IMAP_HOST",
        "INBOUND_IMAP_USERNAME",
        "INBOUND_IMAP_PASSWORD",
        "INBOUND_EMAIL_CALLBACK_URL",
        "RFQ_EMAIL_INBOUND_SECRET",
    ):
        monkeypatch.setitem(app.config, name, "")
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["inbound_email_worker"]["configured"] is False


@pytest.mark.unit
def test_production_email_worker_requires_https_callback(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "INBOUND_EMAIL_ENABLED", True)
    for name, value in {
        "INBOUND_IMAP_HOST": "imap.example.com",
        "INBOUND_IMAP_USERNAME": "worker@example.com",
        "INBOUND_IMAP_PASSWORD": "password",
        "RFQ_EMAIL_INBOUND_SECRET": "secret",
        "INBOUND_EMAIL_CALLBACK_URL": "http://example.com/api/chain-xiaoyi/email-quote-inbound",
    }.items():
        monkeypatch.setitem(app.config, name, value)
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["inbound_email_worker"]["configured"] is False


@pytest.mark.unit
def test_production_readiness_rejects_insecure_econtract_endpoint(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "ECONTRACT_PROVIDER", "custom")
    monkeypatch.setitem(app.config, "ECONTRACT_API_KEY", "provider-key")
    monkeypatch.setitem(app.config, "ECONTRACT_BASE_URL", "http://contracts.example.test/api")
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["econtract"]["configured"] is False

    monkeypatch.setitem(app.config, "ECONTRACT_BASE_URL", "https://contracts.example.test/api")
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["econtract"]["configured"] is True


@pytest.mark.unit
def test_production_readiness_rejects_insecure_external_data_endpoints(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(
        app.config,
        "EXTERNAL_INTERFACES",
        {
            "industrial_commerce_api": {
                "is_enabled": True,
                "base_url": "http://registry.example/api",
                "auth_type": "api_key",
                "api_key": "provider-key",
            },
            "tax_api": {"is_enabled": False},
            "power_api": {"is_enabled": False},
        },
    )
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["business_data"]["configured"] is False

    monkeypatch.setitem(
        app.config["EXTERNAL_INTERFACES"]["industrial_commerce_api"],
        "base_url",
        "https://registry.example/api",
    )
    with app.app_context():
        report = build_readiness_report()
    assert report["checks"]["business_data"]["configured"] is True

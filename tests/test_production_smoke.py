from scripts.verify.production_smoke import run_smoke, safe_error


def test_clamav_smoke_uses_private_clamd_when_configured(app, monkeypatch):
    monkeypatch.setitem(app.config, "CLAMAV_HOST", "clamav")
    monkeypatch.setitem(app.config, "CLAMAV_PORT", 3310)
    monkeypatch.setattr("app.services.material_security.ping_clamd", lambda **_kwargs: True)

    from scripts.verify.production_smoke import probe_clamav

    with app.app_context():
        result = probe_clamav(app, required=True)
    assert result["ok"] is True
    assert result["status"] == "ok"


def test_safe_error_never_returns_exception_text_or_secrets():
    error = safe_error(RuntimeError("Authorization Bearer secret-value"))
    assert error == "RuntimeError"
    assert "secret" not in error.lower()


def test_smoke_does_not_call_deepseek_without_explicit_probe(app, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "secret-value-that-must-not-print")

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("DeepSeek probe must be opt-in")

    monkeypatch.setattr("scripts.verify.production_smoke.probe_deepseek", fail_if_called)
    report = run_smoke(app, probe_deepseek_enabled=False)
    assert report["checks"]["deepseek"]["status"] == "skipped"
    assert "secret-value" not in str(report)


def test_smoke_calls_deepseek_only_when_explicitly_enabled(app, monkeypatch):
    called = {"value": False}

    def fake_probe(_app):
        called["value"] = True
        return {"name": "deepseek", "ok": True, "required": False, "status": "ok", "duration_ms": 0}

    monkeypatch.setattr("scripts.verify.production_smoke.probe_deepseek", fake_probe)
    report = run_smoke(app, probe_deepseek_enabled=True)
    assert called["value"] is True
    assert report["checks"]["deepseek"]["status"] == "ok"


def test_production_smoke_accepts_configured_deepseek_without_billable_probe(app, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    monkeypatch.setitem(app.config, "TRUSTED_ORIGINS", ["https://app.example.com"])
    monkeypatch.setitem(app.config, "CHAINXIAOYI_CLOUD_REQUIRED", True)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "configured-test-key")
    monkeypatch.setattr("scripts.verify.production_smoke.probe_database", lambda *_args, **_kwargs: {"name": "database", "ok": True, "required": True})
    monkeypatch.setattr("scripts.verify.production_smoke.probe_redis", lambda *_args, **_kwargs: {"name": "redis", "ok": True, "required": True})
    monkeypatch.setattr("scripts.verify.production_smoke.probe_clamav", lambda *_args, **_kwargs: {"name": "clamav", "ok": True, "required": True})
    monkeypatch.setattr("scripts.verify.production_smoke.probe_s3", lambda *_args, **_kwargs: {"name": "s3", "ok": True, "required": True})
    monkeypatch.setattr("scripts.verify.production_smoke.probe_worker", lambda *_args, **_kwargs: {"name": "worker", "ok": True, "required": True})

    report = run_smoke(app, probe_deepseek_enabled=False)

    assert report["checks"]["deepseek"]["ok"] is True
    assert report["checks"]["deepseek"]["status"] == "skipped"
    assert report["ready"] is True

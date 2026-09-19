import pytest
from unittest.mock import patch

from app.applications.fulfillment.services.contract_service import (
    EContractConfigurationError,
    EContractService,
)


def test_unconfigured_econtract_never_generates_local_success(_db, test_enterprise, test_supplier):
    service = EContractService(provider="disabled")
    with pytest.raises(EContractConfigurationError, match="禁止使用模拟"):
        service.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})


def test_provider_failure_does_not_fake_contract_or_signature(_db, test_enterprise, test_supplier, monkeypatch):
    service = EContractService(provider="custom", api_key="test-only", base_url="https://contracts.example.test")

    def fail(*_args, **_kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(service, "_call_api", fail)
    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})
    with pytest.raises(RuntimeError, match="provider unavailable"):
        service.sign_contract("contract-1", test_enterprise.id, {"signature_type": "digital"})


def test_real_provider_calls_include_stable_idempotency_keys(_db, test_enterprise, test_supplier):
    service = EContractService(provider="custom", api_key="test-only", base_url="https://contracts.example.test")
    captured = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"contract_id": "provider-contract-1"}

    def fake_post(url, **kwargs):
        captured.append((url, kwargs))
        return Response()

    with patch("app.applications.fulfillment.services.contract_service.requests.post", fake_post):
        first = service.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})
        second = service.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})

    assert first == second == "provider-contract-1"
    assert captured[0][1]["headers"]["Idempotency-Key"]
    assert captured[0][1]["headers"]["Idempotency-Key"] == captured[1][1]["headers"]["Idempotency-Key"]


def test_production_econtract_rejects_insecure_or_credential_urls(app, _db, test_enterprise, test_supplier, monkeypatch):
    """Production contract calls must not send credentials over HTTP or URL userinfo."""
    monkeypatch.setitem(app.config, "APP_ENV", "production")

    insecure = EContractService(
        provider="custom",
        api_key="test-only",
        base_url="http://contracts.example.test/api",
    )
    with pytest.raises(EContractConfigurationError, match="HTTPS"):
        insecure.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})

    credential_url = EContractService(
        provider="custom",
        api_key="test-only",
        base_url="https://user:password@contracts.example.test/api",
    )
    with pytest.raises(EContractConfigurationError, match="URL"):
        credential_url.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})


def test_development_econtract_rejects_malformed_base_url(_db, test_enterprise, test_supplier):
    """Even development adapters must reject malformed provider endpoints."""
    service = EContractService(provider="custom", api_key="test-only", base_url="not-a-url")
    with pytest.raises(EContractConfigurationError, match="URL"):
        service.generate_contract(test_enterprise.id, test_supplier.id, "连接器", {"quantity": 100})

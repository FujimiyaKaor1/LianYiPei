"""生产外部数据不可用时必须失败关闭，不能制造企业事实。"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app import db
from app.applications.enterprise.services.verification_service import check_single_enterprise
from app.models import Enterprise
from app.services import external_data_service as external
from app.services.recruitment_service import recommend_potential_enterprises


@pytest.fixture(autouse=True)
def disabled_external_interfaces(monkeypatch):
    monkeypatch.setattr(
        external,
        "_interface_runtime_state",
        {
            "power_api": {"interface_type": "power_api", "is_enabled": False},
            "tax_api": {"interface_type": "tax_api", "is_enabled": False},
            "industrial_commerce_api": {
                "interface_type": "industrial_commerce_api",
                "is_enabled": False,
            },
        },
    )
    external._industrial_memory_cache.clear()


def test_power_and_tax_data_do_not_fall_back_to_random_values(app, _db):
    with pytest.raises(external.ExternalDataUnavailable, match="电力"):
        external.power_api_service.fetch_power_consumption(1)
    with pytest.raises(external.ExternalDataUnavailable, match="税务"):
        external.tax_api_service.fetch_invoice_data(1)


def test_industrial_commerce_does_not_invent_companies_or_status(app, _db):
    with pytest.raises(external.ExternalDataUnavailable, match="工商"):
        external.industrial_commerce_service.query_enterprises("连接器")
    with pytest.raises(external.ExternalDataUnavailable, match="工商"):
        external.industrial_commerce_service.check_enterprise_status("某企业")


def test_recruitment_uses_only_internal_candidates_when_external_is_unavailable(app, _db):
    enterprise = Enterprise(
        name="广东真实连接器有限公司",
        role="enterprise",
        business_scope="连接器研发与生产",
        verification_status="approved",
        is_verified=True,
    )
    db.session.add(enterprise)
    db.session.commit()

    results = recommend_potential_enterprises(
        {
            "product_name": "连接器",
            "suggestion": {"enterprise_type": "电子制造企业"},
        }
    )

    assert [item["name"] for item in results] == [enterprise.name]
    assert all(item["source"] != "mock" for item in results)


def test_recruitment_excludes_demo_enterprises_and_redacts_unclaimed_contacts(app, _db):
    demo = Enterprise(
        name="演示连接器企业",
        role="enterprise",
        business_scope="连接器研发与生产",
        verification_status="approved",
        is_verified=True,
        contact="演示联系人",
        phone="13800000000",
        extras={"is_demo": True, "trust_profile": {"claim_status": "claimed", "contact_authorized": True}},
    )
    real = Enterprise(
        name="未认领连接器企业",
        role="enterprise",
        business_scope="连接器研发与生产",
        verification_status="approved",
        is_verified=True,
        contact="不应公开的联系人",
        phone="13900000000",
        extras={"trust_profile": {"claim_status": "unclaimed", "contact_authorized": False}},
    )
    db.session.add_all([demo, real])
    db.session.commit()

    results = recommend_potential_enterprises(
        {"product_name": "连接器", "suggestion": {"enterprise_type": "电子制造企业"}}
    )

    assert [item["name"] for item in results] == [real.name]
    assert results[0]["contact"] == ""
    assert results[0]["phone"] == ""
    assert results[0]["contact_authorized"] is False
    assert results[0]["is_mock"] is False


def test_failed_status_check_does_not_overwrite_enterprise_state(app, _db):
    enterprise = Enterprise(
        name="待核验企业",
        role="enterprise",
        verification_status="approved",
        is_verified=True,
        business_status="存续",
    )
    db.session.add(enterprise)
    db.session.commit()

    result = check_single_enterprise(enterprise.id)

    assert result["success"] is False
    assert Enterprise.query.get(enterprise.id).business_status == "存续"


def test_mapped_company_data_contains_traceable_evidence(app, _db, monkeypatch):
    config = SimpleNamespace(
        interface_type="industrial_commerce_api",
        interface_name="工商数据接口",
        base_url="https://registry.example/api",
        auth_type="api_key",
        api_key="test-only",
        client_id="",
        client_secret="",
        timeout_seconds=1,
        max_retries=1,
        field_mapping=None,
        is_enabled=True,
    )
    monkeypatch.setattr(external.industrial_commerce_service, "get_config", lambda: config)
    with patch.object(
        external.ExternalAPIClient,
        "get",
        return_value={
            "data": [
                {
                    "name": "广东连接器有限公司",
                    "address": "广东省东莞市",
                    "business_scope": "连接器生产",
                }
            ]
        },
    ):
        results = external.industrial_commerce_service.query_enterprises("连接器")

    assert results[0]["source"] == "industrial_commerce_api"
    assert results[0]["source_url"] == "https://registry.example/api"
    assert results[0]["is_mock"] is False
    assert results[0]["collected_at"]
    assert results[0]["updated_at"]


def test_production_external_client_rejects_insecure_provider_url(app, _db, monkeypatch):
    config = SimpleNamespace(
        interface_type="industrial_commerce_api",
        base_url="http://registry.example/api",
        auth_type="api_key",
        api_key="provider-key",
        client_id="",
        client_secret="",
        timeout_seconds=1,
        max_retries=1,
    )
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    with pytest.raises(external.ExternalDataUnavailable, match="HTTPS"):
        external.ExternalAPIClient(config)

    config.base_url = "https://user:password@registry.example/api"
    with pytest.raises(external.ExternalDataUnavailable, match="URL"):
        external.ExternalAPIClient(config)

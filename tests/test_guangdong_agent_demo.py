import pytest

from app.models import Enterprise, Product
from app.services.chain_xiaoyi.orchestrator import _match
from scripts.seed.seed_guangdong_agent_demo import seed


def test_guangdong_demo_seed_is_idempotent_and_never_enters_production_matching(app, _db, monkeypatch):
    first = seed()
    second = seed()
    assert first["buyer_id"] == second["buyer_id"]
    assert len(second["supplier_ids"]) == 4
    assert Enterprise.query.filter(Enterprise.name.like("链易配演示·%")).count() == 5
    assert Product.query.join(Enterprise).filter(Enterprise.name.like("链易配演示·%")).count() == 8
    supplier = Enterprise.query.get(second["supplier_ids"][0])
    assert supplier.extras["is_demo"] is True
    assert supplier.extras["trust_profile"]["sources"][0]["is_mock"] is True
    assert "ISO 9001" in (supplier.qualifications or [])

    monkeypatch.setitem(app.config, "APP_ENV", "development")
    monkeypatch.setitem(app.config, "PUBLIC_DATA_MODE", "demo")
    demo_result, _ = _match({"product": "精密连接器", "region": "广东", "quantity": 1000, "raw_text": "找广东精密连接器"}, first["buyer_id"])
    assert any(row["id"] == supplier.id for row in demo_result["results"])

    certified_result, _ = _match(
        {
            "product": "精密连接器",
            "region": "广东",
            "certifications": ["ISO 9001"],
            "quantity": 1000,
            "raw_text": "找广东有 ISO 9001 的精密连接器",
        },
        first["buyer_id"],
    )
    assert any(row["id"] == supplier.id for row in certified_result["results"])

    monkeypatch.setitem(app.config, "APP_ENV", "production")
    production_result, _ = _match({"product": "精密连接器", "region": "广东", "quantity": 1000, "raw_text": "找广东精密连接器"}, first["buyer_id"])
    assert all(not row["name"].startswith("链易配演示·") for row in production_result["results"])


def test_guangdong_demo_seed_is_blocked_in_production(app, _db, monkeypatch):
    monkeypatch.setitem(app.config, "APP_ENV", "production")
    with pytest.raises(RuntimeError, match="禁止在 production"):
        seed()

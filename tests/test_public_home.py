"""公共平台首页与统一搜索接口测试。"""

from app import db
from app.models import Enterprise, Inquiry, Product, Transaction


def test_public_home_returns_platform_summary_without_auth(client, test_enterprise, test_supplier):
    product = Product(
        name="工业电机",
        description="高效工业电机",
        category="机械制造",
        enterprise_id=test_supplier.id,
    )
    inquiry = Inquiry(
        poster_id=test_enterprise.id,
        direction="demand",
        product=product,
        product_name="工业电机",
        quantity=100,
        unit="件",
        status="open",
    )
    db.session.add_all([product, inquiry])
    db.session.add(
        Transaction(
            buyer_id=test_enterprise.id,
            seller_id=test_supplier.id,
            product_name="工业电机",
            status="completed",
        )
    )
    db.session.commit()

    response = client.get("/api/public/home")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["stats"]["enterprise_count"] == 2
    assert payload["stats"]["product_count"] == 1
    assert payload["stats"]["active_demand_count"] == 1
    assert payload["stats"]["completed_transaction_count"] == 1
    assert payload["featured_enterprises"]
    assert payload["featured_products"][0]["title"] == "工业电机"
    assert "source" in payload["featured_enterprises"][0]
    assert "updated_at" in payload["featured_enterprises"][0]
    assert "is_demo" in payload["featured_enterprises"][0]
    assert "contact" not in payload["featured_enterprises"][0]
    assert "phone" not in payload["featured_enterprises"][0]
    assert "industrial_belts" in payload
    assert "public_services" in payload
    assert "data_freshness" in payload
    assert "verified_count" in payload["stats"]


def test_public_search_unifies_enterprise_product_and_demand_results(
    client, test_enterprise, test_supplier
):
    product = Product(
        name="精密电机",
        description="用于自动化设备",
        category="机械制造",
        enterprise_id=test_supplier.id,
    )
    inquiry = Inquiry(
        poster_id=test_enterprise.id,
        direction="demand",
        product=product,
        product_name="精密电机",
        quantity=20,
        unit="台",
        status="open",
    )
    db.session.add_all([product, inquiry])
    db.session.commit()

    response = client.get("/api/public/search?q=电机&type=all&per_page=20")

    assert response.status_code == 200
    payload = response.get_json()
    kinds = {item["kind"] for item in payload["results"]}
    assert {"enterprise", "product", "demand"}.issubset(kinds)
    assert all(item["requires_login_for_action"] is True for item in payload["results"])
    assert all("source" in item and "updated_at" in item for item in payload["results"])
    assert all("phone" not in item and "contact" not in item for item in payload["results"])


def test_public_search_filters_by_type_and_paginates(client, test_supplier):
    for index in range(3):
        db.session.add(
            Product(
                name=f"传感器-{index}",
                category="电子信息",
                enterprise_id=test_supplier.id,
            )
        )
    db.session.commit()

    response = client.get(
        "/api/public/search?q=传感器&type=product&page=1&per_page=2"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["type"] == "product"
    assert payload["total"] == 3
    assert len(payload["results"]) == 2
    assert payload["has_more"] is True
    assert {item["kind"] for item in payload["results"]} == {"product"}


def test_public_search_empty_result_has_stable_shape(client):
    response = client.get("/api/public/search?q=不存在的资源&type=all")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["results"] == []
    assert payload["total"] == 0
    assert payload["page"] == 1
    assert payload["has_more"] is False


def test_public_search_paginates_beyond_legacy_two_hundred_row_cap(client, test_supplier):
    for index in range(205):
        db.session.add(
            Product(
                name=f"大批量传感器-{index:03d}",
                category="电子信息",
                enterprise_id=test_supplier.id,
            )
        )
    db.session.commit()

    response = client.get(
        "/api/public/search?q=大批量传感器&type=product&page=11&per_page=20"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 205
    assert payload["pages"] == 11
    assert len(payload["results"]) == 5
    assert payload["has_more"] is False


def test_public_search_supports_factory_filters_without_exposing_contact(
    client, test_supplier
):
    test_supplier.province = "广东省"
    test_supplier.city = "佛山市"
    test_supplier.business_status = "存续"
    test_supplier.is_green_factory = True
    test_supplier.registered_capital = 5000
    test_supplier.qualifications = [
        {"label_type": "little_giant", "label_name": "专精特新小巨人", "status": "active"}
    ]
    test_supplier.extras = {"is_export": True}
    db.session.commit()

    response = client.get(
        "/api/public/search?type=enterprise&province=广东省&city=佛山市"
        "&is_export=1&has_decision_maker=1&is_little_giant=1"
        "&is_green_factory=1&company_status=存续&min_registered_capital=1000"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    item = payload["results"][0]
    assert item["public_signals"]["verification_status"] in {"pending", "approved"}
    assert item["public_signals"]["is_export"] is True
    assert item["public_signals"]["has_decision_maker"] is True
    assert item["public_signals"]["is_little_giant"] is True
    assert item["public_signals"]["is_green_factory"] is True
    assert "phone" not in item
    assert "contact" not in item


def test_public_factory_detail_is_redacted_and_includes_products(client, test_supplier):
    db.session.add(
        Product(
            name="公开详情电机",
            description="伺服电机和驱动控制器",
            category="电气设备",
            enterprise_id=test_supplier.id,
        )
    )
    db.session.commit()

    response = client.get(f"/api/public/enterprises/{test_supplier.id}")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["enterprise"]["id"] == test_supplier.id
    assert payload["enterprise"]["name"] == test_supplier.name
    assert payload["products"][0]["title"] == "公开详情电机"
    assert "phone" not in payload["enterprise"]
    assert "contact" not in payload["enterprise"]


def test_public_agent_market_returns_realistic_capability_groups(client):
    response = client.get("/api/public/agent-market")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload["groups"]) == 7
    assert {group["title"] for group in payload["groups"]} >= {
        "AI 销售员",
        "AI 采购员",
        "AI 生产员",
        "AI 情报官",
    }
    assert payload["layers"]


def test_public_ai_find_rejects_empty_query_without_auth(client):
    response = client.post("/api/public/ai-find", json={"query": ""})

    assert response.status_code == 400
    assert response.get_json()["error"]


def test_public_ai_find_exposes_structured_intent_without_sensitive_data(client, monkeypatch):
    monkeypatch.setattr(
        "app.routes.api.extract_weights_from_nl",
        lambda _query: {"product": "精密注塑", "weights": {}},
    )
    monkeypatch.setattr("app.routes.api.match_suppliers", lambda **_kwargs: [])

    response = client.post(
        "/api/public/ai-find",
        json={"query": "找华东能做精密注塑、支持出口、1000 件、30 天交付、ISO 认证的工厂"},
    )

    assert response.status_code == 200
    intent = response.get_json()["parsed_intent"]
    assert intent["product"] == "精密注塑"
    assert intent["region"] == "华东"
    assert intent["quantity"] == 1000
    assert intent["delivery_days"] == 30
    assert intent["is_export"] is True
    assert "ISO" in intent["certifications"]
    assert "phone" not in response.get_json()

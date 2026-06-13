from app import db
from app.models import Enterprise
from app.routes.api import _public_region_from_address


SENSITIVE_KEYS = {
    "contact",
    "phone",
    "password_hash",
    "data_auth",
    "extras",
    "orders",
    "quotes",
    "settings",
}


def _assert_public_items_are_redacted(items):
    for item in items:
        assert not (SENSITIVE_KEYS & set(item.keys()))


def test_guest_can_query_enterprise_directory_with_redacted_summary(client, test_supplier):
    resp = client.get("/api/enterprises/directory?q=金属")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["total"] >= 1
    assert payload["enterprises"]
    _assert_public_items_are_redacted(payload["enterprises"])
    first = payload["enterprises"][0]
    assert first["name"] == test_supplier.name
    assert "金属制品制造" in first["business_scope"]


def test_public_region_redaction_keeps_only_province_city():
    assert _public_region_from_address("广东省东莞市塘厦镇家寮二巷7号") == "广东省 东莞市"
    assert _public_region_from_address("四川省成都市武侯区测试街道 88 号") == "四川省 成都市"


def test_guest_can_query_matching_search_with_redacted_summary(client):
    supplier = Enterprise(
        name="匿名匹配供应商",
        address="四川省成都市武侯区测试街道 88 号",
        province="四川省",
        city="成都市",
        contact="隐藏联系人",
        phone="13900000000",
        role="enterprise",
        credit_score=88.0,
        capacity=80,
        max_capacity=160,
        industry_code="C36",
        tech_keywords="金属加工",
        business_scope="金属制品制造",
    )
    supplier.set_password("test123456")
    db.session.add(supplier)
    db.session.commit()

    resp = client.get("/api/matching/search?query=金属")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert "suppliers" in payload
    _assert_public_items_are_redacted(payload["suppliers"])


def test_guest_still_cannot_access_private_business_apis(client):
    private_paths = [
        "/api/orders",
        "/api/user/settings",
        "/api/favorites",
    ]

    for path in private_paths:
        resp = client.get(path)
        assert resp.status_code in {401, 403}


def test_authenticated_enterprise_queries_still_work(client, test_enterprise, test_supplier):
    with client.session_transaction() as session:
        session["_user_id"] = str(test_enterprise.id)
        session["_fresh"] = True

    directory_resp = client.get("/api/enterprises/directory?q=金属")
    matching_resp = client.get("/api/matching/search?query=金属")

    assert directory_resp.status_code == 200
    assert matching_resp.status_code == 200
    assert directory_resp.get_json()["enterprises"]
    assert "suppliers" in matching_resp.get_json()

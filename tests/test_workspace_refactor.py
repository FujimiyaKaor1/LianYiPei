from datetime import datetime, timedelta

from app import db
from app.models import Alert, Enterprise, Inquiry, Quote


def _login(client, enterprise, password="test123456"):
    enterprise.verification_status = "approved"
    db.session.add(enterprise)
    db.session.commit()
    response = client.post(
        "/auth/login",
        data={"name": enterprise.name, "password": password},
        headers={"X-Login-Modal": "1"},
    )
    assert response.status_code == 200


def test_enterprise_dashboard_is_scoped_to_current_enterprise(client, test_enterprise, test_supplier):
    now = datetime.utcnow()
    own = Inquiry(
        poster_id=test_enterprise.id,
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="自有询盘",
        status="open",
        created_at=now,
    )
    other = Inquiry(
        poster_id=test_supplier.id,
        buyer_id=test_supplier.id,
        seller_id=test_enterprise.id,
        product_name="其他询盘",
        status="open",
        created_at=now - timedelta(days=45),
    )
    db.session.add_all([own, other])
    db.session.commit()
    _login(client, test_enterprise)

    response = client.get("/api/enterprise/dashboard/summary")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["is_demo"] is False
    assert payload["metrics"]["inquiries"] == 1
    assert all(todo["path"] for todo in payload["todos"])


def test_directory_supports_advanced_filters_and_stable_paging(client, test_enterprise, test_supplier):
    test_supplier.province = "四川省"
    test_supplier.city = "成都市"
    test_supplier.tech_keywords = "精密注塑,金属加工"
    test_supplier.is_green_factory = True
    test_supplier.last_data_update = datetime.utcnow()
    db.session.add(test_supplier)
    db.session.commit()
    _login(client, test_enterprise)

    response = client.get(
        "/api/enterprises/directory?city=成都市&tech_keyword=注塑&is_green_factory=1&page=1&per_page=1"
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["total"] == 1
    assert payload["pages"] == 1
    assert "contact" not in payload["enterprises"][0]
    assert "phone" not in payload["enterprises"][0]


def test_quote_selection_is_idempotent_and_notifies_supplier(client, test_enterprise, test_supplier):
    inquiry = Inquiry(
        poster_id=test_enterprise.id,
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="测试报价",
        status="sent",
    )
    db.session.add(inquiry)
    db.session.commit()
    quote = Quote(
        inquiry_id=inquiry.id,
        supplier_id=test_supplier.id,
        product_name="测试报价",
        price=100,
        status="active",
    )
    db.session.add(quote)
    db.session.commit()
    _login(client, test_enterprise)

    first = client.post(f"/api/quotes/{quote.id}/select", json={})
    second = client.post(f"/api/quotes/{quote.id}/select", json={})
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["idempotent"] is True
    assert inquiry.match_context["selected_quote_id"] == quote.id

    client.get("/auth/logout")
    _login(client, test_supplier)
    forbidden = client.post(f"/api/quotes/{quote.id}/select", json={})
    assert forbidden.status_code == 403


def test_alert_actions_are_persisted_and_enterprise_cannot_modify_government_alert(client, test_enterprise, test_admin):
    alert = Alert(
        product_name="测试产能",
        message="产能异常",
        level="yellow",
        alert_type="capacity_risk",
        is_active=True,
        workflow_history=[],
    )
    db.session.add(alert)
    db.session.commit()

    _login(client, test_enterprise)
    forbidden_acknowledge = client.post(f"/api/alerts/{alert.id}/acknowledge", json={})
    assert forbidden_acknowledge.status_code == 403
    db.session.refresh(alert)
    assert alert.is_active is True

    forbidden = client.post(f"/api/alerts/{alert.id}/close", json={})
    assert forbidden.status_code == 403
    db.session.refresh(alert)
    assert alert.is_active is True

    client.get("/auth/logout")
    _login(client, test_admin, password="admin123456")
    acknowledged = client.post(f"/api/alerts/{alert.id}/acknowledge", json={})
    assert acknowledged.status_code == 200
    db.session.refresh(alert)
    assert alert.workflow_history[-1]["action"] == "acknowledge"

    closed = client.post(f"/api/alerts/{alert.id}/close", json={"reason": "已完成处置"})
    assert closed.status_code == 200
    db.session.refresh(alert)
    assert alert.is_active is False
    assert alert.workflow_history[-1]["action"] == "close"
    assert alert.workflow_history[-1]["reason"] == "已完成处置"


def test_sales_summary_is_scoped_and_contains_real_funnel_counts(client, test_enterprise, test_supplier):
    inquiry = Inquiry(
        poster_id=test_supplier.id,
        buyer_id=test_supplier.id,
        seller_id=test_enterprise.id,
        product_name="销售指标测试",
        status="quoted",
    )
    db.session.add(inquiry)
    db.session.commit()
    db.session.add(Quote(
        inquiry_id=inquiry.id,
        supplier_id=test_enterprise.id,
        product_name="销售指标测试",
        price=88,
        status="active",
    ))
    db.session.commit()

    _login(client, test_enterprise)
    response = client.get("/api/enterprise/sales-summary?mode=sales")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["is_demo"] is False
    assert payload["metrics"]["new_inquiries"] == 1
    assert payload["metrics"]["quoted"] == 1
    assert payload["funnel"]["inquiries"] == 1
    assert payload["funnel"]["quotes"] == 1
    assert payload["source"] == "business_records"

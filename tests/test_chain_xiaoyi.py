"""链小易找厂 Agent：模型降级、会话权限、匹配和导出测试。"""
from io import BytesIO

from app import db
from app.models import Product
from app.models_chain_xiaoyi import ChainXiaoYiSession
from app.services.chain_xiaoyi.rules import merge_procurement_intent
from app.services.chain_xiaoyi.orchestrator import _best_database_product, parse_intent


def test_chain_xiaoyi_uses_truthful_rules_fallback(client):
    response = client.get("/api/chain-xiaoyi/model-status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["active_provider"] == "rules"
    assert payload["is_configured"] is False
    assert "尚未配置" in payload["message"]


def test_guest_session_uses_http_only_cookie_and_returns_database_matches(
    client, test_supplier, monkeypatch
):
    db.session.add(Product(name="精密注塑", category="注塑", enterprise_id=test_supplier.id))
    db.session.commit()
    monkeypatch.setattr(
        "app.services.chain_xiaoyi.orchestrator.explain_matches",
        lambda intent, rows: (
            {int(row["id"]): "基于数据库能力字段生成的推荐" for row in rows},
            "rules",
        ),
    )
    created = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"})
    assert created.status_code == 201
    session = created.get_json()["session"]
    assert "token" not in session
    assert "HttpOnly" in created.headers["Set-Cookie"]

    response = client.post(
        f"/api/chain-xiaoyi/sessions/{session['id']}/messages",
        json={"content": "找能做精密注塑、1000件、30天交付的工厂"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["intent"]["quantity"] == 1000
    assert payload["intent"]["delivery_days"] == 30
    assert payload["task"]["status"] == "succeeded"
    result = payload["match_result"]["results"][0]
    assert result["id"] == test_supplier.id
    assert "phone" not in result
    assert "address" not in result

    second = client.post(
        f"/api/chain-xiaoyi/sessions/{session['id']}/messages",
        json={"content": "只看四川的"},
    )
    assert second.status_code == 401
    assert second.get_json()["code"] == "login_required"


def test_chain_xiaoyi_file_preview_is_bounded_and_not_auto_imported(client):
    session = client.post(
        "/api/chain-xiaoyi/sessions", json={"surface": "public"}
    ).get_json()["session"]
    response = client.post(
        f"/api/chain-xiaoyi/sessions/{session['id']}/files",
        data={"file": (BytesIO(b"name,quantity\nsteel,10\n"), "需求.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()["file"]
    assert payload["status"] == "preview"
    assert payload["detected_kind"] == "table"
    assert payload["preview"]["rows"] == 1


def test_authenticated_chain_xiaoyi_can_create_demand_draft(client, test_enterprise):
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.commit()
    login = client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert login.status_code == 200, login.get_json()
    session = client.post(
        "/api/chain-xiaoyi/sessions", json={"surface": "enterprise"}
    ).get_json()["session"]
    response = client.post(
        f"/api/chain-xiaoyi/sessions/{session['id']}/demand-draft",
        json={"intent": {"product": "精密注塑", "quantity": 1000, "unit": "件", "raw_text": "找精密注塑"}},
    )
    assert response.status_code == 201
    assert response.get_json()["inquiry"]["status"] == "draft"


def test_authenticated_user_can_claim_list_archive_and_export_guest_session(
    client, test_enterprise, test_supplier
):
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.add(Product(name="工业电机", category="电机", enterprise_id=test_supplier.id))
    db.session.commit()
    guest = client.post(
        "/api/chain-xiaoyi/sessions", json={"surface": "public"}
    ).get_json()["session"]
    assert client.post(
        f"/api/chain-xiaoyi/sessions/{guest['id']}/messages",
        json={"content": "找工业电机供应商"},
    ).status_code == 200

    login = client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    )
    assert login.status_code == 200
    assert client.post(f"/api/chain-xiaoyi/sessions/{guest['id']}/claim").status_code == 200

    history = client.get("/api/chain-xiaoyi/sessions")
    assert history.status_code == 200
    assert [item["id"] for item in history.get_json()["sessions"]] == [guest["id"]]

    exported = client.get(f"/api/chain-xiaoyi/sessions/{guest['id']}/export.xlsx")
    assert exported.status_code == 200
    assert exported.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert b"13800138001" not in exported.data

    archived = client.post(f"/api/chain-xiaoyi/sessions/{guest['id']}/archive")
    assert archived.status_code == 200
    assert ChainXiaoYiSession.query.get(guest["id"]).status == "archived"


def test_guest_cannot_export(client):
    session = client.post(
        "/api/chain-xiaoyi/sessions", json={"surface": "public"}
    ).get_json()["session"]
    response = client.get(f"/api/chain-xiaoyi/sessions/{session['id']}/export.xlsx")
    assert response.status_code == 401


def test_guest_cannot_bypass_trial_by_creating_another_session(client, test_supplier):
    db.session.add(Product(name="工业电机", category="电机", enterprise_id=test_supplier.id))
    db.session.commit()
    first = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"}).get_json()["session"]
    assert client.post(f"/api/chain-xiaoyi/sessions/{first['id']}/messages", json={"content": "找工业电机"}).status_code == 200
    recreated = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"})
    assert recreated.status_code == 200
    assert recreated.get_json()["session"]["id"] == first["id"]
    denied = client.post(f"/api/chain-xiaoyi/sessions/{first['id']}/messages", json={"content": "再找一次"})
    assert denied.status_code == 401


def test_incremental_intent_merge_preserves_and_explicitly_clears_constraints():
    previous = {"product": "工业电机", "region": "四川", "quantity": 1000}
    merged = merge_procurement_intent(previous, {"delivery_days": 20}, "交期改成20天")
    assert merged["product"] == "工业电机"
    assert merged["region"] == "四川"
    assert merged["delivery_days"] == 20
    cleared = merge_procurement_intent(merged, {}, "取消地区限制")
    assert "region" not in cleared


def test_agent_falls_back_to_local_qwen_before_rules(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("CHAINXIAOYI_LOCAL_ENABLED", "true")
    monkeypatch.setenv("CHAINXIAOYI_LOCAL_MODEL", "qwen-local")
    monkeypatch.setattr(
        "app.services.chain_xiaoyi.orchestrator.invoke_ollama",
        lambda _system, _text: '{"product":"工业电机","region":"四川"}',
    )

    intent, provider = parse_intent("找四川工业电机")

    assert provider == "local"
    assert intent["product"] == "工业电机"
    assert intent["region"] == "四川"


def test_broad_motor_query_recalls_database_products(_db, test_supplier):
    db.session.add_all([
        Product(name="永磁同步驱动电机", category="电驱系统", enterprise_id=test_supplier.id),
        Product(name="低压伺服电机", category="机器人部件", enterprise_id=test_supplier.id),
    ])
    db.session.commit()

    intent = parse_intent("找工业电机供应商")[0]
    recall_term = _best_database_product(intent["raw_text"], intent["product"])

    assert recall_term == "电机"

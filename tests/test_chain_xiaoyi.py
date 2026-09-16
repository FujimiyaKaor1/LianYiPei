"""链小易主 Agent：规则降级、会话隔离和文件预览测试。"""
from io import BytesIO

from app import db


def test_chain_xiaoyi_uses_truthful_rules_fallback(client):
    response = client.get("/api/chain-xiaoyi/model-status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["active_provider"] == "rules"
    assert payload["is_configured"] is False
    assert "尚未配置" in payload["message"]


def test_guest_chain_xiaoyi_session_requires_token_and_extracts_intent(client):
    created = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"})
    assert created.status_code == 201
    session = created.get_json()["session"]
    session_id = session["id"]
    token = session["token"]

    denied = client.post(f"/api/chain-xiaoyi/sessions/{session_id}/messages", json={"content": "找广东能做精密注塑、1000件、30天交付的工厂"})
    assert denied.status_code == 404

    response = client.post(
        f"/api/chain-xiaoyi/sessions/{session_id}/messages",
        headers={"X-Chain-Xiaoyi-Token": token},
        json={"content": "找广东能做精密注塑、1000件、30天交付的工厂"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["intent"]["product"]
    assert payload["intent"]["quantity"] == 1000
    assert payload["intent"]["delivery_days"] == 30
    assert payload["task"]["status"] == "succeeded"


def test_chain_xiaoyi_file_preview_is_bounded_and_not_auto_imported(client):
    created = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"}).get_json()["session"]
    response = client.post(
        f"/api/chain-xiaoyi/sessions/{created['id']}/files",
        headers={"X-Chain-Xiaoyi-Token": created["token"]},
        data={"file": (BytesIO(b"name,quantity\nsteel,10\n"), "需求.csv")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()["file"]
    assert payload["status"] == "preview"
    assert payload["detected_kind"] == "table"
    assert payload["preview"]["rows"] == 1


def test_authenticated_chain_xiaoyi_can_create_demand_draft(client, test_enterprise):
    created = client.post("/api/chain-xiaoyi/sessions", json={"surface": "public"}).get_json()["session"]
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.commit()
    with client:
        login = client.post(
            "/auth/login",
            data={"name": test_enterprise.name, "password": "test123456"},
            headers={"X-Login-Modal": "1"},
        )
        assert login.status_code == 200, login.get_json()
        response = client.post(
            f"/api/chain-xiaoyi/sessions/{created['id']}/demand-draft",
            headers={"X-Chain-Xiaoyi-Token": created["token"]},
            json={"intent": {"product": "精密注塑", "quantity": 1000, "unit": "件", "raw_text": "找精密注塑"}},
        )
    assert response.status_code == 201
    assert response.get_json()["inquiry"]["status"] == "draft"

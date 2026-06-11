from datetime import datetime

from app import db
from app.models import Alert, HermesPendingAction


def _auth_headers(token: str = "test-hermes-token") -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "X-Forwarded-For": "127.0.0.1",
    }


def _create_alert(**overrides) -> Alert:
    payload = {
        "product_name": "汽车线束",
        "message": "本地供应商数量不足，存在断链风险",
        "level": "red",
        "dimension": "supplier_count",
        "alert_type": "supply_chain_break",
        "severity_score": 0.92,
        "suggestion": "建议立即派发给产业链专员核实替代供应商",
        "is_active": True,
        "analysis_data": {
            "risk_reason": "本地可用供应商少于 3 家",
            "impact_scope": "新能源汽车零部件供应",
            "ai_suggestions": ["核查外地替代供应商", "启动招商补链任务"],
        },
        "created_at": datetime.utcnow(),
    }
    payload.update(overrides)
    alert = Alert(**payload)
    db.session.add(alert)
    db.session.commit()
    return alert


def test_hermes_alert_routes_require_service_token(client, app):
    app.config["HERMES_LIANYIPEI_TOKEN"] = "test-hermes-token"

    response = client.get("/api/hermes/alerts")

    assert response.status_code == 401
    assert response.get_json()["error"] == "unauthorized"


def test_hermes_can_query_active_red_alerts(client, app, _db):
    app.config["HERMES_LIANYIPEI_TOKEN"] = "test-hermes-token"
    alert = _create_alert()
    _create_alert(product_name="普通提示", level="blue")

    response = client.get(
        "/api/hermes/alerts?level=red&status=active",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert body["alerts"][0]["id"] == alert.id
    assert body["alerts"][0]["risk_reason"] == "本地可用供应商少于 3 家"


def test_hermes_can_preview_and_confirm_assign_alert(
    client,
    app,
    _db,
    test_admin,
    test_government,
):
    app.config["HERMES_LIANYIPEI_TOKEN"] = "test-hermes-token"
    app.config["HERMES_ACTION_CONFIRM_TTL_SECONDS"] = 300
    alert = _create_alert()

    preview = client.post(
        "/api/hermes/actions/preview",
        json={
            "action": "assign_alert",
            "alert_id": alert.id,
            "requested_by": "weixin:test-user",
            "parameters": {
                "assigned_to": test_government.id,
                "assigned_by": test_admin.id,
            },
        },
        headers=_auth_headers(),
    )

    assert preview.status_code == 200
    preview_body = preview.get_json()
    assert preview_body["requires_confirmation"] is True
    assert preview_body["confirmation_phrase"] == "确认执行"
    assert "pending_action_id" in preview_body
    pending_action_id = preview_body["pending_action_id"]

    denied = client.post(
        "/api/hermes/actions/execute",
        json={
            "pending_action_id": pending_action_id,
            "confirmation": "执行吧",
        },
        headers=_auth_headers(),
    )
    assert denied.status_code == 400

    executed = client.post(
        "/api/hermes/actions/execute",
        json={
            "pending_action_id": pending_action_id,
            "confirmation": "确认执行",
        },
        headers=_auth_headers(),
    )

    assert executed.status_code == 200
    body = executed.get_json()
    assert body["success"] is True
    assert body["result"]["action"] == "assign_alert"

    db.session.refresh(alert)
    assert alert.workflow_history[0]["assigned_to"] == test_government.id
    assert alert.workflow_history[0]["status"] == "pending"

    pending = db.session.get(HermesPendingAction, pending_action_id)
    assert pending.status == "executed"
    assert pending.executed_at is not None


def test_hermes_rejects_expired_pending_action(client, app, _db, test_admin):
    app.config["HERMES_LIANYIPEI_TOKEN"] = "test-hermes-token"
    app.config["HERMES_ACTION_CONFIRM_TTL_SECONDS"] = -1
    alert = _create_alert()

    preview = client.post(
        "/api/hermes/actions/preview",
        json={
            "action": "close_alert",
            "alert_id": alert.id,
            "requested_by": "weixin:test-user",
            "parameters": {
                "operator_id": test_admin.id,
                "reason": "测试过期确认",
            },
        },
        headers=_auth_headers(),
    )
    assert preview.status_code == 200
    pending_action_id = preview.get_json()["pending_action_id"]

    executed = client.post(
        "/api/hermes/actions/execute",
        json={
            "pending_action_id": pending_action_id,
            "confirmation": "确认执行",
        },
        headers=_auth_headers(),
    )

    assert executed.status_code == 400
    assert executed.get_json()["error"] == "pending_action_expired"
    assert db.session.get(HermesPendingAction, pending_action_id).status == "expired"


def test_red_alert_falls_back_to_existing_wechat_when_hermes_unavailable(
    monkeypatch,
    app,
    _db,
    test_admin,
):
    from app.applications.risk.services import alert_notifier

    alert = _create_alert()
    calls = []

    monkeypatch.setattr(
        alert_notifier,
        "_send_hermes_alert",
        lambda alert_obj, recipient_ids: {"success": False, "message": "disabled"},
    )
    monkeypatch.setattr(
        alert_notifier,
        "_send_wechat_push",
        lambda alert_obj, recipient_ids: calls.append(("wechat", recipient_ids)),
    )
    monkeypatch.setattr(alert_notifier, "_send_sms", lambda alert_obj, recipient_ids: None)
    monkeypatch.setattr(
        alert_notifier,
        "_send_in_site_message",
        lambda alert_obj, recipient_ids: None,
    )

    alert_notifier.notify_alert(alert, [test_admin.id])

    assert calls == [("wechat", [test_admin.id])]

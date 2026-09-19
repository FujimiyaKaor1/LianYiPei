"""Signed, idempotent callbacks for the post-RFQ order lifecycle."""

from __future__ import annotations

from datetime import date
import hashlib
import hmac
import json

from app import db
from app.services.order_service import OrderService
from app.models_chain_xiaoyi import ChainXiaoYiEvent, ChainXiaoYiSession, ChainXiaoYiTask


SECRET = "fulfillment-callback-test-secret"


def _post(client, payload: dict, secret: str = SECRET, provider: str = "erp"):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return client.post(
        f"/api/chain-xiaoyi/fulfillment-event-callback/{provider}",
        data=raw,
        content_type="application/json",
        headers={"X-Lianyipei-Signature": f"sha256={signature}"},
    )


def _order(test_enterprise):
    return OrderService.create_order(
        enterprise_id=test_enterprise.id,
        product_name="连接器",
        quantity=100,
        unit="件",
        customer_name="广东供应商",
        order_date=date(2026, 6, 12),
        metadata={
            "requires_contract_confirmation": True,
            "requires_payment_confirmation": True,
        },
    )


def test_fulfillment_callback_requires_secret_and_valid_provider(client, app):
    payload = {"event_id": "missing-secret", "enterprise_id": 1, "order_id": 1, "event_type": "payment_succeeded"}
    missing = client.post("/api/chain-xiaoyi/fulfillment-event-callback/erp", json=payload)
    assert missing.status_code == 503
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    unsupported = _post(client, payload, provider="unknown")
    assert unsupported.status_code == 404


def test_fulfillment_callback_records_events_without_bypassing_confirmations(
    client, app, test_enterprise
):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    order = _order(test_enterprise)
    payment = _post(
        client,
        {
            "event_id": "erp-payment-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "payment_succeeded",
            "reference": "pay-ref-1",
        },
    )
    assert payment.status_code == 200
    assert payment.get_json()["status"] == "payment_recorded"
    current = OrderService.get_order_by_id(order.id, enterprise_id=test_enterprise.id)
    assert current.status == "pending"
    assert current.metadata["external_event_latest"]["payment_succeeded"]["reference"] == "pay-ref-1"
    assert "payment_confirmed_at" not in current.metadata

    corrected = _post(
        client,
        {
            "event_id": "erp-payment-2",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "payment_succeeded",
            "reference": "pay-ref-2",
        },
    )
    assert corrected.status_code == 200
    current = OrderService.get_order_by_id(order.id, enterprise_id=test_enterprise.id)
    assert len(current.metadata["external_events"]) == 2
    assert current.metadata["external_event_latest"]["payment_succeeded"]["reference"] == "pay-ref-2"

    repeated = _post(
        client,
        {
            "event_id": "erp-payment-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "payment_succeeded",
            "reference": "pay-ref-1",
        },
    )
    assert repeated.status_code == 200
    assert repeated.get_json()["idempotent"] is True

    wrong_owner = _post(
        client,
        {
            "event_id": "erp-payment-wrong-owner",
            "enterprise_id": test_enterprise.id + 999,
            "order_id": order.id,
            "event_type": "payment_succeeded",
        },
    )
    # Owner scoping intentionally returns 404 to avoid leaking another
    # enterprise's order namespace.
    assert wrong_owner.status_code == 404


def test_fulfillment_callback_advances_status_only_after_independent_confirmations(
    client, app, test_enterprise
):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.commit()
    order = _order(test_enterprise)
    assert client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    ).status_code == 200
    for requirement in ("contract", "payment"):
        confirmed = client.post(
            f"/orders/{order.id}/confirm-{requirement}",
            json={"confirm": True},
        )
        assert confirmed.status_code == 200

    shipped = _post(
        client,
        {
            "event_id": "erp-shipped-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "shipment_dispatched",
            "tracking_no": "SF123456",
        },
    )
    assert shipped.status_code == 200
    assert shipped.get_json()["status"] == "in_progress"
    assert OrderService.get_order_by_id(order.id, enterprise_id=test_enterprise.id).status == "in_progress"

    delivered = _post(
        client,
        {
            "event_id": "erp-delivered-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "delivery_confirmed",
        },
    )
    assert delivered.status_code == 200
    assert delivered.get_json()["status"] == "completed"
    assert OrderService.get_order_by_id(order.id, enterprise_id=test_enterprise.id).status == "completed"


def test_fulfillment_callback_scopes_event_types_to_provider(client, app, test_enterprise):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    order = _order(test_enterprise)
    response = _post(
        client,
        {
            "event_id": "payment-cannot-ship",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "shipment_dispatched",
        },
        provider="payment",
    )
    assert response.status_code == 403


def test_fulfillment_provider_allowlists_include_failure_events(client, app, test_enterprise):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    order = _order(test_enterprise)
    response = _post(
        client,
        {
            "event_id": "payment-failed-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "payment_failed",
            "reason": "支付渠道拒绝",
        },
        provider="payment",
    )
    assert response.status_code == 200
    current = OrderService.get_order_by_id(order.id, enterprise_id=test_enterprise.id)
    assert current.metadata["external_payment_status"] == "failed"


def _agent_order(test_enterprise, *, task_status="completed"):
    session = ChainXiaoYiSession(
        owner_id=test_enterprise.id,
        access_token=ChainXiaoYiSession.issue_token(),
        title="履约回写测试",
        surface="private",
    )
    db.session.add(session)
    db.session.flush()
    task = ChainXiaoYiTask(
        session_id=session.id,
        task_type="rfq",
        status=task_status,
        input_json={"intent": {"product": "连接器"}},
        output_json={},
    )
    db.session.add(task)
    db.session.flush()
    order = OrderService.create_order(
        enterprise_id=test_enterprise.id,
        product_name="连接器",
        quantity=100,
        unit="件",
        customer_name="测试供应商",
        order_date=date(2026, 6, 12),
        metadata={
            "chain_xiaoyi_task_id": task.id,
            "supplier_id": 999,
            "requires_contract_confirmation": False,
            "requires_payment_confirmation": False,
        },
        commit=False,
    )
    db.session.commit()
    return session, task, order


def test_fulfillment_callback_writes_agent_audit_and_progresses_task(client, app, test_enterprise):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    session, task, order = _agent_order(test_enterprise)

    shipped = _post(
        client,
        {
            "event_id": "erp-agent-shipped-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "shipment_dispatched",
            "tracking_no": "SF-AGENT-1",
        },
    )
    assert shipped.status_code == 200
    current_task = db.session.get(ChainXiaoYiTask, task.id)
    assert current_task.status == "fulfillment_in_progress"
    assert current_task.output_json["fulfillment"]["latest_event"] == "shipment_dispatched"
    events = ChainXiaoYiEvent.query.filter_by(session_id=session.id).all()
    assert len(events) == 1
    assert events[0].event_type == "fulfillment_event_received"
    assert events[0].payload["task_id"] == task.id

    delivered = _post(
        client,
        {
            "event_id": "erp-agent-delivered-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "delivery_confirmed",
        },
    )
    assert delivered.status_code == 200
    assert db.session.get(ChainXiaoYiTask, task.id).status == "fulfillment_completed"
    assert ChainXiaoYiEvent.query.filter_by(session_id=session.id).count() == 2


def test_fulfillment_exception_creates_recoverable_agent_task(client, app, test_enterprise):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    session, task, order = _agent_order(test_enterprise)
    response = _post(
        client,
        {
            "event_id": "erp-agent-delay-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "shipment_delayed",
            "reason": "产线排期延迟",
            "delay_days": 3,
        },
    )
    assert response.status_code == 200
    current_task = db.session.get(ChainXiaoYiTask, task.id)
    assert current_task.status == "fulfillment_exception"
    assert current_task.output_json["fulfillment"]["exception"]["reason"] == "产线排期延迟"
    events = ChainXiaoYiEvent.query.filter_by(session_id=session.id).all()
    assert events[0].payload["recoverable"] is True
    assert events[0].payload["event_type"] == "shipment_delayed"


def test_fulfillment_callback_mirrors_batch_parent_task(client, app, test_enterprise):
    app.config["FULFILLMENT_CALLBACK_SECRET"] = SECRET
    session, child, order = _agent_order(test_enterprise)
    parent = ChainXiaoYiTask(
        session_id=session.id,
        task_type="procurement_intake",
        status="running",
        input_json={"intent": {"product": "连接器"}},
        output_json={"batch_rfq": {"task_ids": [child.id]}},
    )
    db.session.add(parent)
    db.session.flush()
    child.input_json = {**(child.input_json or {}), "source_procurement_task_id": parent.id}
    db.session.commit()

    response = _post(
        client,
        {
            "event_id": "erp-parent-delivered-1",
            "enterprise_id": test_enterprise.id,
            "order_id": order.id,
            "event_type": "delivery_confirmed",
        },
    )
    assert response.status_code == 200
    assert db.session.get(ChainXiaoYiTask, child.id).status == "fulfillment_completed"
    assert db.session.get(ChainXiaoYiTask, parent.id).status == "fulfillment_completed"
    parent_events = [
        row for row in ChainXiaoYiEvent.query.filter_by(session_id=session.id).all()
        if (row.payload or {}).get("task_id") == parent.id
    ]
    assert len(parent_events) == 1
    assert parent_events[0].payload["child_task_id"] == child.id

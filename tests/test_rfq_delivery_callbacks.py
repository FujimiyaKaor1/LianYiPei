"""RFQ provider delivery callback tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timedelta

from app import db
from app.models_chain_xiaoyi import (
    ChainXiaoYiOutboundRecord,
    ChainXiaoYiSession,
    ChainXiaoYiTask,
)
from app.models import ExternalCallbackReceipt
from app.services.chain_xiaoyi.orchestrator import ChainXiaoYiOrchestrator


SECRET = "delivery-callback-test-secret"


def _signature(payload: bytes) -> str:
    return hmac.new(SECRET.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def _create_outbound(test_enterprise, test_supplier):
    session = ChainXiaoYiSession(
        owner_id=test_enterprise.id,
        access_token=ChainXiaoYiSession.issue_token(),
        title="外部渠道回调测试",
    )
    db.session.add(session)
    db.session.flush()
    task = ChainXiaoYiTask(
        session_id=session.id,
        task_type="rfq",
        status="sent",
        requires_approval=True,
    )
    db.session.add(task)
    db.session.flush()
    outbound = ChainXiaoYiOutboundRecord(
        task_id=task.id,
        supplier_id=test_supplier.id,
        status="sent",
        channel="email",
        channel_status_json={
            "channels": {
                "email": {"status": "sent", "message_id": "provider-message-1"}
            }
        },
    )
    db.session.add(outbound)
    db.session.commit()
    return task, outbound


def _post_callback(client, payload: dict, *, signature: str | None = None):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return client.post(
        "/api/chain-xiaoyi/delivery-callback/email",
        data=raw,
        content_type="application/json",
        headers={"X-Lianyipei-Signature": signature or _signature(raw)},
    )


def test_delivery_callback_rejects_missing_or_invalid_signature(client, app, monkeypatch):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    payload = {"event_id": "event-invalid", "outbound_id": 1, "status": "delivered"}

    missing = client.post(
        "/api/chain-xiaoyi/delivery-callback/email",
        json=payload,
    )
    assert missing.status_code == 403

    invalid = _post_callback(client, payload, signature="bad-signature")
    assert invalid.status_code == 403


def test_delivery_callback_updates_outbound_and_is_idempotent(
    client, app, monkeypatch, test_enterprise, test_supplier
):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    _, outbound = _create_outbound(test_enterprise, test_supplier)
    payload = {
        "event_id": "email-event-1",
        "provider_message_id": "provider-message-1",
        "status": "delivered",
    }

    response = _post_callback(client, payload)
    assert response.status_code == 200
    assert response.get_json()["status"] == "delivered"
    db.session.refresh(outbound)
    assert outbound.status == "delivered"
    assert outbound.delivered_at is not None
    assert outbound.channel_status_json["channels"]["email"]["status"] == "delivered"
    assert ExternalCallbackReceipt.query.count() == 1

    reordered = {
        "status": "delivered",
        "event_id": "email-event-1",
        "provider_message_id": "provider-message-1",
    }
    reordered_response = _post_callback(client, reordered)
    assert reordered_response.status_code == 200
    assert reordered_response.get_json()["idempotent"] is True
    assert ExternalCallbackReceipt.query.count() == 1

    repeated = _post_callback(client, payload)
    assert repeated.status_code == 200
    assert repeated.get_json()["idempotent"] is True
    assert ExternalCallbackReceipt.query.count() == 1


def test_delivery_callback_cannot_regress_read_or_replied_status(
    client, app, monkeypatch, test_enterprise, test_supplier
):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    _, outbound = _create_outbound(test_enterprise, test_supplier)
    outbound.status = "read"
    outbound.read_at = db.func.now()
    db.session.commit()

    payload = {
        "event_id": "email-event-stale",
        "provider_message_id": "provider-message-1",
        "status": "delivered",
    }
    response = _post_callback(client, payload)
    assert response.status_code == 200
    assert response.get_json()["status"] == "read"
    db.session.refresh(outbound)
    assert outbound.status == "read"
    assert outbound.read_at is not None

    failed_payload = {
        "event_id": "email-event-late-failed",
        "outbound_id": outbound.id,
        "status": "failed",
        "error": "late provider retry",
    }
    failed_response = _post_callback(client, failed_payload)
    assert failed_response.status_code == 200
    assert failed_response.get_json()["status"] == "read"
    db.session.refresh(outbound)
    assert outbound.status == "read"
    assert outbound.error_message is None


def test_delivery_callback_marks_failure_and_requires_provider_secret(
    client, app, monkeypatch, test_enterprise, test_supplier
):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    _, outbound = _create_outbound(test_enterprise, test_supplier)
    payload = {
        "event_id": "email-event-failed",
        "outbound_id": outbound.id,
        "status": "failed",
        "error": "mailbox rejected",
    }
    response = _post_callback(client, payload)
    assert response.status_code == 200
    db.session.refresh(outbound)
    assert outbound.status == "failed"
    assert outbound.error_message == "mailbox rejected"

    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", "")
    unavailable = client.post(
        "/api/chain-xiaoyi/delivery-callback/email",
        data=json.dumps({"event_id": "without-secret"}).encode("utf-8"),
        content_type="application/json",
    )
    assert unavailable.status_code == 503


def test_provider_message_lookup_is_limited_to_callback_channel(
    client, app, monkeypatch, test_enterprise, test_supplier
):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    _, outbound = _create_outbound(test_enterprise, test_supplier)
    outbound.channel_status_json = {"channels": {"wechat": {"status": "sent", "message_id": "same-id"}}}
    db.session.commit()
    payload = {"event_id": "email-wrong-channel", "provider_message_id": "same-id", "status": "delivered"}
    response = _post_callback(client, payload)
    assert response.status_code == 404
    db.session.refresh(outbound)
    assert outbound.status == "sent"


def test_late_delivery_callback_cannot_reopen_timed_out_rfq(
    client, app, monkeypatch, test_enterprise, test_supplier
):
    monkeypatch.setitem(app.config, "RFQ_DELIVERY_CALLBACK_SECRET", SECRET)
    task, outbound = _create_outbound(test_enterprise, test_supplier)
    task.quote_deadline_at = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    assert ChainXiaoYiOrchestrator.expire_rfq_tasks(now=datetime.utcnow())["expired_records"] == 1

    response = _post_callback(
        client,
        {
            "event_id": "late-delivery-after-timeout",
            "outbound_id": outbound.id,
            "status": "delivered",
        },
    )
    assert response.status_code == 200
    assert response.get_json()["status"] == "timed_out"
    db.session.refresh(outbound)
    assert outbound.status == "timed_out"

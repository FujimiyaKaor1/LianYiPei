"""Signed inbound email adapter for the Chain XiaoYi quote loop."""

from __future__ import annotations

import hashlib
import hmac
import json

from app import db
from app.applications.fulfillment.services.intent_quote_service import IntentQuoteService
from app.models import IntentQuote


SECRET = "email-inbound-test-secret"


def _post(client, payload: dict, secret: str = SECRET):
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return client.post(
        "/api/chain-xiaoyi/email-quote-inbound",
        data=raw,
        content_type="application/json",
        headers={"X-Lianyipei-Signature": f"sha256={signature}"},
    )


def _prepare_quote(test_enterprise, test_supplier):
    test_supplier.extras = {
        "email": "sales@supplier.example",
        "communication_authorizations": {"email": True},
        "trust_profile": {"claim_status": "claimed", "contact_authorized": True},
    }
    db.session.commit()
    quote, error = IntentQuoteService().create_intent_quote(
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="精密连接器",
        quantity=1000,
        unit="件",
    )
    assert not error
    quote, error = IntentQuoteService().send_intent_quote(quote.id, test_enterprise.id)
    assert not error
    return quote


def test_email_quote_inbound_requires_configuration_and_signature(client, app):
    payload = {"event_id": "missing-secret", "from_email": "sales@example.com", "text": "报价 #1 单价12元"}
    response = client.post(
        "/api/chain-xiaoyi/email-quote-inbound",
        json=payload,
    )
    assert response.status_code == 503

    app.config["RFQ_EMAIL_INBOUND_SECRET"] = SECRET
    invalid = client.post(
        "/api/chain-xiaoyi/email-quote-inbound",
        data=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
        headers={"X-Lianyipei-Signature": "bad"},
    )
    assert invalid.status_code == 403


def test_email_quote_inbound_previews_then_confirms_idempotently(
    client, app, test_enterprise, test_supplier
):
    app.config["RFQ_EMAIL_INBOUND_SECRET"] = SECRET
    quote = _prepare_quote(test_enterprise, test_supplier)
    preview = _post(
        client,
        {
            "event_id": "email-preview-1",
            "from_email": "sales@supplier.example",
            "subject": f"Re: 询价 #{quote.id}",
            "text": f"报价 #{quote.id} 单价12.8元 含税13% 交期25天 有效期30天",
        },
    )
    assert preview.status_code == 200
    assert preview.get_json()["confirmed"] is False
    assert preview.get_json()["needs_confirmation"] is True
    assert db.session.get(IntentQuote, quote.id).status == "pending"

    confirmed_payload = {
        "event_id": "email-confirmed-1",
        "from_email": "sales@supplier.example",
        "subject": f"Re: 询价 #{quote.id}",
        "text": f"确认报价 #{quote.id} 单价12.8元 含税13% 交期25天 有效期30天",
    }
    confirmed = _post(client, confirmed_payload)
    assert confirmed.status_code == 200
    assert confirmed.get_json()["status"] == "accepted"
    assert db.session.get(IntentQuote, quote.id).seller_reply_price == 12.8

    repeated = _post(client, confirmed_payload)
    assert repeated.status_code == 200
    assert repeated.get_json()["idempotent"] is True


def test_email_quote_inbound_rejects_unapproved_sender(client, app, test_enterprise, test_supplier):
    app.config["RFQ_EMAIL_INBOUND_SECRET"] = SECRET
    quote = _prepare_quote(test_enterprise, test_supplier)
    payload = {
        "event_id": "email-unauthorized-1",
        "from_email": "attacker@example.com",
        "text": f"确认报价 #{quote.id} 单价1元",
    }
    response = _post(client, payload)
    assert response.status_code == 403
    assert db.session.get(IntentQuote, quote.id).status == "pending"


def test_email_quote_inbound_rejects_quote_id_mismatch(client, app, test_enterprise, test_supplier):
    app.config["RFQ_EMAIL_INBOUND_SECRET"] = SECRET
    quote = _prepare_quote(test_enterprise, test_supplier)
    response = _post(
        client,
        {
            "event_id": "email-mismatch-1",
            "from_email": "sales@supplier.example",
            "text": f"确认报价 #{quote.id + 99} 单价12元",
            "quote_id": quote.id,
        },
    )
    assert response.status_code == 400
    assert db.session.get(IntentQuote, quote.id).status == "pending"

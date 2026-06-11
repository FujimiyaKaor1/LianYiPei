from app import db
from app.models import ChatMessage, InquiryChat, MatchRecord


def _login_as(client, enterprise):
    with client.session_transaction() as session:
        session["_user_id"] = str(enterprise.id)
        session["_fresh"] = True


def test_resending_existing_pending_intent_quote_is_idempotent(
    client,
    test_enterprise,
    test_supplier,
):
    _login_as(client, test_enterprise)

    match = MatchRecord(
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
        product_name="高压线束总成",
        match_score=0.86,
        status="matched",
    )
    db.session.add(match)
    db.session.flush()

    chat = InquiryChat(
        match_record_id=match.id,
        buyer_id=test_enterprise.id,
        seller_id=test_supplier.id,
    )
    db.session.add(chat)
    db.session.commit()

    payload = {
        "seller_id": test_supplier.id,
        "product_name": "高压线束总成",
        "chat_id": chat.id,
        "match_record_id": match.id,
        "quantity": 1200,
        "unit": "套",
        "target_price": 268.5,
        "budget_range": "250-285",
    }

    first_create = client.post("/api/intent-quote/create", json=payload)
    assert first_create.status_code == 200

    quote_id = first_create.get_json()["quote_id"]
    first_send = client.post(f"/api/intent-quote/{quote_id}/send")
    assert first_send.status_code == 200
    assert first_send.get_json()["status"] == "pending"

    second_create = client.post("/api/intent-quote/create", json=payload)
    assert second_create.status_code == 200
    assert second_create.get_json()["quote_id"] == quote_id
    assert second_create.get_json()["status"] == "pending"

    second_send = client.post(f"/api/intent-quote/{quote_id}/send")
    assert second_send.status_code == 200
    assert second_send.get_json()["status"] == "pending"

    sent_messages = ChatMessage.query.filter_by(
        chat_id=chat.id,
        message_type="system",
    ).all()
    assert len(sent_messages) == 1
    assert sent_messages[0].msg_metadata["event"] == "intent_quote_sent"

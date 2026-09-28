from app import db
from app.models import InquiryChat, MatchRecord
from app.services.inquiry_chat_service import InquiryChatService


def _login_as(client, enterprise):
    with client.session_transaction() as session:
        session["_user_id"] = str(enterprise.id)
        session["_fresh"] = True


def test_business_insight_risk_marks_65_credit_score_as_low_risk():
    assert InquiryChatService._score_to_risk(65) == (
        "低风险",
        "信用表现良好，违约风险较低",
    )


def test_business_insight_risk_keeps_scores_below_60_high_risk():
    risk_level, _ = InquiryChatService._score_to_risk(59.9)
    assert risk_level == "高风险"


def test_matching_page_can_create_exchange_chat_without_placeholder_match_id(
    client, test_enterprise, test_supplier
):
    _login_as(client, test_enterprise)

    response = client.post(
        "/api/inquiry-chat/create",
        json={
            "buyer_id": test_enterprise.id,
            "seller_id": test_supplier.id,
            "product_name": "精密零部件",
            "match_score": 88,
        },
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["success"] is True
    chat = db.session.get(InquiryChat, payload["chat_id"])
    assert chat is not None
    assert chat.match_record_id is not None
    match = db.session.get(MatchRecord, chat.match_record_id)
    assert match is not None
    assert match.buyer_id == test_enterprise.id
    assert match.seller_id == test_supplier.id

    chat.status = "quoted"
    match.status = "quote_acknowledged"
    db.session.commit()
    exchanged = client.post(f"/api/inquiry-chat/{chat.id}/exchange-card")
    assert exchanged.status_code == 200, exchanged.get_json()
    assert exchanged.get_json()["card"]["name"] == test_supplier.name
    assert db.session.get(InquiryChat, chat.id).status == "contracted"
    assert match.product_name == "精密零部件"

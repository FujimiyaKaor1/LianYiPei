from app import db
from app.models import InquiryChat, MatchRecord


def _login_as(client, enterprise):
    with client.session_transaction() as session:
        session["_user_id"] = str(enterprise.id)
        session["_fresh"] = True


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
    assert match.product_name == "精密零部件"

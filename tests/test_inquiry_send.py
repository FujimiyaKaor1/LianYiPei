from app import db
from app.models import Inquiry, MatchFeedback, Message


def _login_as(client, enterprise):
    with client.session_transaction() as session:
        session["_user_id"] = str(enterprise.id)
        session["_fresh"] = True


def test_matching_page_can_send_inquiry(client, test_enterprise, test_supplier):
    _login_as(client, test_enterprise)

    response = client.post(
        "/api/inquiry/send",
        json={
            "supplier_id": test_supplier.id,
            "product_name": "精密零部件",
            "content": "请提供报价和交期。",
            "dim_scores": {},
            "match_score": 49,
        },
    )

    assert response.status_code == 200, response.get_json()
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["inquiry_id"] == db.session.query(Inquiry).one().id
    assert payload["match_feedback_id"] == db.session.query(MatchFeedback).one().id
    assert db.session.query(Message).filter_by(recipient_id=test_supplier.id).count() == 1


def test_matching_page_can_open_chat_after_sending_inquiry(
    client, test_enterprise, test_supplier
):
    _login_as(client, test_enterprise)

    inquiry_response = client.post(
        "/api/inquiry/send",
        json={
            "supplier_id": test_supplier.id,
            "product_name": "精密零部件",
            "content": "请提供报价和交期。",
            "dim_scores": {},
            "match_score": 49,
        },
    )
    inquiry = inquiry_response.get_json()

    chat_response = client.post(
        "/api/inquiry-chat/create",
        json={
            "buyer_id": test_enterprise.id,
            "seller_id": test_supplier.id,
            "match_feedback_id": inquiry["match_feedback_id"],
            "is_anonymous": False,
            "product_name": "精密零部件",
            "match_score": 49,
            "dim_scores": {},
        },
    )

    assert chat_response.status_code == 200, chat_response.get_json()
    assert chat_response.get_json()["success"] is True

import pytest

from app import db
from app.services.finance_service import calculate_loan_eligibility, apply_order_financing


def _login_as(client, enterprise):
    with client.session_transaction() as session:
        session["_user_id"] = str(enterprise.id)
        session["_fresh"] = True


def test_finance_estimate_does_not_invent_match_score_or_bank(_db, test_enterprise):
    estimate = calculate_loan_eligibility(test_enterprise.id)

    assert estimate["eligible"] is False
    assert estimate["match_score"] is None
    assert estimate["loan_amount_yuan"] is None
    assert estimate["bank_name"] is None
    assert "没有已持久化的匹配反馈" in estimate["reason"]


def test_finance_application_fails_closed_without_provider(_db, test_enterprise):
    before = test_enterprise.credit_score

    with pytest.raises(RuntimeError, match="金融机构接口未接入"):
        apply_order_financing(test_enterprise.id, "某银行", 10000)

    db.session.refresh(test_enterprise)
    assert test_enterprise.credit_score == before
    assert not (test_enterprise.extras or {}).get("financing_applications")


def test_finance_api_returns_provider_unavailable(client, test_enterprise):
    _login_as(client, test_enterprise)

    response = client.post("/api/finance/apply-order-financing", json={"loan_amount_yuan": 10000})

    assert response.status_code == 503
    assert response.get_json()["code"] == "finance_provider_unavailable"

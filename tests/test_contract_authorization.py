"""电子合同路由的企业级授权边界测试。"""

from unittest.mock import MagicMock, patch

import pytest

from app import db
from app.models import Enterprise, Transaction
from app.services.econtract_service import EContractService


def _login(client, enterprise: Enterprise) -> None:
    response = client.post(
        "/auth/login",
        data={"name": enterprise.name, "password": "test123456"},
    )
    assert response.status_code in {200, 302}


def _enterprise(name: str) -> Enterprise:
    enterprise = Enterprise(
        name=name,
        role="enterprise",
        is_verified=True,
        verification_status="approved",
    )
    enterprise.set_password("test123456")
    db.session.add(enterprise)
    db.session.commit()
    return enterprise


def _contract_transaction(buyer: Enterprise, seller: Enterprise, contract_id: str) -> Transaction:
    transaction = Transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        product_name="高压线束",
        status="pending",
        invoice_info={"contract_id": contract_id},
        fulfillment_status="contract_pending",
    )
    db.session.add(transaction)
    db.session.commit()
    return transaction


def test_non_participant_cannot_read_or_sign_contract(client):
    buyer = _enterprise("合同买方")
    seller = _enterprise("合同卖方")
    attacker = _enterprise("无关企业")
    _contract_transaction(buyer, seller, "CT-AUTH-1")
    _login(client, attacker)

    service = MagicMock()
    with patch("app.routes.contract.get_econtract_service", return_value=service):
        status_response = client.get("/contract/api/status/CT-AUTH-1")
        sign_response = client.post(
            "/contract/api/sign",
            json={"contract_id": "CT-AUTH-1", "signature_data": {}},
        )

    assert status_response.status_code == 403
    assert sign_response.status_code == 403
    service.check_contract_status.assert_not_called()
    service.sign_contract.assert_not_called()


def test_seller_cannot_self_confirm_fulfillment(client):
    buyer = _enterprise("履约买方")
    seller = _enterprise("履约卖方")
    tx = _contract_transaction(buyer, seller, "CT-AUTH-2")
    tx.match_code = "LYP-AUTH-2"
    db.session.commit()
    _login(client, seller)

    with patch("app.routes.contract.trigger_fulfillment_backflow") as backflow:
        response = client.post(
            "/contract/api/fulfill",
            json={
                "contract_id": "CT-AUTH-2",
                "invoice_info": {"invoice_no": "INV-1", "invoice_amount": 1000},
            },
        )

    assert response.status_code == 403
    backflow.assert_not_called()


def test_buyer_can_confirm_own_contract_fulfillment(client):
    buyer = _enterprise("确认买方")
    seller = _enterprise("确认卖方")
    tx = _contract_transaction(buyer, seller, "CT-AUTH-3")
    tx.match_code = "LYP-AUTH-3"
    db.session.commit()
    _login(client, buyer)

    with patch(
        "app.routes.contract.trigger_fulfillment_backflow",
        return_value={"success": True, "status": "fulfilled"},
    ) as backflow:
        response = client.post(
            "/contract/api/fulfill",
            json={
                "contract_id": "CT-AUTH-3",
                "invoice_info": {
                    "invoice_no": "INV-3",
                    "invoice_date": "2026-09-17",
                    "invoice_amount": 1000,
                },
            },
        )

    assert response.status_code == 200
    backflow.assert_called_once()


def test_unverified_invoice_cannot_trigger_fulfillment(client):
    buyer = _enterprise("验票买方")
    seller = _enterprise("验票卖方")
    tx = _contract_transaction(buyer, seller, "CT-AUTH-4")
    tx.match_code = "LYP-AUTH-4"
    db.session.commit()
    _login(client, buyer)

    with patch("app.routes.contract.trigger_fulfillment_backflow") as backflow:
        response = client.post(
            "/contract/api/fulfill",
            json={
                "contract_id": "CT-AUTH-4",
                "invoice_info": {
                    "invoice_no": "INVALID-4",
                    "invoice_date": "2026-09-17",
                    "invoice_amount": 1000,
                },
            },
        )

    assert response.status_code == 422
    assert response.get_json()["data"]["manual_review_required"] is False
    backflow.assert_not_called()


def test_contract_creation_requires_current_enterprise_as_buyer(client):
    buyer = _enterprise("被冒用买方")
    seller = _enterprise("创建卖方")
    attacker = _enterprise("创建攻击者")
    _login(client, attacker)

    service = MagicMock()
    with patch("app.routes.contract.get_econtract_service", return_value=service):
        response = client.post(
            "/contract/create",
            data={
                "buyer_id": buyer.id,
                "seller_id": seller.id,
                "product_name": "连接器",
                "quantity": 100,
                "unit": "件",
                "price": 10,
                "total_amount": 1000,
            },
        )

    assert response.status_code == 403
    service.generate_contract.assert_not_called()


def test_contract_creation_persists_local_authorization_mapping(client):
    buyer = _enterprise("本地映射买方")
    seller = _enterprise("本地映射卖方")
    _login(client, buyer)
    service = MagicMock()
    service.generate_contract.return_value = "CT-LOCAL-MAP"

    with (
        patch("app.routes.contract.get_econtract_service", return_value=service),
        patch("app.routes.contract.send_message"),
    ):
        response = client.post(
            "/contract/create",
            data={
                "buyer_id": buyer.id,
                "seller_id": seller.id,
                "product_name": "连接器",
                "quantity": 100,
                "unit": "件",
                "price": 10,
                "total_amount": 1000,
                "delivery_time": "2026-10-01",
                "payment_terms": "验收后付款",
            },
        )

    assert response.status_code == 302
    tx = Transaction.query.filter_by(buyer_id=buyer.id, seller_id=seller.id).one()
    assert tx.invoice_info["contract_id"] == "CT-LOCAL-MAP"
    assert tx.invoice_info["created_by"] == buyer.id
    assert tx.fulfillment_status == "contract_pending"


def test_contract_creation_rejects_invalid_commercial_terms(client):
    buyer = _enterprise("条款校验买方")
    seller = _enterprise("条款校验卖方")
    _login(client, buyer)
    service = MagicMock()

    with patch("app.routes.contract.get_econtract_service", return_value=service):
        response = client.post(
            "/contract/create",
            data={
                "buyer_id": buyer.id,
                "seller_id": seller.id,
                "product_name": "连接器",
                "quantity": -1,
                "unit": "件",
                "price": 10,
                "total_amount": -10,
            },
        )

    assert response.status_code == 400
    service.generate_contract.assert_not_called()


def test_collaboration_code_reuses_local_contract_mapping(app, _db):
    buyer = _enterprise("撮合码买方")
    seller = _enterprise("撮合码卖方")
    tx = _contract_transaction(buyer, seller, "CT-CODE-1")
    service = EContractService(
        provider="custom",
        api_key="test-only",
        base_url="https://contract-provider.example",
    )

    with patch.object(
        service,
        "_call_api",
        return_value={
            "buyer_id": buyer.id,
            "seller_id": seller.id,
            "product_name": "高压线束",
            "amount_range": "1-5万",
        },
    ):
        first = service.generate_collaboration_code("CT-CODE-1")
        second = service.generate_collaboration_code("CT-CODE-1")

    assert first == second
    assert Transaction.query.count() == 1
    assert Transaction.query.get(tx.id).match_code == first


def test_collaboration_code_rejects_provider_party_mismatch(app, _db):
    buyer = _enterprise("一致性买方")
    seller = _enterprise("一致性卖方")
    attacker = _enterprise("错误签约方")
    tx = _contract_transaction(buyer, seller, "CT-CODE-2")
    service = EContractService(
        provider="custom",
        api_key="test-only",
        base_url="https://contract-provider.example",
    )

    with patch.object(
        service,
        "_call_api",
        return_value={
            "buyer_id": attacker.id,
            "seller_id": seller.id,
            "product_name": "高压线束",
        },
    ):
        with pytest.raises(ValueError, match="签约方"):
            service.generate_collaboration_code("CT-CODE-2")

    assert Transaction.query.get(tx.id).match_code is None

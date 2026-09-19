from datetime import date

from flask_login import login_user

from app import db
from app.models import Enterprise
from app.services.order_service import OrderService


def _make_enterprise(name: str) -> Enterprise:
    ent = Enterprise(
        name=name,
        role="enterprise",
        verification_status="approved",
        is_verified=True,
    )
    ent.set_password("test123456")
    db.session.add(ent)
    db.session.commit()
    return ent


def test_update_status_uses_current_enterprise_order_namespace(client, app):
    """SaaS orders use per-enterprise ids, so status updates must be owner-scoped."""
    with app.app_context():
        first = _make_enterprise("订单命名空间企业A")
        second = _make_enterprise("订单命名空间企业B")
        first_order = OrderService.create_order(
            enterprise_id=first.id,
            product_name="企业A物料",
            quantity=1,
            unit="件",
            customer_name="客户A",
            order_date=date(2026, 6, 12),
        )
        second_order = OrderService.create_order(
            enterprise_id=second.id,
            product_name="企业B物料",
            quantity=2,
            unit="件",
            customer_name="客户B",
            order_date=date(2026, 6, 12),
        )

        assert first_order.id == second_order.id == 1

        with client:
            login_user(second)
            response = client.post(
                "/orders/1/update-status",
                json={"status": "in_progress"},
            )

        assert response.status_code == 200
        assert response.get_json()["success"] is True

        assert OrderService.get_orders(second.id)["orders"][0].status == "in_progress"
        first_id = first.id
    assert OrderService.get_orders(first_id)["orders"][0].status == "pending"


def test_formal_order_requires_independent_contract_and_payment_confirmations(
    client, test_enterprise
):
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.commit()
    assert client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    ).status_code == 200
    order = OrderService.create_order(
        enterprise_id=test_enterprise.id,
        product_name="连接器",
        quantity=100,
        unit="件",
        customer_name="供应商",
        order_date=date(2026, 6, 12),
        metadata={
            "chain_xiaoyi_task_id": 99,
            "requires_contract_confirmation": True,
            "requires_payment_confirmation": True,
        },
    )

    blocked = client.post(
        f"/orders/{order.id}/update-status",
        json={"status": "in_progress"},
    )
    assert blocked.status_code == 409
    assert "合同" in blocked.get_json()["message"]

    contract = client.post(
        f"/orders/{order.id}/confirm-contract",
        json={"confirm": True},
    )
    assert contract.status_code == 200
    payment = client.post(
        f"/orders/{order.id}/confirm-payment",
        json={"confirm": True},
    )
    assert payment.status_code == 200

    ready = client.post(
        f"/orders/{order.id}/update-status",
        json={"status": "in_progress"},
    )
    assert ready.status_code == 200
    assert ready.get_json()["order"]["status"] == "in_progress"


def test_order_confirmation_is_idempotent_and_rejects_false_confirmation(
    client, test_enterprise
):
    test_enterprise.verification_status = "approved"
    test_enterprise.is_verified = True
    db.session.commit()
    assert client.post(
        "/auth/login",
        data={"name": test_enterprise.name, "password": "test123456"},
        headers={"X-Login-Modal": "1"},
    ).status_code == 200
    order = OrderService.create_order(
        enterprise_id=test_enterprise.id,
        product_name="冲压件",
        quantity=50,
        unit="件",
        customer_name="供应商",
        order_date=date(2026, 6, 12),
        metadata={"requires_contract_confirmation": True},
    )

    rejected = client.post(
        f"/orders/{order.id}/confirm-contract",
        json={"confirm": False},
    )
    assert rejected.status_code == 400

    first = client.post(
        f"/orders/{order.id}/confirm-contract",
        json={"confirm": True},
    )
    second = client.post(
        f"/orders/{order.id}/confirm-contract",
        json={"confirm": True},
    )
    assert first.status_code == second.status_code == 200
    assert second.get_json()["idempotent"] is True

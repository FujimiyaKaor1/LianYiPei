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
        assert OrderService.get_orders(first.id)["orders"][0].status == "pending"

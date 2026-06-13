"""
SaaS 订单：存于 Enterprise.extras['saas_orders'] 列表（替代 orders 表）。
"""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm.attributes import flag_modified

from app import db
from app.models import Enterprise, Transaction


class _OrderView:
    """兼容原 Order 属性访问（模板 / 路由）。"""

    def __init__(self, enterprise_id: int, data: Dict[str, Any]):
        self.enterprise_id = enterprise_id
        self._d = data

    def __getattr__(self, name: str):
        if name in self._d:
            return self._d[name]
        raise AttributeError(name)


def _extras(ent: Enterprise) -> Dict[str, Any]:
    return dict(ent.extras) if isinstance(ent.extras, dict) else {}


def _saas_orders(ent: Enterprise) -> List[Dict[str, Any]]:
    ex = _extras(ent)
    raw = ex.get("saas_orders")
    return list(raw) if isinstance(raw, list) else []


def _save_saas_orders(ent: Enterprise, orders: List[Dict[str, Any]]) -> None:
    ex = _extras(ent)
    ex["saas_orders"] = orders
    ent.extras = ex
    flag_modified(ent, "extras")


def _next_order_id(orders: List[Dict[str, Any]]) -> int:
    if not orders:
        return 1
    return max(int(o.get("id", 0) or 0) for o in orders) + 1


class OrderService:
    @staticmethod
    def generate_order_no() -> str:
        date_str = datetime.now().strftime("%Y%m%d")
        random_str = secrets.token_hex(3).upper()
        return f"ORD{date_str}{random_str}"

    @staticmethod
    def create_order(
        enterprise_id: int,
        product_name: str,
        quantity: int,
        unit: str,
        customer_name: str,
        order_date: date,
        delivery_date: Optional[date] = None,
        notes: str = "",
    ) -> _OrderView:
        ent = Enterprise.query.get_or_404(enterprise_id)
        orders = _saas_orders(ent)
        oid = _next_order_id(orders)
        row = {
            "id": oid,
            "order_no": OrderService.generate_order_no(),
            "product_name": product_name,
            "quantity": quantity,
            "unit": unit,
            "customer_name": customer_name,
            "order_date": order_date.isoformat() if order_date else None,
            "delivery_date": delivery_date.isoformat() if delivery_date else None,
            "actual_delivery_date": None,
            "status": "pending",
            "notes": notes,
            "created_at": datetime.utcnow().isoformat(),
        }
        orders.append(row)
        _save_saas_orders(ent, orders)
        ent.current_orders = (ent.current_orders or 0) + 1
        ent.last_order_update = datetime.utcnow()
        db.session.commit()
        return _OrderView(enterprise_id, row)

    @staticmethod
    def _find_order(order_id: int, enterprise_id: Optional[int] = None) -> tuple[Enterprise, Dict[str, Any]]:
        if enterprise_id is not None:
            enterprises = [Enterprise.query.get_or_404(enterprise_id)]
        else:
            enterprises = Enterprise.query.all()

        for ent in enterprises:
            for row in _saas_orders(ent):
                if int(row.get("id", 0)) == int(order_id):
                    return ent, row

        from flask import abort

        abort(404)

    @staticmethod
    def update_order_status(
        order_id: int,
        status: str,
        actual_delivery_date: Optional[date] = None,
        enterprise_id: Optional[int] = None,
    ) -> _OrderView:
        ent, row = OrderService._find_order(order_id, enterprise_id=enterprise_id)
        orders = _saas_orders(ent)
        target = None
        for candidate in orders:
            if int(candidate.get("id", 0)) == int(order_id):
                target = candidate
                break
        if target is None:
            from flask import abort

            abort(404)
        old_status = target.get("status")
        target["status"] = status
        if status == "completed" and actual_delivery_date:
            target["actual_delivery_date"] = actual_delivery_date.isoformat()
        _save_saas_orders(ent, orders)
        if status in ("completed", "cancelled") and old_status not in ("completed", "cancelled"):
            if ent.current_orders and ent.current_orders > 0:
                ent.current_orders -= 1
            ent.last_order_update = datetime.utcnow()
        db.session.commit()
        return _OrderView(ent.id, target)

    @staticmethod
    def get_orders(
        enterprise_id: int,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict:
        ent = Enterprise.query.get_or_404(enterprise_id)
        rows = [r for r in _saas_orders(ent)]
        if status:
            rows = [r for r in rows if r.get("status") == status]

        def _od(r):
            d = r.get("order_date")
            if not d:
                return None
            if isinstance(d, date):
                return d
            try:
                return date.fromisoformat(str(d)[:10])
            except Exception:
                return None

        if start_date:
            rows = [r for r in rows if _od(r) and _od(r) >= start_date]
        if end_date:
            rows = [r for r in rows if _od(r) and _od(r) <= end_date]
        rows.sort(key=lambda r: r.get("order_date") or "", reverse=True)
        total = len(rows)
        start = (page - 1) * per_page
        chunk = rows[start : start + per_page]
        items = [_OrderView(enterprise_id, x) for x in chunk]
        pages = (total + per_page - 1) // per_page if per_page else 1
        return {
            "orders": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": pages,
        }

    @staticmethod
    def get_order_by_id(order_id: int, enterprise_id: Optional[int] = None) -> _OrderView:
        ent, row = OrderService._find_order(order_id, enterprise_id=enterprise_id)
        return _OrderView(ent.id, row)

    @staticmethod
    def update_order(order_id: int, enterprise_id: Optional[int] = None, **kwargs) -> _OrderView:
        ov = OrderService.get_order_by_id(order_id, enterprise_id=enterprise_id)
        ent = Enterprise.query.get_or_404(ov.enterprise_id)
        orders = _saas_orders(ent)
        for o in orders:
            if int(o.get("id", 0)) == int(order_id):
                for field in [
                    "product_name",
                    "quantity",
                    "unit",
                    "customer_name",
                    "order_date",
                    "delivery_date",
                    "notes",
                ]:
                    if field in kwargs:
                        val = kwargs[field]
                        if field in ("order_date", "delivery_date") and hasattr(val, "isoformat"):
                            o[field] = val.isoformat()
                        else:
                            o[field] = val
                _save_saas_orders(ent, orders)
                db.session.commit()
                return _OrderView(ent.id, o)
        from flask import abort

        abort(404)

    @staticmethod
    def delete_order(order_id: int, enterprise_id: Optional[int] = None) -> bool:
        ov = OrderService.get_order_by_id(order_id, enterprise_id=enterprise_id)
        ent = Enterprise.query.get_or_404(ov.enterprise_id)
        orders = [o for o in _saas_orders(ent) if int(o.get("id", 0)) != int(order_id)]
        _save_saas_orders(ent, orders)
        if ov._d.get("status") not in ("completed", "cancelled"):
            if ent.current_orders and ent.current_orders > 0:
                ent.current_orders -= 1
            ent.last_order_update = datetime.utcnow()
        db.session.commit()
        return True

    @staticmethod
    def get_order_statistics(enterprise_id: int) -> Dict:
        ent = Enterprise.query.get_or_404(enterprise_id)
        rows = _saas_orders(ent)
        return {
            "total": len(rows),
            "pending": sum(1 for r in rows if r.get("status") == "pending"),
            "in_progress": sum(1 for r in rows if r.get("status") == "in_progress"),
            "completed": sum(1 for r in rows if r.get("status") == "completed"),
            "cancelled": sum(1 for r in rows if r.get("status") == "cancelled"),
        }

    @staticmethod
    def export_orders_data(
        enterprise_id: int,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict]:
        pack = OrderService.get_orders(
            enterprise_id, status, start_date, end_date, page=1, per_page=100000
        )
        data = []
        for o in pack["orders"]:
            d = o._d
            data.append(
                {
                    "订单编号": d.get("order_no"),
                    "产品名称": d.get("product_name"),
                    "数量": d.get("quantity"),
                    "单位": d.get("unit"),
                    "客户名称": d.get("customer_name"),
                    "订单日期": (d.get("order_date") or "")[:10],
                    "预计交货日期": (d.get("delivery_date") or "")[:10],
                    "实际交货日期": (d.get("actual_delivery_date") or "")[:10],
                    "状态": d.get("status"),
                    "备注": d.get("notes") or "",
                }
            )
        return data

    @staticmethod
    def sync_capacity_data() -> int:
        enterprises = Enterprise.query.filter(Enterprise.max_capacity.isnot(None)).all()
        count = 0
        for enterprise in enterprises:
            in_progress_count = sum(
                1
                for r in _saas_orders(enterprise)
                if r.get("status") in ("pending", "in_progress")
            )
            if enterprise.current_orders != in_progress_count:
                enterprise.current_orders = in_progress_count
                enterprise.last_order_update = datetime.utcnow()
                count += 1
        if count > 0:
            db.session.commit()
        return count

    @staticmethod
    def get_capacity_calendar(enterprise_id: int, year: int, month: int) -> Dict:
        from calendar import monthrange

        enterprise = Enterprise.query.get_or_404(enterprise_id)
        _, days_in_month = monthrange(year, month)
        calendar_data = {}
        for day in range(1, days_in_month + 1):
            target_date = date(year, month, day)
            orders_count = sum(
                1
                for r in _saas_orders(enterprise)
                if r.get("status") in ("pending", "in_progress")
                and (
                    (r.get("order_date") or "")[:10] == target_date.isoformat()
                    or (r.get("delivery_date") or "")[:10] == target_date.isoformat()
                )
            )
            max_cap = enterprise.max_capacity or 0
            # 按日占用：当日在制订单数相对产能上限的比例（0–100%），便于日历热力区分
            if max_cap > 0:
                utilization = min(1.0, float(orders_count) / float(max_cap))
            else:
                utilization = 0.0
            util_pct = round(utilization * 100, 1)
            if util_pct >= 80:
                status, color = "full", "danger"
            elif util_pct >= 50:
                status, color = "normal", "warning"
            elif util_pct > 0:
                status, color = "available", "success"
            else:
                status, color = "idle", "neutral"
            date_iso = target_date.strftime("%Y-%m-%d")
            calendar_data[str(day)] = {
                "date": date_iso,
                "orders_count": orders_count,
                "order_count": orders_count,
                "utilization": util_pct,
                "status": status,
                "color": color,
            }
        return {
            "year": year,
            "month": month,
            "days": calendar_data,
            "current_orders": enterprise.current_orders or 0,
            "max_capacity": enterprise.max_capacity or 0,
            "overall_utilization": round(
                (enterprise.current_orders or 0)
                / (enterprise.max_capacity or 1)
                * 100,
                1,
            ),
        }

    @staticmethod
    def get_orders_by_date(enterprise_id: int, target_date: date) -> List[_OrderView]:
        ent = Enterprise.query.get_or_404(enterprise_id)
        out = []
        for r in _saas_orders(ent):
            od = (r.get("order_date") or "")[:10]
            dd = (r.get("delivery_date") or "")[:10]
            if od == target_date.isoformat() or dd == target_date.isoformat():
                out.append(_OrderView(enterprise_id, r))
        return out

    @staticmethod
    def update_calendar_visibility(enterprise_id: int, visibility: str) -> bool:
        if visibility not in ("public", "partners", "private"):
            raise ValueError("Invalid visibility value")
        enterprise = Enterprise.query.get_or_404(enterprise_id)
        enterprise.capacity_calendar_visibility = visibility
        db.session.commit()
        return True

    @staticmethod
    def can_view_calendar(viewer_id: int, owner_id: int) -> bool:
        if viewer_id == owner_id:
            return True
        owner = Enterprise.query.get_or_404(owner_id)
        if owner.capacity_calendar_visibility == "public":
            return True
        if owner.capacity_calendar_visibility == "private":
            return False
        if owner.capacity_calendar_visibility == "partners":
            has_collaboration = (
                Transaction.query.filter(
                    or_(
                        and_(
                            Transaction.buyer_id == viewer_id,
                            Transaction.seller_id == owner_id,
                        ),
                        and_(
                            Transaction.buyer_id == owner_id,
                            Transaction.seller_id == viewer_id,
                        ),
                    )
                ).first()
                is not None
            )
            return has_collaboration
        return False

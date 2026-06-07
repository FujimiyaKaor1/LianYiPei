"""
履约看板：聚合信用趋势、交付统计、进行中履约记录（供 /api/fulfillment 与 fulfillment 蓝图复用）。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List

from app.models import Enterprise, Transaction
from app.services.credit_score_events import credit_events_newest_first, credit_events_oldest_first

_TERMINAL_FULFILLMENT = frozenset({"verified", "completed", "failed", "cancelled"})


def _naive(dt: datetime) -> datetime:
    """剥除时区信息，统一转 naive（避免 naive/aware 比较炸 500）。"""
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt


def _parse_event_dt(ev: dict) -> datetime | None:
    raw = ev.get("created_at")
    if not raw:
        return None
    try:
        s = str(raw).strip()
        # 尝试完整 ISO8601（含时区），再 fallback 纯日期时间
        try:
            dt = datetime.fromisoformat(s)
            return _naive(dt)
        except ValueError:
            dt = datetime.fromisoformat(s.replace("Z", ""))
            return _naive(dt)
    except Exception:
        return None


def build_credit_trend(eid: int, start: datetime, end: datetime) -> list:
    """按月返回信用分趋势。"""
    ent = Enterprise.query.get(eid)
    if not ent:
        return []
    # 统一转 naive，避免比较时 aware/naive 混用
    start_n = _naive(start)
    end_n = _naive(end)
    records = []
    for ev in credit_events_oldest_first(ent):
        dt = _parse_event_dt(ev)
        if dt is None:
            continue
        if start_n <= dt <= end_n:
            records.append((dt, float(ev.get("new_score") or 0)))

    monthly: dict[str, float] = {}
    for dt, new_score in records:
        key = dt.strftime("%Y-%m")
        monthly[key] = new_score

    result = []
    current = start_n.replace(day=1)
    last_score = None
    while current <= end_n:
        key = current.strftime("%Y-%m")
        score = monthly.get(key, last_score)
        if score is not None:
            result.append({"month": key, "score": score})
            last_score = score
        current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

    return result


def build_delivery_stats(eid: int, since: datetime) -> dict:
    rows = Transaction.query.filter(
        Transaction.seller_id == eid,
        Transaction.created_at >= since,
    ).all()
    records = []
    for tx in rows:
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if info.get("verified"):
            records.append(tx)

    total = len(records)
    on_time_count = sum(1 for r in records if (r.invoice_info or {}).get("on_time", True))
    own_rate = round(on_time_count / total * 100, 1) if total else 0.0

    all_verified = []
    for tx in Transaction.query.all():
        inf = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if inf.get("verified"):
            all_verified.append(tx)
    all_total = len(all_verified)
    all_on_time = sum(1 for tx in all_verified if (tx.invoice_info or {}).get("on_time", True))
    industry_rate = round(all_on_time / all_total * 100, 1) if all_total else 85.0

    return {
        "own_rate": own_rate,
        "industry_rate": industry_rate,
        "total_count": total,
        "on_time_count": on_time_count,
    }


def build_score_dimensions(eid: int) -> dict:
    from collections import defaultdict

    type_map = {
        "fulfillment_on_time": "履约",
        "fulfillment_late": "履约",
        "data_auth": "数据更新",
        "data_update": "数据更新",
        "report_verified": "举报",
        "report_false": "举报",
        "activity_inquiry": "交易",
        "activity_quote": "交易",
        "batch_recalculate": "系统",
        "consecutive_bonus": "履约",
    }

    ent = Enterprise.query.get(eid)
    agg: dict[str, float] = defaultdict(float)
    if ent:
        for ev in credit_events_oldest_first(ent):
            ct = ev.get("change_type") or ""
            agg[ct] += float(ev.get("change_value") or 0)

    dims: dict[str, float] = {"交易": 0, "履约": 0, "数据更新": 0, "举报": 0, "系统": 0}
    for change_type, total in agg.items():
        dim = type_map.get(change_type, "系统")
        dims[dim] = dims.get(dim, 0) + (total or 0)

    return dims


def build_history(eid: int) -> list:
    ent = Enterprise.query.get(eid)
    if not ent:
        return []
    records = credit_events_newest_first(ent)[:10]
    out = []
    for r in records:
        dt = _parse_event_dt(r)
        # strftime 兼容 naive/aware
        ts = (dt.strftime("%Y-%m-%d %H:%M") if dt else "")
        out.append(
            {
                "id": r.get("id"),
                "change_value": r.get("change_value"),
                "change_type": r.get("change_type"),
                "reason": r.get("reason"),
                "old_score": r.get("old_score"),
                "new_score": r.get("new_score"),
                "created_at": ts,
            }
        )
    return out


def get_dashboard_payload(eid: int) -> Dict[str, Any]:
    """与 fulfillment.dashboard_data 返回字段一致（含 success）。"""
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)

    trend = build_credit_trend(eid, twelve_months_ago, now)
    delivery_stats = build_delivery_stats(eid, twelve_months_ago)
    dimensions = build_score_dimensions(eid)
    history = build_history(eid)

    ent = Enterprise.query.get(eid)
    current_score = float(ent.credit_score or 60.0) if ent else 60.0

    return {
        "success": True,
        "current_score": current_score,
        "trend": trend,
        "delivery_stats": delivery_stats,
        "dimensions": dimensions,
        "history": history,
    }


def _payment_progress(info: dict) -> float:
    raw = info.get("payment_progress")
    if isinstance(raw, (int, float)):
        return max(0.0, min(100.0, float(raw)))
    paid = info.get("paid_amount")
    total = info.get("invoice_amount") or info.get("total_amount")
    try:
        if paid is not None and total:
            return max(0.0, min(100.0, float(paid) / float(total) * 100))
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return 0.0


def serialize_active_fulfillment(tx: Transaction) -> Dict[str, Any]:
    info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
    logistics = info.get("logistics") if isinstance(info.get("logistics"), dict) else {}
    qc_status = info.get("qc_status") or info.get("quality_status") or "pending"

    return {
        "id": tx.id,
        "product_name": tx.product_name,
        "buyer_id": tx.buyer_id,
        "fulfillment_status": tx.fulfillment_status or "pending",
        "created_at": tx.created_at.isoformat() + "Z" if tx.created_at else None,
        "logistics_nodes": logistics.get("nodes")
        or info.get("logistics_nodes")
        or [],
        "logistics_current": logistics.get("current") or info.get("logistics_current"),
        "qc_status": qc_status,
        "payment_progress": round(_payment_progress(info), 1),
        "invoice_info": {
            "verified": bool(info.get("verified")),
            "on_time": info.get("on_time", True),
            "delivery_date": info.get("delivery_date"),
        },
    }


def get_active_fulfillments(eid: int, limit: int = 20) -> List[Dict[str, Any]]:
    """当前用户作为卖方的进行中履约（Transaction，排除已闭环状态）。"""
    q = (
        Transaction.query.filter(Transaction.seller_id == eid)
        .order_by(Transaction.created_at.desc())
        .limit(200)
        .all()
    )
    out: List[Dict[str, Any]] = []
    for tx in q:
        st = (tx.fulfillment_status or "").lower()
        if st in _TERMINAL_FULFILLMENT:
            continue
        out.append(serialize_active_fulfillment(tx))
        if len(out) >= limit:
            break
    return out

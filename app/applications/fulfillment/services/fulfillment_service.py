"""
履约数据回流：写入 Transaction.invoice_info，案例写入 Enterprise.cooperation_cases JSON。
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import db
from app.models import Enterprise, Message, Transaction
from app.services import credit_engine

logger = logging.getLogger(__name__)


def _mask_buyer_name(buyer_name: str) -> str:
    if not buyer_name:
        return "某企业"
    if "500强" in buyer_name:
        return "某世界500强企业"
    if "上市" in buyer_name:
        return "某上市公司"
    if len(buyer_name) <= 2:
        return buyer_name[0] + "*"
    return buyer_name[0] + "*" * (len(buyer_name) - 2) + buyer_name[-1]


def _get_amount_range(amount: Optional[float]) -> str:
    if not amount:
        return "金额保密"
    if amount < 10_000:
        return "1万以下"
    if amount < 100_000:
        return f"{int(amount/10000)}-{int(amount/10000)+1}万"
    if amount < 1_000_000:
        return f"{int(amount/10000)}万-{int(amount/10000+10)}万"
    if amount < 10_000_000:
        return f"{int(amount/10000)}万-{int(amount/10000*1.2):.0f}万"
    return f"{amount/10000000:.0f}千万以上"


def _get_cooperation_time(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.utcnow()
    quarter = (dt.month - 1) // 3 + 1
    return f"{dt.year}年Q{quarter}"


def _tx_on_time(tx: Transaction) -> bool:
    info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
    return bool(info.get("on_time", True))


def _coop_cases(ent: Enterprise) -> List[Dict[str, Any]]:
    raw = ent.cooperation_cases
    return list(raw) if isinstance(raw, list) else []


def trigger_fulfillment_backflow(
    collaboration_code: str,
    invoice_info: dict,
    buyer_id: int,
    seller_id: int,
) -> dict:
    result: dict = {
        "success": False,
        "fulfillment_id": None,
        "credit_update": {},
        "case_id": None,
    }
    try:
        invoice_info = dict(invoice_info or {})
        invoice_info["collaboration_code"] = collaboration_code

        from app.services.invoice_validator import store_fulfillment_data

        fulfillment = store_fulfillment_data(invoice_info, buyer_id, seller_id)
        if not fulfillment:
            logger.error("履约数据存储失败")
            return result
        result["fulfillment_id"] = fulfillment.id

        _update_tx_match_status(collaboration_code, _tx_on_time(fulfillment))

        change_type = (
            "fulfillment_on_time" if _tx_on_time(fulfillment) else "fulfillment_late"
        )
        reason = "按时履约" if _tx_on_time(fulfillment) else "逾期履约"
        credit_result = credit_engine.update_credit_score(
            enterprise_id=seller_id,
            change_type=change_type,
            reason=reason,
        )
        result["credit_update"] = credit_result

        case_id = _auto_append_case(fulfillment, buyer_id, seller_id, collaboration_code)
        result["case_id"] = case_id

        _notify_fulfillment_complete(buyer_id, seller_id, fulfillment, credit_result)

        result["success"] = True
        logger.info(
            "履约数据回流完成: code=%s seller=%s",
            collaboration_code,
            seller_id,
        )
    except Exception as exc:
        db.session.rollback()
        logger.error("履约数据回流异常: %s", exc, exc_info=True)

    return result


def _update_tx_match_status(code: str, on_time: bool):
    if not code:
        return
    tx = Transaction.query.filter_by(match_code=code).first()
    if tx:
        tx.fulfillment_status = "fulfilled" if on_time else "failed"
        db.session.commit()


def _auto_append_case(
    tx: Transaction,
    buyer_id: int,
    seller_id: int,
    collaboration_code: str,
) -> Optional[str]:
    try:
        buyer = Enterprise.query.get(buyer_id)
        seller = Enterprise.query.get(seller_id)
        if not seller:
            return None
        masked = _mask_buyer_name(buyer.name if buyer else "未知企业")
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        amt = info.get("invoice_amount")
        case_id = f"case_{seller_id}_{int(time.time())}"
        entry = {
            "id": case_id,
            "buyer_name_masked": masked,
            "product_category": collaboration_code or "通用产品",
            "cooperation_time": _get_cooperation_time(tx.created_at),
            "amount_range": _get_amount_range(float(amt) if amt is not None else None),
            "is_public": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        cases = _coop_cases(seller)
        cases.append(entry)
        seller.cooperation_cases = cases
        db.session.commit()
        return case_id
    except Exception as exc:
        logger.warning("自动生成案例条目失败: %s", exc)
        db.session.rollback()
        return None


def _notify_fulfillment_complete(
    buyer_id: int,
    seller_id: int,
    fulfillment: Transaction,
    credit_result: dict,
):
    try:
        change = credit_result.get("change_value", 0)
        new_score = credit_result.get("new_score", 0)
        status_text = "按时完成" if _tx_on_time(fulfillment) else "逾期完成"
        seller_msg = Message(
            recipient_id=seller_id,
            message_type="transaction",
            title=f"履约数据已回流（{status_text}）",
            content=(
                f"您的履约数据已成功记录。"
                f"信用分变化：{change:+.1f}分，当前信用分：{new_score:.1f}分。"
            ),
            link_url="/fulfillment/dashboard",
            priority="normal",
        )
        db.session.add(seller_msg)
        buyer_msg = Message(
            recipient_id=buyer_id,
            message_type="transaction",
            title="合作履约已完成",
            content=f"您的合作订单已{status_text}，履约数据已记录。",
            link_url="/fulfillment/dashboard",
            priority="normal",
        )
        db.session.add(buyer_msg)
        db.session.commit()
    except Exception as exc:
        logger.warning("发送履约通知失败: %s", exc)


def toggle_case_visibility(case_id: str, enterprise_id: int, is_public: bool) -> bool:
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return False
    cases = _coop_cases(ent)
    for c in cases:
        if isinstance(c, dict) and c.get("id") == case_id:
            c["is_public"] = is_public
            ent.cooperation_cases = cases
            db.session.commit()
            return True
    return False


def get_public_cases(supplier_id: int, limit: int = 10) -> list:
    supplier = Enterprise.query.get(supplier_id)
    score = float(supplier.credit_score or 60.0) if supplier else 60.0
    max_cases = 3 if score < 80 else limit
    cases = [c for c in _coop_cases(supplier) if isinstance(c, dict) and c.get("is_public")]
    cases = sorted(cases, key=lambda x: x.get("created_at") or "", reverse=True)[:max_cases]
    return cases


def get_all_cases(supplier_id: int) -> list:
    supplier = Enterprise.query.get(supplier_id)
    if not supplier:
        return []
    return [c for c in _coop_cases(supplier) if isinstance(c, dict)]

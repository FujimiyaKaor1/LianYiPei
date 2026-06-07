"""
合作闭环：撮合码使用 Transaction.match_code；API 密钥使用环境变量 COLLAB_API_KEYS。
"""
from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from sqlalchemy import and_, or_

from config import get_collab_api_keys

from app import db
from app.models import Enterprise, Message, Transaction
from app.services.credit_engine import update_credit_score

logger = logging.getLogger(__name__)


def _mask_enterprise_name(name: str) -> str:
    if not name:
        return "某企业"
    if len(name) <= 4:
        return name[:2] + "***"
    return name[:3] + "***" + name[-1]


def _amount_to_range(amount: Optional[float]) -> str:
    if not amount:
        return "未披露"
    if amount < 100000:
        return "10万以下"
    if amount < 500000:
        return "10-50万"
    if amount < 1000000:
        return "50-100万"
    if amount < 5000000:
        return "100-500万"
    return "500万以上"


class CollaborationCodeManager:
    INTERFACE_TYPE = "collab"

    def generate_code(
        self, buyer_id: int, seller_id: int, contract_id: str = ""
    ) -> str:
        max_tries = 10
        code_str = ""
        for _ in range(max_tries):
            code_str = Transaction.generate_match_code(buyer_id, seller_id, contract_id)
            if not Transaction.query.filter_by(match_code=code_str).first():
                break
        tx = Transaction(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name="撮合订单",
            status="pending",
            match_code=code_str,
            invoice_info={"contract_id": contract_id} if contract_id else {},
            fulfillment_status="pending",
        )
        db.session.add(tx)
        db.session.commit()
        return code_str

    def verify_code(self, code: str, api_key: str) -> Tuple[Optional[Dict], Optional[str]]:
        if api_key not in get_collab_api_keys():
            logger.info("collab verify unauthorized code=%s", code)
            return None, "API密钥无效或已过期"

        tx = Transaction.query.filter_by(match_code=code).first()
        if not tx:
            return None, "撮合码不存在"

        buyer = Enterprise.query.get(tx.buyer_id)
        seller = Enterprise.query.get(tx.seller_id)
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        return {
            "valid": True,
            "code": code,
            "buyer_name": _mask_enterprise_name(buyer.name if buyer else ""),
            "seller_name": _mask_enterprise_name(seller.name if seller else ""),
            "product_category": tx.product_name or "未知",
            "amount_range": info.get("amount_range") or "未披露",
            "fulfillment_status": tx.fulfillment_status or "pending",
            "cooperation_date": tx.created_at.strftime("%Y-%m") if tx.created_at else "",
        }, None

    def get_code_details(self, code: str) -> Optional[Dict]:
        tx = Transaction.query.filter_by(match_code=code).first()
        if not tx:
            return None
        buyer = Enterprise.query.get(tx.buyer_id)
        seller = Enterprise.query.get(tx.seller_id)
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        return {
            "id": tx.id,
            "code": tx.match_code,
            "buyer_id": tx.buyer_id,
            "buyer_name": buyer.name if buyer else "",
            "seller_id": tx.seller_id,
            "seller_name": seller.name if seller else "",
            "contract_id": info.get("contract_id"),
            "product_name": tx.product_name,
            "amount_range": info.get("amount_range"),
            "fulfillment_status": tx.fulfillment_status,
            "valid_until": info.get("valid_until"),
            "created_at": tx.created_at.isoformat() if tx.created_at else None,
        }

    def log_verification(
        self,
        code: str,
        caller_api_key: str,
        caller_name: str,
        ip_address: str,
        result: str,
    ) -> None:
        logger.info(
            "collab_verify code=%s result=%s ip=%s caller=%s",
            code,
            result,
            ip_address,
            caller_name,
        )


collaboration_code_manager = CollaborationCodeManager()


def generate_collaboration_code(
    buyer_id: int,
    seller_id: int,
    product_name: str = "",
    contract_id: str = "",
    amount_range: str = "",
) -> Transaction:
    code_str = Transaction.generate_match_code(buyer_id, seller_id, contract_id)
    tx = Transaction(
        buyer_id=buyer_id,
        seller_id=seller_id,
        product_name=product_name or "撮合订单",
        status="pending",
        match_code=code_str,
        invoice_info={
            "contract_id": contract_id or None,
            "amount_range": amount_range or None,
        },
        fulfillment_status="pending",
    )
    db.session.add(tx)
    db.session.commit()
    return tx


def verify_collaboration_code(
    code: str,
    api_key_value: str,
    ip_address: str = "",
) -> tuple[dict | None, str | None]:
    if api_key_value not in get_collab_api_keys():
        logger.warning("verify_collaboration_code unauthorized ip=%s", ip_address)
        return None, "API密钥无效或已过期"

    tx = Transaction.query.filter_by(match_code=code).first()
    if not tx:
        return None, "撮合码不存在"

    buyer = Enterprise.query.get(tx.buyer_id)
    seller = Enterprise.query.get(tx.seller_id)
    info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
    return {
        "valid": True,
        "code": code,
        "buyer_name": _mask_enterprise_name(buyer.name if buyer else ""),
        "seller_name": _mask_enterprise_name(seller.name if seller else ""),
        "product_category": tx.product_name or "未知",
        "amount_range": info.get("amount_range") or "未披露",
        "fulfillment_status": tx.fulfillment_status or "pending",
        "cooperation_date": tx.created_at.strftime("%Y-%m") if tx.created_at else "",
    }, None


def record_fulfillment(
    buyer_id: int,
    seller_id: int,
    on_time: bool,
    quality_rating: int = 4,
    invoice_no: str = "",
    invoice_amount: float = 0.0,
    collaboration_code: str = "",
) -> Transaction:
    inv = {
        "invoice_no": invoice_no,
        "invoice_amount": invoice_amount,
        "on_time": on_time,
        "quality_rating": max(1, min(5, quality_rating)),
        "verified": bool(invoice_no),
    }
    tx = Transaction(
        buyer_id=buyer_id,
        seller_id=seller_id,
        product_name="履约记录",
        status="completed",
        match_code=collaboration_code or None,
        invoice_info=inv,
        fulfillment_status="fulfilled" if on_time else "failed",
    )
    db.session.add(tx)
    db.session.flush()

    if collaboration_code:
        orig = Transaction.query.filter_by(match_code=collaboration_code).first()
        if orig and orig.id != tx.id:
            orig.fulfillment_status = "fulfilled" if on_time else "failed"

    change_type = "fulfillment_on_time" if on_time else "fulfillment_late"
    reason = f'完成履约（{"按时" if on_time else "逾期"}），质量评分{quality_rating}星'
    update_credit_score(seller_id, change_type, reason=reason)

    _update_case_library_json(buyer_id, seller_id, collaboration_code, invoice_amount)
    db.session.commit()
    return tx


def _update_case_library_json(
    buyer_id: int, seller_id: int, collab_code: str, invoice_amount: float
):
    buyer = Enterprise.query.get(buyer_id)
    seller = Enterprise.query.get(seller_id)
    if not buyer or not seller:
        return
    masked = _mask_enterprise_name(buyer.name)
    cases = seller.cooperation_cases if isinstance(seller.cooperation_cases, list) else []
    cases = list(cases)
    cases.append(
        {
            "id": f"case_{seller_id}_{int(datetime.utcnow().timestamp())}",
            "buyer_name_masked": masked,
            "product_category": collab_code or "通用产品",
            "cooperation_time": datetime.utcnow().strftime("%Y年Q")
            + str((datetime.utcnow().month - 1) // 3 + 1),
            "amount_range": _amount_to_range(invoice_amount),
            "is_public": False,
            "created_at": datetime.utcnow().isoformat(),
        }
    )
    seller.cooperation_cases = cases


def send_message(
    recipient_id: int,
    message_type: str,
    title: str,
    content: str = "",
    link_url: str = "",
    priority: str = "normal",
    mode: str = "procurement",
) -> Message:
    msg = Message(
        recipient_id=recipient_id,
        message_type=message_type,
        title=title,
        content=content,
        link_url=link_url,
        priority=priority,
        mode=mode,
    )
    db.session.add(msg)
    db.session.commit()
    return msg


def get_unread_count(enterprise_id: int) -> int:
    return Message.query.filter_by(recipient_id=enterprise_id, is_read=False).count()


def mark_messages_read(enterprise_id: int, message_ids: List[int] | None = None):
    q = Message.query.filter_by(recipient_id=enterprise_id, is_read=False)
    if message_ids:
        q = q.filter(Message.id.in_(message_ids))
    q.update(
        {"is_read": True, "read_at": datetime.utcnow()},
        synchronize_session=False,
    )
    db.session.commit()

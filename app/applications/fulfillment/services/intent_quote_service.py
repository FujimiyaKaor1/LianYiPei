"""
意向报价服务层（Intent Quote Service）
==========================================

职责：
1. 创建/更新/确认意向报价
2. 供应商回复意向报价
3. AI生成报价建议
4. 状态流转管理

关联需求：AI商机洞察、名片交换前置
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from app import db
from app.models import (
    IntentQuote,
    InquiryChat,
    MatchRecord,
    Enterprise,
    ChatMessage,
)


class IntentQuoteService:
    """意向报价业务服务"""

    # 意向报价有效期（天）
    DEFAULT_VALIDITY_DAYS = 7

    # ── 基础CRUD ───────────────────────────────────────────────────────────

    def create_intent_quote(
        self,
        buyer_id: int,
        seller_id: int,
        product_name: str,
        chat_id: Optional[int] = None,
        match_record_id: Optional[int] = None,
        quantity: Optional[int] = None,
        unit: Optional[str] = None,
        target_price: Optional[float] = None,
        budget_range: Optional[str] = None,
    ) -> tuple[IntentQuote | None, str]:
        """
        创建意向报价（草稿状态）。

        返回 (IntentQuote对象, 错误信息)。
        """
        if buyer_id == seller_id:
            return None, "不能向自己发起意向报价"

        # 检查是否已有待处理的意向报价
        existing = IntentQuote.query.filter(
            IntentQuote.buyer_id == buyer_id,
            IntentQuote.seller_id == seller_id,
            IntentQuote.product_name == product_name,
            IntentQuote.status.in_(["draft", "pending"]),
        ).first()

        if existing:
            return existing, ""

        quote = IntentQuote(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=product_name,
            chat_id=chat_id,
            match_record_id=match_record_id,
            quantity=quantity,
            unit=unit,
            target_price=target_price,
            budget_range=budget_range,
            status="draft",
            expires_at=datetime.utcnow() + timedelta(days=self.DEFAULT_VALIDITY_DAYS),
        )
        db.session.add(quote)
        db.session.commit()
        return quote, ""

    def get_intent_quote_by_id(self, quote_id: int) -> Optional[IntentQuote]:
        """根据ID获取意向报价"""
        return IntentQuote.query.get(quote_id)

    def send_intent_quote(
        self,
        quote_id: int,
        sender_id: int,
    ) -> tuple[IntentQuote | None, str]:
        """
        发送意向报价（从草稿改为待确认）。

        返回 (IntentQuote对象, 错误信息)。
        """
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return None, "意向报价不存在"

        if quote.buyer_id != sender_id:
            return None, "只有采购方可以发送意向报价"

        if quote.status == "pending":
            if not quote.buyer_confirmed:
                quote.buyer_confirmed = True
                quote.updated_at = datetime.utcnow()
                db.session.commit()
            return quote, ""

        if quote.status != "draft":
            return None, f"当前状态为 {quote.status}，无法发送"

        quote.status = "pending"
        quote.buyer_confirmed = True
        quote.updated_at = datetime.utcnow()
        db.session.commit()

        # 发送系统消息到询价会话
        if quote.chat_id:
            self._send_system_message(
                chat_id=quote.chat_id,
                content=self._build_quote_sent_message(quote),
                event="intent_quote_sent",
                metadata={"quote_id": quote.id},
            )

        return quote, ""

    def cancel_intent_quote(
        self,
        quote_id: int,
        sender_id: int,
    ) -> tuple[bool, str]:
        """
        取消意向报价。

        返回 (是否成功, 错误信息)。
        """
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return False, "意向报价不存在"

        if quote.buyer_id != sender_id:
            return False, "只有采购方可以取消意向报价"

        if quote.status in ("accepted", "rejected"):
            return False, f"当前状态为 {quote.status}，无法取消"

        quote.status = "cancelled"
        quote.updated_at = datetime.utcnow()
        db.session.commit()
        return True, ""

    # ── 供应商回复 ──────────────────────────────────────────────────────────

    def accept_intent_quote(
        self,
        quote_id: int,
        seller_id: int,
        reply_price: Optional[float] = None,
        reply_notes: Optional[str] = None,
    ) -> tuple[IntentQuote | None, str]:
        """
        供应商接受意向报价。

        返回 (IntentQuote对象, 错误信息)。
        """
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return None, "意向报价不存在"

        if quote.seller_id != seller_id:
            return None, "只有供应方可以接受意向报价"

        if quote.status != "pending":
            return None, f"当前状态为 {quote.status}，无法接受"

        quote.status = "accepted"
        quote.seller_confirmed = True
        quote.seller_reply_price = reply_price
        quote.seller_reply_notes = reply_notes
        quote.updated_at = datetime.utcnow()
        db.session.commit()

        # 更新 MatchRecord 状态
        if quote.match_record_id:
            record = MatchRecord.query.get(quote.match_record_id)
            if record and record.status not in ("contracted",):
                record.status = "quote_acknowledged"
                record.updated_at = datetime.utcnow()

        # 发送系统消息
        if quote.chat_id:
            self._send_system_message(
                chat_id=quote.chat_id,
                content=f"供应商已接受您的意向报价（报价: {reply_price or quote.target_price} 元）",
                event="intent_quote_accepted",
                metadata={"quote_id": quote.id},
            )

        return quote, ""

    def reject_intent_quote(
        self,
        quote_id: int,
        seller_id: int,
        reason: Optional[str] = None,
    ) -> tuple[IntentQuote | None, str]:
        """
        供应商拒绝意向报价。

        返回 (IntentQuote对象, 错误信息)。
        """
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return None, "意向报价不存在"

        if quote.seller_id != seller_id:
            return None, "只有供应方可以拒绝意向报价"

        if quote.status != "pending":
            return None, f"当前状态为 {quote.status}，无法拒绝"

        quote.status = "rejected"
        quote.seller_reply_notes = reason
        quote.updated_at = datetime.utcnow()
        db.session.commit()

        # 发送系统消息
        if quote.chat_id:
            reason_text = f"，拒绝原因：{reason}" if reason else ""
            self._send_system_message(
                chat_id=quote.chat_id,
                content=f"供应商婉拒了您的意向报价{reason_text}",
                event="intent_quote_rejected",
                metadata={"quote_id": quote.id},
            )

        return quote, ""

    # ── 列表查询 ────────────────────────────────────────────────────────────

    def get_buyer_quotes(
        self,
        buyer_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """获取采购方发起的意向报价列表"""
        query = IntentQuote.query.filter_by(buyer_id=buyer_id)
        if status:
            query = query.filter(IntentQuote.status == status)
        
        quotes = query.order_by(IntentQuote.created_at.desc()).offset(offset).limit(limit).all()
        return [self._serialize_quote(q, buyer_id) for q in quotes]

    def get_seller_quotes(
        self,
        seller_id: int,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """获取供应方收到的意向报价列表"""
        query = IntentQuote.query.filter_by(seller_id=seller_id)
        if status:
            query = query.filter(IntentQuote.status == status)
        
        quotes = query.order_by(IntentQuote.created_at.desc()).offset(offset).limit(limit).all()
        return [self._serialize_quote(q, seller_id) for q in quotes]

    # ── AI报价建议 ──────────────────────────────────────────────────────────

    def generate_ai_price_suggestion(
        self,
        seller_id: int,
        product_name: str,
        quantity: Optional[int] = None,
    ) -> dict:
        """
        生成AI意向报价建议。

        基于供应商产能、信用、市场价格生成建议报价。
        
        返回：
        {
            "suggested_price": float,
            "price_range": {"min": float, "max": float},
            "delivery_estimate": str,
            "basis": str,
            "capacity_available": bool,
        }
        """
        supplier = Enterprise.query.get(seller_id)
        if not supplier:
            return {
                "suggested_price": 0,
                "price_range": {"min": 0, "max": 0},
                "delivery_estimate": "无法估算",
                "basis": "供应商信息不存在",
                "capacity_available": False,
            }

        # 获取价格指数
        from app.services.quote_pool import get_price_index
        price_data = get_price_index(product_name)
        median_price = price_data.get("median_price") or 50.0

        # 基于供应商信用和产能调整报价
        credit_score = supplier.credit_score or 70.0
        capacity = supplier.capacity or 50
        max_cap = supplier.max_capacity or 100

        # 信用溢价（高信用供应商可适当提高报价）
        credit_premium = 1.0
        if credit_score >= 90:
            credit_premium = 1.1
        elif credit_score >= 85:
            credit_premium = 1.05
        elif credit_score < 70:
            credit_premium = 0.95

        # 产能充足度影响报价（产能紧张时略微提价）
        capacity_ratio = capacity / max_cap if max_cap else 0.5
        capacity_premium = 1.0 + (1 - capacity_ratio) * 0.05

        # 数量折扣（大批量采购价格更低）
        quantity_discount = 1.0
        if quantity:
            if quantity >= 1000:
                quantity_discount = 0.92
            elif quantity >= 500:
                quantity_discount = 0.95
            elif quantity >= 100:
                quantity_discount = 0.98

        suggested = median_price * credit_premium * capacity_premium * quantity_discount
        suggested = round(suggested, 2)

        # 报价区间
        price_range = {
            "min": round(suggested * 0.92, 2),
            "max": round(suggested * 1.08, 2),
        }

        # 交期估算
        if capacity_ratio > 0.8:
            delivery_estimate = "7-10天"
        elif capacity_ratio > 0.5:
            delivery_estimate = "10-15天"
        else:
            delivery_estimate = "15-30天"

        # 产能是否充足
        capacity_available = capacity_ratio < 0.9

        # 报价依据
        basis_parts = []
        if price_data.get("is_cold_start"):
            basis_parts.append("参考行业均价")
        else:
            basis_parts.append("基于市场实时报价")
        basis_parts.append(f"供应商信用调整(+{(credit_premium-1)*100:+.0f}%)")
        basis_parts.append(f"产能状态调整(+{(capacity_premium-1)*100:+.0f}%)")
        if quantity and quantity >= 100:
            basis_parts.append(f"批量折扣(-{(1-quantity_discount)*100:.0f}%)")

        return {
            "suggested_price": suggested,
            "price_range": price_range,
            "delivery_estimate": delivery_estimate,
            "basis": " | ".join(basis_parts),
            "capacity_available": capacity_available,
            "median_price": median_price,
            "credit_score": credit_score,
            "capacity_ratio": round(capacity_ratio * 100, 1),
        }

    def apply_ai_suggestion(
        self,
        quote_id: int,
        suggested_price: float,
        price_basis: str,
        delivery_estimate: str,
    ) -> tuple[bool, str]:
        """将AI报价建议应用到意向报价"""
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return False, "意向报价不存在"

        quote.ai_suggested_price = suggested_price
        quote.ai_price_basis = price_basis
        quote.ai_delivery_estimate = delivery_estimate
        quote.updated_at = datetime.utcnow()
        db.session.commit()
        return True, ""

    # ── 名片交换检查 ────────────────────────────────────────────────────────

    def can_exchange_card(self, quote_id: int) -> tuple[bool, str]:
        """
        检查是否可以交换名片。

        条件：意向报价已双方确认（accepted）
        """
        quote = IntentQuote.query.get(quote_id)
        if not quote:
            return False, "意向报价不存在"

        if quote.status != "accepted":
            return False, f"意向报价状态为 {quote.status}，需先被供应商接受"

        if not (quote.buyer_confirmed and quote.seller_confirmed):
            return False, "双方尚未完成确认"

        return True, ""

    def get_card_exchange_eligible_quotes(
        self,
        buyer_id: int,
        seller_id: int,
    ) -> list[IntentQuote]:
        """获取可交换名片的所有意向报价"""
        return IntentQuote.query.filter(
            IntentQuote.buyer_id == buyer_id,
            IntentQuote.seller_id == seller_id,
            IntentQuote.status == "accepted",
            IntentQuote.buyer_confirmed == True,
            IntentQuote.seller_confirmed == True,
        ).all()

    # ── 辅助方法 ────────────────────────────────────────────────────────────

    def _serialize_quote(
        self,
        quote: IntentQuote,
        current_user_id: int,
    ) -> dict:
        """序列化意向报价为API响应格式"""
        buyer = Enterprise.query.get(quote.buyer_id)
        seller = Enterprise.query.get(quote.seller_id)

        is_buyer = current_user_id == quote.buyer_id

        return {
            "id": quote.id,
            "chat_id": quote.chat_id,
            "buyer_id": quote.buyer_id,
            "buyer_name": buyer.name if buyer else "未知",
            "seller_id": quote.seller_id,
            "seller_name": seller.name if seller else "未知",
            "product_name": quote.product_name,
            "quantity": quote.quantity,
            "unit": quote.unit or "件",
            "target_price": quote.target_price,
            "budget_range": quote.budget_range,
            "ai_suggested_price": quote.ai_suggested_price,
            "ai_price_basis": quote.ai_price_basis,
            "ai_delivery_estimate": quote.ai_delivery_estimate,
            "status": quote.status,
            "buyer_confirmed": quote.buyer_confirmed,
            "seller_confirmed": quote.seller_confirmed,
            "seller_reply_price": quote.seller_reply_price,
            "seller_reply_notes": quote.seller_reply_notes,
            "is_buyer": is_buyer,
            "created_at": quote.created_at.isoformat() if quote.created_at else None,
            "expires_at": quote.expires_at.isoformat() if quote.expires_at else None,
        }

    def _send_system_message(
        self,
        chat_id: int,
        content: str,
        event: str,
        metadata: dict,
    ) -> None:
        """发送系统消息到询价会话"""
        msg = ChatMessage(
            chat_id=chat_id,
            sender_id=None,
            content=content,
            message_type="system",
            msg_metadata={"event": event, **metadata},
        )
        db.session.add(msg)
        db.session.commit()

    def _build_quote_sent_message(self, quote: IntentQuote) -> str:
        """构建意向报价发送的系统消息内容"""
        buyer = Enterprise.query.get(quote.buyer_id)
        buyer_name = buyer.name if buyer else "某采购商"
        
        price_info = ""
        if quote.ai_suggested_price:
            price_info = f"，AI建议价 ¥{quote.ai_suggested_price}"
        
        return (
            f"【{buyer_name}】发起了意向报价：\n"
            f"产品：{quote.product_name}\n"
            f"数量：{quote.quantity or '待定'} {quote.unit or '件'}\n"
            f"目标价：¥{quote.target_price or '待定'}{price_info}\n"
            f"请及时查看并回复"
        )


# ── 模块级单例 ────────────────────────────────────────────────────────────
intent_quote_service = IntentQuoteService()

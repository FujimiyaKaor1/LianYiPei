"""
询价会话服务层（InquiryChat Service）
==========================================

职责：
1. 创建/获取询价会话（create_or_get_chat）
2. 发送聊天消息（send_message）
3. 获取聊天历史，含匿名脱敏（get_chat_history）
4. 切换采购/销售模式（switch_mode）
5. 创建/获取 MatchRecord（get_or_create_match_record）
6. 更新 MatchRecord 状态（update_match_status）
7. 计算 AI 商机评估数据（get_business_insights）
8. 提交正式结构化报价（submit_formal_quote）

关联需求：4（信用分卡点）、15（匿名逻辑）、16（价格指数触发）

使用方式：
    from app.services.inquiry_chat_service import InquiryChatService
    svc = InquiryChatService()
    chat = svc.create_or_get_chat(buyer_id, seller_id, match_record_id)
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from app import db
from app.models import ChatMessage, Enterprise, InquiryChat, MatchRecord, Quote
from app.services.credit_engine import CreditEngine, can_submit_quote, increment_quote_count


class InquiryChatService:
    """询价会话业务服务"""

    # ── 会话管理 ────────────────────────────────────────────────────────────

    def create_or_get_chat(
        self,
        buyer_id: int,
        seller_id: int,
        match_record_id: int,
        is_anonymous: bool = False,
    ) -> tuple[InquiryChat, bool]:
        """
        创建或获取已有的询价会话。

        同一 buyer+seller+match_record 组合只创建一个会话。
        返回 (会话, 是否新创建)。
        """
        existing = InquiryChat.query.filter_by(
            buyer_id=buyer_id,
            seller_id=seller_id,
            match_record_id=match_record_id,
        ).first()

        if existing:
            return existing, False

        chat = InquiryChat(
            buyer_id=buyer_id,
            seller_id=seller_id,
            match_record_id=match_record_id,
            is_anonymous=is_anonymous,
            mode="procurement",
            status="active",
        )
        db.session.add(chat)
        db.session.flush()
        return chat, True

    def get_chat_by_id(self, chat_id: int) -> InquiryChat | None:
        """根据 ID 获取会话"""
        return InquiryChat.query.get(chat_id)

    def get_chat_list(
        self,
        enterprise_id: int,
        role: str = "buyer",
        status: str | None = None,
        limit: int = 50,
    ) -> list[InquiryChat]:
        """
        获取企业的会话列表。

        role: "buyer" → 该企业作为买方的会话
              "seller" → 该企业作为卖方的会话
        """
        query = InquiryChat.query
        if role == "buyer":
            query = query.filter(InquiryChat.buyer_id == enterprise_id)
        else:
            query = query.filter(InquiryChat.seller_id == enterprise_id)

        if status:
            query = query.filter(InquiryChat.status == status)

        return (
            query.order_by(InquiryChat.updated_at.desc())
            .limit(limit)
            .all()
        )

    def switch_mode(self, chat_id: int, new_mode: str) -> InquiryChat | None:
        """
        切换会话视角模式。
        new_mode: "procurement" | "sales"
        """
        chat = InquiryChat.query.get(chat_id)
        if not chat or new_mode not in ("procurement", "sales"):
            return None
        chat.mode = new_mode
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return chat

    def close_chat(self, chat_id: int) -> bool:
        """关闭会话"""
        chat = InquiryChat.query.get(chat_id)
        if not chat:
            return False
        chat.status = "closed"
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return True

    # ── 消息管理 ────────────────────────────────────────────────────────────

    def count_own_text_messages_since_last_peer(
        self,
        chat_id: int,
        user_id: int,
    ) -> int:
        """对方最后一条文字消息之后，当前用户已发送的文字条数（不含本条）。"""
        messages = (
            ChatMessage.query.filter_by(chat_id=chat_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        last_peer_idx = -1
        for i, m in enumerate(messages):
            if m.sender_id is None:
                continue
            if m.sender_id != user_id and m.message_type == "text":
                last_peer_idx = i
        n = 0
        for m in messages[last_peer_idx + 1 :]:
            if m.sender_id == user_id and m.message_type == "text":
                n += 1
        return n

    def can_send_text_message(self, chat_id: int, sender_id: int) -> tuple[bool, str]:
        """在对方回复前，每方最多连续发送 2 条文字消息。"""
        n = self.count_own_text_messages_since_last_peer(chat_id, sender_id)
        if n >= 2:
            return False, "对方未回复前，最多连续发送 2 条文字消息，请等待对方回复后再发"
        return True, ""

    def send_message(
        self,
        chat_id: int,
        sender_id: int | None,
        content: str,
        message_type: str = "text",
        msg_metadata: dict | None = None,
    ) -> ChatMessage | None:
        """
        发送聊天消息。

        sender_id 为 None 时表示系统消息。
        """
        chat = InquiryChat.query.get(chat_id)
        if not chat or chat.status == "closed":
            return None

        msg = ChatMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            content=content,
            message_type=message_type,
            msg_metadata=msg_metadata,
        )
        db.session.add(msg)

        # 更新会话最新时间
        chat.updated_at = datetime.utcnow()
        db.session.commit()
        return msg

    def get_chat_history(
        self,
        chat_id: int,
        current_user_id: int,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        获取聊天记录（按时间升序）。

        含匿名脱敏逻辑：
        - 若买方发起时设置了匿名（is_anonymous=True），
          则在卖方视角下将买方名称替换为「匿名上市车企」。
        """
        chat = InquiryChat.query.get(chat_id)
        if not chat:
            return []

        is_seller_view = (current_user_id == chat.seller_id)
        is_anonymous_inquiry = chat.is_anonymous

        messages = (
            ChatMessage.query.filter_by(chat_id=chat_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        result = []
        for msg in messages:
            sender_name = None
            if msg.sender_id:
                sender_ent = Enterprise.query.get(msg.sender_id)
                if sender_ent:
                    # 匿名脱敏：卖方视角下隐藏买方真实名称
                    if is_seller_view and is_anonymous_inquiry and msg.sender_id == chat.buyer_id:
                        sender_name = self._get_anonymous_buyer_label()
                    else:
                        sender_name = sender_ent.name
            else:
                sender_name = "系统"

            result.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "sender_name": sender_name,
                "is_mine": msg.sender_id == current_user_id,
                "content": msg.content,
                "message_type": msg.message_type,
                "msg_metadata": msg.msg_metadata,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            })

        return result

    def _get_anonymous_buyer_label(self) -> str:
        """生成随机的匿名买方标签（需求15）"""
        labels = [
            "匿名上市车企",
            "匿名采购商",
            "某大型需求方",
            "匿名企业客户",
        ]
        return labels[datetime.utcnow().second % len(labels)]

    def get_latest_message(self, chat_id: int) -> ChatMessage | None:
        """获取会话最新一条消息"""
        return (
            ChatMessage.query.filter_by(chat_id=chat_id)
            .order_by(ChatMessage.created_at.desc())
            .first()
        )

    # ── MatchRecord 管理 ─────────────────────────────────────────────────────

    def get_or_create_match_record(
        self,
        buyer_id: int,
        seller_id: int,
        product_name: str,
        match_score: float | None = None,
        dim_scores: dict | None = None,
        match_feedback_id: int | None = None,
    ) -> MatchRecord:
        """创建或获取已有的匹配记录"""
        existing = MatchRecord.query.filter_by(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=product_name,
        ).first()

        if existing:
            if match_score is not None:
                existing.match_score = match_score
            if dim_scores is not None:
                existing.dim_scores = dim_scores
            db.session.commit()
            return existing

        session_id = hashlib.md5(
            f"{buyer_id}-{seller_id}-{product_name}".encode()
        ).hexdigest()[:16]

        record = MatchRecord(
            buyer_id=buyer_id,
            seller_id=seller_id,
            product_name=product_name,
            match_score=match_score,
            dim_scores=dim_scores,
            match_feedback_id=match_feedback_id,
            status="matched",
            session_id=session_id,
        )
        db.session.add(record)
        db.session.flush()
        return record

    def update_match_status(self, match_record_id: int, new_status: str) -> bool:
        """
        更新匹配记录状态。
        状态流转：matched → inquiry_sent → inquiry_accepted → quoted → contracted
        """
        valid_statuses = {
            "matched", "inquiry_sent", "inquiry_accepted",
            "quoted", "quote_acknowledged", "contracted",
        }
        if new_status not in valid_statuses:
            return False

        record = MatchRecord.query.get(match_record_id)
        if not record:
            return False

        record.status = new_status
        record.updated_at = datetime.utcnow()
        db.session.commit()
        return True

    def get_match_record_by_id(self, match_record_id: int) -> MatchRecord | None:
        """根据 ID 获取 MatchRecord"""
        return MatchRecord.query.get(match_record_id)

    # ── 商机评估 ─────────────────────────────────────────────────────────────

    def get_business_insights(
        self,
        match_record_id: int,
        current_enterprise_id: int,
    ) -> dict:
        """
        计算 AI 商机评估数据。

        返回字段：
          - match_score: 匹配度（%，来自 MatchRecord）
          - profit_rate: 预计利润率（%，基于供需类型估算）
          - risk_level: 客户风险评估（低/中/高）
          - risk_detail: 风险描述
          - credit_score: 对方信用分
          - level: 信用等级（AAA/AA+/A/一般）
        """
        record = MatchRecord.query.get(match_record_id)
        if not record:
            return {
                "match_score": 0,
                "profit_rate": 0,
                "risk_level": "未知",
                "risk_detail": "匹配记录不存在",
                "credit_score": 0,
                "level": "未知",
            }

        # 判断当前企业是买方还是卖方，对方即为交易对手
        if current_enterprise_id == record.buyer_id:
            counterparty = Enterprise.query.get(record.seller_id)
        else:
            counterparty = Enterprise.query.get(record.buyer_id)

        if not counterparty:
            raw_ms = float(record.match_score or 0)
            ms_early = min(100, int(round(raw_ms * 100))) if raw_ms <= 1.0001 else min(100, int(round(raw_ms)))
            return {
                "match_score": ms_early,
                "profit_rate": 0,
                "risk_level": "未知",
                "risk_detail": "对方企业信息不存在",
                "credit_score": 0,
                "level": "未知",
            }

        credit_score = float(counterparty.credit_score or 60.0)
        level = self._score_to_level(credit_score)
        risk_level, risk_detail = self._score_to_risk(credit_score)

        raw_ms = float(record.match_score or 0)
        ms_unit = raw_ms if raw_ms <= 1.0001 else min(raw_ms / 100.0, 1.0)

        # 利润率估算：基于供需方向和匹配质量
        base_profit = 10.0 + min(ms_unit * 5, 10)
        profit_rate = round(base_profit, 1)

        # 数据库存 0~1 或 0~100 均兼容，展示统一为 0~100
        if raw_ms > 1.0001:
            match_pct = min(100, int(round(raw_ms)))
        else:
            match_pct = min(100, int(round(raw_ms * 100)))

        return {
            "match_score": match_pct,
            "profit_rate": profit_rate,
            "risk_level": risk_level,
            "risk_detail": risk_detail,
            "credit_score": credit_score,
            "level": level,
        }

    @staticmethod
    def _score_to_level(score: float) -> str:
        """信用分 → 信用等级"""
        if score >= 90:
            return "AAA"
        elif score >= 85:
            return "AA+"
        elif score >= 80:
            return "AA"
        elif score >= 70:
            return "A"
        elif score >= 60:
            return "一般"
        else:
            return "待提升"

    @staticmethod
    def _score_to_risk(score: float) -> tuple[str, str]:
        """信用分 → 风险等级 + 描述"""
        if score >= 85:
            return "低风险", "信用表现优秀，违约风险极低"
        elif score >= 75:
            return "中风险", "信用表现良好，建议适度关注账期"
        elif score >= 70:
            return "中风险", "信用表现一般，建议关注履约情况"
        else:
            return "高风险", "信用表现偏弱，建议设置更严格的履约条件"

    # ── 正式报价 ─────────────────────────────────────────────────────────────

    def submit_formal_quote(
        self,
        chat_id: int,
        sender_id: int,
        price: float,
        quantity: int,
        unit: str,
        delivery_days: int,
        remarks: str,
    ) -> tuple[Quote | None, str]:
        """
        提交正式结构化报价。

        1. 校验发送方信用分权益（can_submit_quote）
        2. 写入 Quote 表（触发 QuotePoolManager 逻辑）
        3. 发送系统消息通知对方
        4. 更新 MatchRecord 状态为 quoted
        5. 更新 InquiryChat 状态为 quoted

        返回 (Quote对象, 错误信息)；错误时 Quote 为 None。
        """
        chat = InquiryChat.query.get(chat_id)
        if not chat:
            return None, "会话不存在"

        # 1. 信用分权益校验（需求4）
        allowed, reason = can_submit_quote(sender_id)
        if not allowed:
            return None, reason

        if price <= 0:
            return None, "报价金额必须大于0"

        record = MatchRecord.query.get(chat.match_record_id)

        # 2. 写入 Quote 表
        from app.services.quote_pool import QuotePoolManager

        qpm = QuotePoolManager()
        quote, q_error = qpm.add_quote(
            inquiry_id=chat.match_record_id,
            supplier_id=sender_id,
            product_name=record.product_name if record else "未知产品",
            price=price,
            quantity=quantity,
            unit=unit,
            delivery_days=delivery_days,
            remarks=remarks,
        )

        if not quote:
            return None, q_error

        # 3. 发送系统消息（InquiryChat 内聊天消息）
        sender_ent = Enterprise.query.get(sender_id)
        sender_name = sender_ent.name if sender_ent else "某企业"

        total_price = price * quantity
        sys_content = (
            f"【{sender_name}】提交了正式报价：\n"
            f"单价 {price:.2f} 元/{unit}，数量 {quantity} {unit}\n"
            f"合计约 {total_price:.2f} 元，交期 {delivery_days} 天"
        )
        self.send_message(
            chat_id=chat_id,
            sender_id=None,
            content=sys_content,
            message_type="system",
            msg_metadata={
                "quote_id": quote.id,
                "price": price,
                "quantity": quantity,
                "unit": unit,
                "total_price": total_price,
                "delivery_days": delivery_days,
            },
        )

        # 4. 通知买方：收件方为采购方，归入「采购模式」收件箱
        if chat.buyer_id != sender_id:
            buyer_ent = Enterprise.query.get(chat.buyer_id)
            if buyer_ent:
                from app.services.message_service import MessageService
                product_label = record.product_name if record else "精密零部件"
                MessageService.create_message(
                    recipient_id=chat.buyer_id,
                    message_type="inquiry",
                    title=f"【{sender_name}】提交了报价：{product_label}",
                    content=(
                        f"供应商 {sender_name} 已提交正式报价：\n"
                        f"单价 {price:.2f} 元/{unit}，数量 {quantity} {unit}，"
                        f"交期 {delivery_days} 天\n合计约 {total_price:.2f} 元"
                    ),
                    link_url=f"/sales-console?inquiry_id={chat.match_record_id}&buyer_id={chat.buyer_id}",
                    priority="high",
                    mode="procurement",
                )

        # 5. 更新 MatchRecord 状态
        if record and record.status not in ("quoted", "contracted"):
            record.status = "quoted"
            record.updated_at = datetime.utcnow()

        # 6. 更新 InquiryChat 状态
        if chat.status != "quoted":
            chat.status = "quoted"
            chat.updated_at = datetime.utcnow()

        db.session.commit()
        return quote, ""

    # ── 辅助：序列化 ─────────────────────────────────────────────────────────

    def serialize_chat(
        self,
        chat: InquiryChat,
        current_user_id: int,
    ) -> dict:
        """
        将 InquiryChat 序列化为 API 返回格式（含最新消息预览和匿名脱敏）。
        """
        is_seller_view = (current_user_id == chat.seller_id)
        latest_msg = self.get_latest_message(chat.id)

        # 对方名称（匿名处理）
        if is_seller_view:
            counterparty_ent = Enterprise.query.get(chat.buyer_id)
            counterparty_name = (
                self._get_anonymous_buyer_label()
                if chat.is_anonymous and counterparty_ent
                else (counterparty_ent.name if counterparty_ent else "未知")
            )
        else:
            counterparty_ent = Enterprise.query.get(chat.seller_id)
            counterparty_name = counterparty_ent.name if counterparty_ent else "未知"

        # 最新消息预览
        latest_content = None
        if latest_msg:
            if latest_msg.message_type == "quote_proposal":
                meta = latest_msg.msg_metadata or {}
                latest_content = (
                    f"报价：{meta.get('price', '?')} 元 × {meta.get('quantity', '?')}"
                )
            elif latest_msg.message_type == "system":
                latest_content = latest_msg.content[:50]
            elif latest_msg.message_type == "text":
                latest_content = latest_msg.content[:60]

        # 读取匹配记录
        record = MatchRecord.query.get(chat.match_record_id)

        return {
            "id": chat.id,
            "match_record_id": chat.match_record_id,
            "buyer_id": chat.buyer_id,
            "seller_id": chat.seller_id,
            "mode": chat.mode,
            "is_anonymous": chat.is_anonymous,
            "status": chat.status,
            "match_record_status": record.status if record else None,
            "counterparty_name": counterparty_name,
            "product_name": record.product_name if record else None,
            "match_score": record.match_score if record else None,
            "latest_message": latest_content,
            "latest_message_at": (
                latest_msg.created_at.isoformat() if latest_msg and latest_msg.created_at else None
            ),
            "created_at": chat.created_at.isoformat() if chat.created_at else None,
            "updated_at": chat.updated_at.isoformat() if chat.updated_at else None,
        }

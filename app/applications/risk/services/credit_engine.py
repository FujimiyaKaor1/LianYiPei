"""
信用分计算引擎
- 多维度加权计算（履约、活跃度、数据完整度、举报记录）
- 信用分权益体系（报价限制、匹配权重、融资推荐）
- 变更记录与历史查询
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from config import DEFAULT_CREDIT_RULES

from app import db
from app.models import Enterprise, Inquiry, Message, Transaction
from app.services.credit_score_events import append_credit_event

SCORE_MIN = 0.0
SCORE_MAX = 100.0


class CreditEngine:
    """信用引擎单例：封装评分、权益、历史、配额与批处理逻辑。"""

    _instance: "CreditEngine | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @staticmethod
    def _clamp(score: float) -> float:
        return max(SCORE_MIN, min(SCORE_MAX, score))

    @staticmethod
    def _get_rule_value(rule_type: str) -> float:
        """从 config.DEFAULT_CREDIT_RULES 读取规则值。"""
        return float(DEFAULT_CREDIT_RULES.get(rule_type, 0.0))

    @staticmethod
    def _tx_verified(tx: Transaction) -> bool:
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if info.get("verified") is True:
            return True
        return (tx.fulfillment_status or "") in ("verified", "completed")

    @staticmethod
    def _tx_on_time(tx: Transaction) -> Optional[bool]:
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        if "on_time" in info:
            return bool(info.get("on_time"))
        return None

    @staticmethod
    def _tx_quality(tx: Transaction) -> Optional[int]:
        info = tx.invoice_info if isinstance(tx.invoice_info, dict) else {}
        q = info.get("quality_rating")
        return int(q) if q is not None else None

    def calculate_credit_score(self, enterprise_id: int) -> float:
        """
        重新计算企业信用分（不写库，仅返回计算值）。
        基础分60 + 履约维度(40%) + 活跃度(25%) + 数据完整度(20%) + 举报记录(15%)
        """
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return 60.0

        base = 60.0

        fulfillment_score = self._calc_fulfillment_score(enterprise_id)
        activity_score = self._calc_activity_score(enterprise_id)
        data_score = self._calc_data_completeness_score(ent)
        report_score = self._calc_report_score(enterprise_id)
        consecutive_bonus = self._calc_consecutive_bonus(enterprise_id)

        total = (
            base
            + fulfillment_score * 0.40
            + activity_score * 0.25
            + data_score * 0.20
            + report_score * 0.15
            + consecutive_bonus
        )
        return self._clamp(total)

    def _calc_fulfillment_score(self, enterprise_id: int) -> float:
        """履约得分 0-40（基于 Transaction + invoice_info）"""
        cutoff = datetime.utcnow() - timedelta(days=365)
        rows = (
            Transaction.query.filter(
                Transaction.seller_id == enterprise_id,
                Transaction.created_at >= cutoff,
            )
            .order_by(Transaction.created_at.desc())
            .all()
        )
        records = [r for r in rows if self._tx_verified(r)]
        if not records:
            return 0.0
        on_time_vals = [self._tx_on_time(r) for r in records]
        on_time = sum(1 for v in on_time_vals if v is True)
        unknown = sum(1 for v in on_time_vals if v is None)
        denom = len(records) - unknown
        rate = (on_time / denom) if denom else 0.0
        score = rate * 40.0
        rated = [r for r in records if self._tx_quality(r) is not None]
        if rated:
            avg_q = sum(self._tx_quality(r) for r in rated) / len(rated)
            score += (avg_q - 3) * 2
        return max(0.0, score)

    @staticmethod
    def _calc_activity_score(enterprise_id: int) -> float:
        """活跃度得分 0-25（最近30天：挂牌/询价 + 买方询盘）"""
        cutoff = datetime.utcnow() - timedelta(days=30)
        poster_count = Inquiry.query.filter(
            Inquiry.poster_id == enterprise_id,
            Inquiry.created_at >= cutoff,
        ).count()
        buyer_count = Inquiry.query.filter(
            Inquiry.buyer_id == enterprise_id,
            Inquiry.created_at >= cutoff,
        ).count()
        score = min(25.0, poster_count * 2.0 + buyer_count * 1.0)
        return score

    @staticmethod
    def _calc_data_completeness_score(ent: Enterprise) -> float:
        """数据完整度得分 0-20"""
        score = 0.0
        if ent.address:
            score += 3
        if ent.contact:
            score += 2
        if ent.phone:
            score += 2
        if ent.industry_code:
            score += 3
        if ent.tech_keywords:
            score += 3
        if ent.business_scope:
            score += 2
        auth = ent.data_auth if isinstance(ent.data_auth, dict) else {}
        auth_count = sum(
            1 for v in auth.values() if isinstance(v, dict) and v.get("authorized")
        )
        score += min(5.0, float(auth_count) * 5.0)
        return min(20.0, score)

    @staticmethod
    def _calc_report_score(enterprise_id: int) -> float:
        """举报记录得分 0-15（被举报记录存于 Enterprise.extras['reports_received']）"""
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return 0.0
        ex = ent.extras if isinstance(ent.extras, dict) else {}
        received = ex.get("reports_received")
        if not isinstance(received, list):
            return 15.0
        verified_reports = sum(
            1
            for r in received
            if isinstance(r, dict) and r.get("status") == "verified_true"
        )
        score = 15.0 - verified_reports * 5.0
        return max(0.0, score)

    def _calc_consecutive_bonus(self, enterprise_id: int) -> float:
        records = (
            Transaction.query.filter(
                Transaction.seller_id == enterprise_id,
            )
            .order_by(Transaction.created_at.desc())
            .limit(10)
            .all()
        )
        records = [r for r in records if self._tx_verified(r)]
        consecutive = 0
        for r in records:
            ot = self._tx_on_time(r)
            if ot is True or (ot is None and r.fulfillment_status == "verified"):
                consecutive += 1
            else:
                break
        bonus = (consecutive // 3) * 5.0
        return min(15.0, bonus)

    def update_credit_score(
        self,
        enterprise_id: int,
        change_type: str,
        change_value: Optional[float] = None,
        reason: str = "",
    ) -> dict:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return {}

        if change_value is None:
            change_value = self._get_rule_value(change_type)

        old_score = float(ent.credit_score or 60.0)
        new_score = self._clamp(old_score + change_value)

        ent.credit_score = new_score
        ent.last_data_update = datetime.utcnow()

        append_credit_event(
            ent,
            old_score=old_score,
            new_score=new_score,
            change_value=change_value,
            change_type=change_type,
            reason=reason or change_type,
        )

        if abs(change_value) >= 10:
            self._send_credit_message(ent, change_value, reason)

        db.session.commit()
        return {
            "old_score": old_score,
            "new_score": new_score,
            "change_value": change_value,
        }

    @staticmethod
    def _send_credit_message(ent: Enterprise, change_value: float, reason: str):
        direction = "提升" if change_value > 0 else "下降"
        msg = Message(
            recipient_id=ent.id,
            message_type="credit",
            title=f"信用分{direction}{abs(change_value):.0f}分",
            content=(
                f"您的信用分{direction}了{abs(change_value):.0f}分，原因：{reason}。"
                f"当前信用分：{ent.credit_score:.1f}分。"
            ),
            link_url="/enterprise/profile",
            priority="high" if abs(change_value) >= 20 else "normal",
        )
        db.session.add(msg)

    @staticmethod
    def check_credit_privileges(enterprise_id: int) -> dict:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return {}

        score = float(ent.credit_score or 60.0)

        if score >= 90:
            daily_limit = "unlimited"
            weight_boost = 1.20
            financing = True
            preferred = True
        elif score >= 75:
            daily_limit = 20
            weight_boost = 1.10
            financing = False
            preferred = False
        elif score >= 70:
            daily_limit = "unlimited"
            weight_boost = 1.0
            financing = False
            preferred = False
        else:
            daily_limit = 3
            weight_boost = 0.85
            financing = False
            preferred = False

        return {
            "credit_score": score,
            "daily_quote_limit": daily_limit,
            "matching_weight_boost": weight_boost,
            "financing_priority": financing,
            "preferred_supplier": preferred,
        }

    def can_submit_quote(self, enterprise_id: int) -> tuple[bool, str]:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return False, "企业不存在"

        today = date.today()
        if ent.last_quote_reset_date != today:
            ent.daily_quote_count = 0
            ent.last_quote_reset_date = today
            db.session.commit()

        privileges = self.check_credit_privileges(enterprise_id)
        limit = privileges.get("daily_quote_limit", 3)

        if limit == "unlimited":
            return True, ""

        if ent.daily_quote_count >= limit:
            return (
                False,
                f"今日报价次数已达上限（{limit}次），提升信用分可解锁更多次数",
            )

        return True, ""

    def get_enterprise_credit_level(self, enterprise_id: int) -> dict:
        """返回企业信用分、等级和风险等级的聚合数据。"""
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return {
                "credit_score": 0,
                "level": "未知",
                "risk_level": "未知",
                "risk_detail": "企业不存在",
            }
        score = float(ent.credit_score or 60.0)
        if score >= 90:
            level, risk_level, risk_detail = "AAA", "低风险", "信用表现优秀，违约风险极低"
        elif score >= 85:
            level, risk_level, risk_detail = "AA+", "低风险", "信用表现优秀，违约风险极低"
        elif score >= 80:
            level, risk_level, risk_detail = "AA", "中风险", "信用表现良好，建议适度关注账期"
        elif score >= 75:
            level, risk_level, risk_detail = "A", "中风险", "信用表现良好，建议适度关注账期"
        elif score >= 70:
            level, risk_level, risk_detail = "A", "中风险", "信用表现一般，建议关注履约情况"
        else:
            level, risk_level, risk_detail = "一般", "高风险", "信用表现偏弱，建议设置更严格的履约条件"
        return {
            "credit_score": score,
            "level": level,
            "risk_level": risk_level,
            "risk_detail": risk_detail,
        }

    @staticmethod
    def increment_quote_count(enterprise_id: int):
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return
        today = date.today()
        if ent.last_quote_reset_date != today:
            ent.daily_quote_count = 0
            ent.last_quote_reset_date = today
        ent.daily_quote_count = (ent.daily_quote_count or 0) + 1
        db.session.commit()

    @staticmethod
    def get_credit_history(enterprise_id: int, limit: int = 10) -> list:
        from app.services.credit_score_events import (
            credit_events_newest_first,
            event_to_api_dict,
        )

        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return []
        rows = credit_events_newest_first(ent)[:limit]
        return [event_to_api_dict(e) for e in rows]

    def batch_recalculate_all(self):
        enterprises = Enterprise.query.filter_by(role="enterprise").all()
        updated = 0
        for ent in enterprises:
            new_score = self.calculate_credit_score(ent.id)
            old_score = float(ent.credit_score or 60.0)
            if abs(new_score - old_score) >= 0.5:
                ent.credit_score = new_score
                append_credit_event(
                    ent,
                    old_score=old_score,
                    new_score=new_score,
                    change_value=new_score - old_score,
                    change_type="batch_recalculate",
                    reason="系统每日批量重算",
                )
                updated += 1
        db.session.commit()
        return updated

    @staticmethod
    def reset_daily_quote_counts():
        today = date.today()
        Enterprise.query.filter(Enterprise.last_quote_reset_date != today).update(
            {"daily_quote_count": 0, "last_quote_reset_date": today},
            synchronize_session=False,
        )
        db.session.commit()


# 单例实例（全局复用，避免重复实例化）
_credit_engine_singleton = CreditEngine()

# 兼容旧调用方式：保留原函数名导出
calculate_credit_score = _credit_engine_singleton.calculate_credit_score
update_credit_score = _credit_engine_singleton.update_credit_score
get_credit_history = _credit_engine_singleton.get_credit_history
check_credit_privileges = _credit_engine_singleton.check_credit_privileges
can_submit_quote = _credit_engine_singleton.can_submit_quote
get_enterprise_credit_level = _credit_engine_singleton.get_enterprise_credit_level
increment_quote_count = _credit_engine_singleton.increment_quote_count
batch_recalculate_all = _credit_engine_singleton.batch_recalculate_all
reset_daily_quote_counts = _credit_engine_singleton.reset_daily_quote_counts

"""
AI 企业画像服务
======================

职责：
1. 生成企业基础画像（不含敏感信息）
2. AI商机洞察消息生成
3. 匹配推荐理由生成

关联需求：AI商机洞察消息、意向报价前置
"""
from __future__ import annotations

import logging
from typing import Optional

from app.models import Enterprise, MatchRecord

logger = logging.getLogger(__name__)


class DeepSeekProfileService:
    """AI 企业画像服务（保留历史类名以兼容旧导入路径）。"""

    # 允许公开的企业画像字段
    PUBLIC_PROFILE_FIELDS = [
        "name",
        "industry_code",
        "province",
        "city",
        "business_scope",
        "capacity",
        "max_capacity",
        "credit_score",
        "patent_count",
        "is_green_factory",
        "carbon_emission_level",
        "clean_energy_usage",
        "registered_capital",
        "green_certification",
    ]

    # 敏感字段（不包含在画像中）
    SENSITIVE_FIELDS = [
        "contact",      # 联系人
        "phone",        # 联系电话
        "address",      # 详细地址
        "legal_person", # 法人代表（虽然当前模型中没有此字段，但保留扩展）
    ]

    # ── 企业画像生成 ────────────────────────────────────────────────────────

    def generate_public_profile(
        self,
        enterprise_id: int,
    ) -> dict | None:
        """
        生成公开企业画像（不含敏感信息）。

        返回格式：
        {
            "enterprise_id": int,
            "name": str,
            "industry_code": str,
            "province": str,
            "city": str,
            "main_products": str,
            "capacity_status": str,
            "capacity_usage": str,
            "credit_score": float,
            "credit_level": str,
            "green_level": str,
            "patent_count": int,
            "cooperation_risk": str,
            "registered_capital": str,
        }
        """
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return None

        # 基础信息
        profile = {
            "enterprise_id": ent.id,
            "name": ent.name,
            "industry_code": ent.industry_code or "",
            "province": ent.province or "",
            "city": ent.city or "",
            "main_products": self._truncate_text(ent.business_scope or "未填写", 100),
        }

        # 产能状态：current_orders 是当前负载，max_capacity 是能力上限。
        # 缺少任一事实时不能用默认值伪造实时利用率。
        current_orders = ent.current_orders
        max_cap = ent.max_capacity
        if max_cap is None or max_cap <= 0 or current_orders is None:
            usage_ratio = None
            capacity_status = "未公开"
            capacity_usage = "未公开"
        else:
            usage_ratio = min(100.0, max(0.0, float(current_orders) / float(max_cap) * 100))
            if usage_ratio >= 90:
                capacity_status = "产能紧张"
            elif usage_ratio >= 70:
                capacity_status = "产能正常"
            else:
                capacity_status = "产能充裕"
            capacity_usage = f"{usage_ratio:.0f}%"

        profile["capacity_status"] = capacity_status
        profile["capacity_usage"] = capacity_usage

        # 信用评分
        credit_score = float(ent.credit_score) if ent.credit_score is not None else None
        profile["credit_score"] = credit_score
        profile["credit_level"] = self._score_to_level(credit_score) if credit_score is not None else "未公开"

        # 绿色等级
        if ent.is_green_factory:
            profile["green_level"] = "A级" if ent.carbon_emission_level in ("A", "a") else "B级"
        else:
            profile["green_level"] = "未认证"

        # 专利数量
        profile["patent_count"] = ent.patent_count or 0

        # 合作风险评估
        profile["cooperation_risk"] = self._assess_risk(credit_score, usage_ratio or 0.0) if credit_score is not None else "未知"

        # 注册资本
        reg_cap = ent.registered_capital
        if reg_cap:
            if reg_cap >= 10000:
                profile["registered_capital"] = f"{reg_cap/10000:.1f}亿元"
            else:
                profile["registered_capital"] = f"{reg_cap:.0f}万元"
        else:
            profile["registered_capital"] = "未公示"

        return profile

    def generate_match_recommendation(
        self,
        enterprise_id: int,
        product_name: str,
        match_score: Optional[float] = None,
    ) -> str:
        """
        生成AI匹配推荐理由。

        用于在匹配结果中展示推荐理由。
        """
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return "未找到相关企业信息"

        reasons = []

        # 产能匹配
        if ent.capacity and ent.max_capacity:
            usage = ent.capacity / ent.max_capacity
            if usage < 0.7:
                reasons.append("产能充裕，可快速响应")
            elif usage < 0.9:
                reasons.append("产能正常，交期有保障")

        # 信用匹配
        credit = ent.credit_score
        if credit is not None and credit >= 85:
            reasons.append("信用优秀，合作风险低")
        elif credit is not None and credit >= 75:
            reasons.append("信用良好，值得信赖")

        # 绿色认证
        if ent.is_green_factory:
            reasons.append("绿色工厂，环保合规")

        # 专利技术
        patents = ent.patent_count or 0
        if patents >= 5:
            reasons.append(f"拥有{patents}项专利，技术实力强")
        elif patents >= 1:
            reasons.append(f"拥有{patents}项专利，有一定研发能力")

        # 地理位置
        if ent.province and ent.city:
            reasons.append(f"位于{ent.province}{ent.city}")

        # 匹配分
        if match_score:
            score_pct = match_score * 100 if match_score <= 1 else match_score
            if score_pct >= 85:
                reasons.append(f"综合匹配度{score_pct:.0f}%")

        if not reasons:
            reasons.append("综合评估合格")

        return " | ".join(reasons[:3])

    def generate_business_insight_message(
        self,
        enterprise_id: int,
        product_name: str,
        buyer_id: int,
    ) -> dict:
        """
        生成商机洞察消息内容。

        返回格式：
        {
            "type": "ai_business_insight",
            "enterprise_id": int,
            "enterprise_name": str,
            "insight_summary": str,
            "enterprise_profile": dict,
            "actions": {
                "generate_quote": {
                    "enabled": bool,
                    "label": str,
                    "description": str,
                }
            }
        }
        """
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return {
                "type": "ai_business_insight",
                "error": "企业信息不存在",
            }

        profile = self.generate_public_profile(enterprise_id)

        # 生成商机摘要
        insight_summary = self._generate_insight_text(
            product_name=product_name,
            capacity=ent.current_orders,
            max_cap=ent.max_capacity,
            credit_score=ent.credit_score,
            is_green=ent.is_green_factory,
        )

        # 产能信息
        capacity_info = ""
        if ent.current_orders is not None and ent.max_capacity:
            usage = min(100.0, max(0.0, ent.current_orders / ent.max_capacity * 100))
            capacity_info = f"当前产能利用率{int(usage)}%，"

        return {
            "type": "ai_business_insight",
            "generation_mode": "database_rules",
            "enterprise_id": enterprise_id,
            "enterprise_name": ent.name,
            "insight_summary": (
                f"已为您提取商机：{product_name}。"
                f"根据企业登记的产能字段分析：{capacity_info}"
                f"建议结合价格指数和供应商回执后报价。"
            ),
            "enterprise_profile": profile,
            "actions": {
                "generate_quote": {
                    "enabled": True,
                    "label": "立即生成",
                    "description": "一键生成意向报价单",
                }
            }
        }

    # ── 可解释规则洞察（不冒充云端模型调用） ────────────────────────────────

    def generate_ai_insight_text(
        self,
        product_name: str,
        capacity: Optional[int],
        max_cap: Optional[int],
        credit_score: Optional[float],
        is_green: bool,
    ) -> str:
        """
        根据已持久化的企业事实生成可解释文本；不会伪称已调用 DeepSeek。
        """
        return self._generate_insight_text(
            product_name=product_name,
            capacity=capacity,
            max_cap=max_cap,
            credit_score=credit_score,
            is_green=is_green,
        )

    # ── 辅助方法 ────────────────────────────────────────────────────────────

    @staticmethod
    def _generate_insight_text(
        product_name: str,
        capacity: Optional[int],
        max_cap: Optional[int],
        credit_score: Optional[float],
        is_green: bool,
    ) -> str:
        """生成商机洞察文本"""
        parts = []

        # 产能评估
        if capacity is not None and max_cap:
            usage = min(100.0, max(0.0, float(capacity) / float(max_cap) * 100))
            if usage >= 90:
                parts.append("当前产能紧张，可能需要排队等待")
            elif usage >= 70:
                parts.append("产能利用处于正常水平，可承接订单")
            else:
                parts.append("产能充裕，可快速响应您的需求")

        # 信用评估
        if credit_score is None:
            # Do not turn missing evidence into a negative or positive
            # credit judgment.
            score = None
        else:
            score = float(credit_score)
        if score is not None and score >= 85:
            parts.append("企业信用表现优秀，合作风险低")
        elif score is not None and score >= 75:
            parts.append("企业信用表现良好，合作较为可靠")
        elif score is not None:
            parts.append("建议关注企业履约情况")
        else:
            parts.append("企业信用分尚未公开，需结合履约记录评估")

        # 绿色认证
        if is_green:
            parts.append("该企业拥有绿色工厂认证，符合低碳采购要求")

        return "；".join(parts)

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
    def _assess_risk(credit_score: float, usage_ratio: float) -> str:
        """评估合作风险"""
        if credit_score >= 85 and usage_ratio < 85:
            return "低风险"
        elif credit_score >= 75 and usage_ratio < 90:
            return "较低风险"
        elif credit_score >= 70:
            return "中等风险"
        else:
            return "较高风险"

    @staticmethod
    def _truncate_text(text: str, max_len: int) -> str:
        """截断文本"""
        if len(text) <= max_len:
            return text
        return text[:max_len] + "..."


# ── 模块级单例 ────────────────────────────────────────────────────────────
deepseek_profile_service = DeepSeekProfileService()

"""
金融赋能：基于企业信用与匹配表现的链易贷额度测算与申请落库。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app import db
from app.models import Enterprise, MatchFeedback

# 合作银行展示名（按企业 id 稳定映射，体现「系统撮合」）
_PARTNER_BANK_PREFIXES = ('工商', '建设', '农业', '中国', '交通', '招商', '浦发', '兴业')

CREDIT_BUMP_ON_APPLY = 2.0
MAX_CREDIT_SCORE = 100.0


def _partner_bank_name(enterprise_id: int) -> str:
    return f'{_PARTNER_BANK_PREFIXES[enterprise_id % len(_PARTNER_BANK_PREFIXES)]}银行'


def _latest_match_score_for_buyer(enterprise_id: int) -> float:
    """取该企业作为采购方最近一次反馈中的综合匹配分（0–100）；无记录时用中性默认值。"""
    fb = (
        MatchFeedback.query.filter_by(buyer_id=enterprise_id)
        .filter(MatchFeedback.match_score.isnot(None))
        .order_by(MatchFeedback.created_at.desc())
        .first()
    )
    if fb is None or fb.match_score is None:
        return 75.0
    return float(fb.match_score)


def enterprise_has_green_factory_tag(ent: Enterprise) -> bool:
    """绿色工厂：布尔字段或绿色认证列表中含「绿色工厂」。"""
    if bool(getattr(ent, 'is_green_factory', False)):
        return True
    raw = getattr(ent, 'green_certification', None)
    if isinstance(raw, list):
        return any('绿色工厂' in str(x) for x in raw)
    if isinstance(raw, str) and '绿色工厂' in raw:
        return True
    return False


def calculate_loan_eligibility(enterprise_id: int) -> Optional[Dict[str, Any]]:
    """
    评估链易贷预授信额度（元）：
    LoanAmount = (credit_score × 1000) + (match_score × 2000)
    若企业具备「绿色工厂」标签，额度上浮 20%。
    """
    ent = Enterprise.query.get(enterprise_id)
    if ent is None:
        return None

    credit = float(ent.credit_score or 0.0)
    match_score = _latest_match_score_for_buyer(enterprise_id)
    base_yuan = credit * 1000.0 + match_score * 2000.0
    green = enterprise_has_green_factory_tag(ent)
    if green:
        base_yuan *= 1.2

    loan_yuan = round(base_yuan, 2)
    loan_wan = round(loan_yuan / 10000.0, 2)

    return {
        'eligible': True,
        'enterprise_id': enterprise_id,
        'credit_score': round(credit, 2),
        'match_score': round(match_score, 2),
        'is_green_factory': green,
        'loan_amount_yuan': loan_yuan,
        'loan_amount_wan': loan_wan,
        'loan_amount_wan_display': int(round(loan_wan)) if loan_wan >= 10 else round(loan_wan, 1),
        'bank_name': _partner_bank_name(enterprise_id),
        'product_name': '链易贷',
    }


def apply_order_financing(
    enterprise_id: int,
    bank_name: str,
    loan_amount_yuan: float,
    *,
    supplier_id: Optional[int] = None,
    product_name: str = '链易贷',
) -> Dict[str, Any]:
    """
    写入融资申请并上调企业信用分（金融活跃度正向反馈，上限 100）。
    """
    ent = Enterprise.query.get(enterprise_id)
    if ent is None:
        raise ValueError('企业不存在')

    ex = dict(ent.extras) if isinstance(ent.extras, dict) else {}
    apps = list(ex.get("financing_applications") or [])
    app_id = len(apps) + 1
    apps.append(
        {
            "id": app_id,
            "bank_name": bank_name.strip() or _partner_bank_name(enterprise_id),
            "product_name": product_name or "链易贷",
            "loan_amount_yuan": float(loan_amount_yuan),
            "supplier_id": supplier_id,
            "status": "submitted",
        }
    )
    ex["financing_applications"] = apps
    ent.extras = ex

    prev = float(ent.credit_score or 0.0)
    ent.credit_score = min(MAX_CREDIT_SCORE, round(prev + CREDIT_BUMP_ON_APPLY, 2))
    db.session.commit()

    return {
        "application_id": app_id,
        "credit_score_before": prev,
        "credit_score_after": float(ent.credit_score),
    }

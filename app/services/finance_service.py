"""
金融赋能：基于企业信用与匹配表现的链易贷内部测算；金融机构未接入时严格失败关闭。
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from app.models import Enterprise, MatchFeedback

def _latest_match_score_for_buyer(enterprise_id: int) -> Optional[float]:
    """取该企业作为采购方最近一次持久化反馈中的综合匹配分。"""
    fb = (
        MatchFeedback.query.filter_by(buyer_id=enterprise_id)
        .filter(MatchFeedback.match_score.isnot(None))
        .order_by(MatchFeedback.created_at.desc())
        .first()
    )
    if fb is None or fb.match_score is None:
        return None
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
    评估链易贷内部参考额度（元），不代表银行授信：
    LoanAmount = (credit_score × 1000) + (match_score × 2000)
    若企业具备「绿色工厂」标签，额度上浮 20%。
    """
    ent = Enterprise.query.get(enterprise_id)
    if ent is None:
        return None

    credit = float(ent.credit_score or 0.0)
    match_score = _latest_match_score_for_buyer(enterprise_id)
    if match_score is None:
        return {
            'eligible': False,
            'enterprise_id': enterprise_id,
            'credit_score': round(credit, 2),
            'match_score': None,
            'is_green_factory': enterprise_has_green_factory_tag(ent),
            'loan_amount_yuan': None,
            'loan_amount_wan': None,
            'loan_amount_wan_display': None,
            'bank_name': None,
            'product_name': '链易贷（未接入）',
            'reason': '没有已持久化的匹配反馈，无法进行内部测算；金融机构接口尚未接入',
        }
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
        'bank_name': None,
        'product_name': '链易贷（内部测算，未接入金融机构）',
        'reason': '当前仅支持内部规则测算，未接入金融机构，不代表授信或放款承诺',
    }


def apply_order_financing(
    enterprise_id: int,
    bank_name: str,
    loan_amount_yuan: float,
    *,
    supplier_id: Optional[int] = None,
    product_name: str = '链易贷',
) -> Dict[str, Any]:
    raise RuntimeError('金融机构接口未接入，不能提交融资申请或修改信用分')

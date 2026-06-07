"""
时序预测 - 供需趋势预测
使用 statsmodels 实现 ARIMA/指数平滑等 SOTA 时序模型
（可扩展为 Time-Series-Library 的深度时序模型）
"""
from datetime import datetime, timedelta
from collections import defaultdict
from app.models import Inquiry, Transaction
from app import db


def _get_monthly_series():
    """从 demands/transactions 聚合月度供需数据"""
    supply_by_month = defaultdict(int)
    demand_by_month = defaultdict(int)
    for d in Inquiry.query.filter(Inquiry.status == 'active').all():
        m = d.created_at.strftime('%Y-%m') if d.created_at else None
        if m:
            if d.direction == 'supply':
                supply_by_month[m] += 1
            else:
                demand_by_month[m] += 1
    for t in Transaction.query.all():
        m = t.created_at.strftime('%Y-%m') if t.created_at else None
        if m:
            supply_by_month[m] += 0  # 占位使键存在
            demand_by_month[m] += 0
    months = sorted(set(supply_by_month.keys()) | set(demand_by_month.keys()))
    supply_vals = [supply_by_month.get(m, 0) for m in months]
    demand_vals = [demand_by_month.get(m, 0) for m in months]
    return months, supply_vals, demand_vals


def forecast_supply_demand(horizon=6) -> dict:
    """
    供需趋势预测，返回未来 horizon 个月的预测值
    使用简单指数平滑 (SES) 作为轻量实现
    """
    months, supply_vals, demand_vals = _get_monthly_series()
    if len(months) < 2:
        # 数据不足时返回最近值填充
        s_last = supply_vals[-1] if supply_vals else 0
        d_last = demand_vals[-1] if demand_vals else 0
        base = datetime.now()
        fut_months = [(base + timedelta(days=30 * i)).strftime('%Y-%m') for i in range(1, horizon + 1)]
        return {
            "months": months,
            "supply": supply_vals,
            "demand": demand_vals,
            "forecast_months": fut_months,
            "forecast_supply": [s_last] * horizon,
            "forecast_demand": [d_last] * horizon,
        }
    
    try:
        from statsmodels.tsa.holtwinters import SimpleExpSmoothing
        import numpy as np
        s_series = supply_vals if len(supply_vals) >= 2 else supply_vals + [supply_vals[-1]]
        d_series = demand_vals if len(demand_vals) >= 2 else demand_vals + [demand_vals[-1]]
        ses_s = SimpleExpSmoothing(s_series).fit()
        ses_d = SimpleExpSmoothing(d_series).fit()
        f_s = ses_s.forecast(horizon)
        f_d = ses_d.forecast(horizon)
        base = datetime.now()
        fut_months = [(base + timedelta(days=30 * i)).strftime('%Y-%m') for i in range(1, horizon + 1)]
        return {
            "months": months,
            "supply": supply_vals,
            "demand": demand_vals,
            "forecast_months": fut_months,
            "forecast_supply": [max(0, round(float(x), 1)) for x in f_s],
            "forecast_demand": [max(0, round(float(x), 1)) for x in f_d],
        }
    except ImportError:
        # 无 statsmodels 时使用简单移动平均
        s_avg = sum(supply_vals) / len(supply_vals) if supply_vals else 0
        d_avg = sum(demand_vals) / len(demand_vals) if demand_vals else 0
        base = datetime.now()
        fut_months = [(base + timedelta(days=30 * i)).strftime('%Y-%m') for i in range(1, horizon + 1)]
        return {
            "months": months,
            "supply": supply_vals,
            "demand": demand_vals,
            "forecast_months": fut_months,
            "forecast_supply": [round(s_avg, 1)] * horizon,
            "forecast_demand": [round(d_avg, 1)] * horizon,
        }

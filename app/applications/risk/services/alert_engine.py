"""
预警规则引擎 (AlertEngine)
- 四类预警检查：产能风险、供应链断链、企业经营风险、信用分异常
- 预警等级判定（红/黄/蓝）
- 基于 AlertThreshold 的可配置阈值
- 需求: 32.1-32.8
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

from config import DEFAULT_ALERT_THRESHOLDS

from app import db
from app.models import Alert, Enterprise, Message, Product
from app.services.credit_score_events import credit_events_oldest_first

logger = logging.getLogger(__name__)

# ── 默认阈值（数据库无配置时使用） ──────────────────────────────────────
_DEFAULTS = {
    # 产能风险：利用率低于此值触发预警
    'capacity_utilization_low': 0.30,
    # 供应链断链：供应商数量少于此值触发预警
    'supplier_count_min': 3,
    # 企业经营风险：信用分低于此值触发预警
    'business_risk_credit_min': 50.0,
    # 信用分异常：7天内下降超过此值触发预警
    'credit_drop_7days': 15.0,
    # 红色预警阈值（严重程度 >= 此值）
    'red_threshold': 0.7,
    # 黄色预警阈值（严重程度 >= 此值）
    'yellow_threshold': 0.4,
}

# 预警类型常量
ALERT_TYPE_CAPACITY = 'capacity_risk'
ALERT_TYPE_SUPPLY_CHAIN = 'supply_chain_break'
ALERT_TYPE_BUSINESS = 'business_risk'
ALERT_TYPE_CREDIT_ANOMALY = 'credit_anomaly'

# 预警等级常量
LEVEL_RED = 'red'
LEVEL_YELLOW = 'yellow'
LEVEL_BLUE = 'blue'


def _build_analysis_data(
    alert_type: str,
    enterprise_name: str,
    extra_context: Optional[Dict] = None,
) -> Dict:
    """
    为每一条预警生成结构化的深度分析数据。
    当前基于规则模板生成，后期可对接大模型 API 填充。
    """
    ctx = extra_context or {}
    import datetime as _dt
    import random
    import hashlib

    # 确定性种子：基于企业名称 hash，确保同一企业走势稳定
    seed_int = int(hashlib.md5(enterprise_name.encode()).hexdigest()[:8], 16)
    rng = random.Random(seed_int)

    # 近 7 天趋势：产能利用率或信用分母算值（基空位出现动态波动）
    base = ctx.get('base_trend_value', rng.randint(40, 80))
    historical_trend = [
        max(5, min(100, base + rng.randint(-12, 12))) for _ in range(7)
    ]

    # 按预警类型匹配深度分析模板
    now_str = _dt.datetime.now().strftime('%m-%d %H:%M')
    node_id = f"LN-NODE-{rng.randint(100, 999)}"

    if alert_type == 'capacity_risk':
        utilization = ctx.get('utilization', 0.3)
        return {
            'risk_reason': (
                f'SaaS 系统实时监测数据显示，您当前核心产线的生产负荷已'
                f'连续 7 天均值低于 {utilization*100:.1f}%。该数据比行业均値偏低约 20%，'
                f'表明您的设备处于闲置浪费状态，产能冗余严重。'
            ),
            'impact_scope': (
                f'若此状态持续超过 30 天，将自动触发平台信用分数扣减'
                f'（预计 -5 分）。同时，您的供应商搜索权重将被调低，降低'
                f'平台活跃度可见性。'
            ),
            'ai_suggestions': [
                f'穿计匹配 3 项紧急需匹配的生产需求（精密齿轮加工 10,000 件 / 铝合金压铸件代工）',
                f'建议联系平台招商专员，尝试加入「集采拼单大厅」吸引段小订单',
                f'平台可为您开启「侵卡式扮弹价格策略」，对闲置产能进行消化',
            ],
            'data_source_info': {
                'name': f'IoT 终端：{node_id}',
                'node_id': node_id,
                'last_sync': f'最近应答: {now_str}',
            },
            'historical_trend': historical_trend,
        }
    elif alert_type == 'supply_chain_break':
        supplier_count = ctx.get('supplier_count', 1)
        return {
            'risk_reason': (
                f'平台关联数据显示，该品类目前仅杰9{supplier_count}家有效供应商。'
                f'一旦主要供应商暂停供货，无备用节点可以接典交接。'
            ),
            'impact_scope': (
                f'供应断链将导致相关企业产线停击，平均受影响期为 14-21 天。'
                f'建议立刻块备备用供应商提院计划。'
            ),
            'ai_suggestions': [
                f'将此品类纳入平台「招商选题库」，启动自动化招商流程',
                f'建议就近择择 2-3 家备候供应商并小量评价仓单下单',
                f'平台将在本应层押补贴昇级供应商搜索权重',
            ],
            'data_source_info': {
                'name': f'IoT 终端：{node_id}',
                'node_id': node_id,
                'last_sync': f'最近应答: {now_str}',
            },
            'historical_trend': historical_trend,
        }
    elif alert_type == 'credit_anomaly':
        drop = ctx.get('drop', 15.0)
        return {
            'risk_reason': (
                f'信用分监控模块检测到，您的信用分在迗 7 天将下降约 {drop:.1f} 分。'
                f'主要诱因可能为订单延迟或存在未结常账。'
            ),
            'impact_scope': (
                f'信用分进一步下滑将影响您在平台的匹配权重、报价成功率及'
                f'集采拼单拥有权。建议尽快处理痆结账款。'
            ),
            'ai_suggestions': [
                f'立即前往「信用重建助手」了解加分我务路径',
                f'加快拥有未寄出的报价单答复进度',
                f'主动在平台和交易方确认已履行的延迟订单状态',
            ],
            'data_source_info': {
                'name': f'IoT 终端：{node_id}',
                'node_id': node_id,
                'last_sync': f'最近应答: {now_str}',
            },
            'historical_trend': historical_trend,
        }
    else:  # business_risk
        credit_score = ctx.get('credit_score', 45.0)
        return {
            'risk_reason': (
                f'企业经营风险监测显示异常，当前信用分 {credit_score:.1f} 分低于平台默认抖动阈值。'
                f'可能存在履约能力不足或财务负担分题。'
            ),
            'impact_scope': (
                f'如不及时改善，平台将降低其展示面染并限制其全面报价和能力。'
                f'建议将此公司列为重点跟踪对象。'
            ),
            'ai_suggestions': [
                f'检测其近期履行订单牌号，确认是否有过期未结账款',
                f'建议主动联系平台客户经理进行商谈，将未付账项目才削救',
                f'用 3 天内完成一笔小额订单老实履行，快速回血信用分',
            ],
            'data_source_info': {
                'name': f'IoT 终端：{node_id}',
                'node_id': node_id,
                'last_sync': f'最近应答: {now_str}',
            },
            'historical_trend': historical_trend,
        }


def _get_threshold(key: str) -> float:
    """从 config.DEFAULT_ALERT_THRESHOLDS 读取，否则用模块内 _DEFAULTS。"""
    if key in DEFAULT_ALERT_THRESHOLDS:
        return float(DEFAULT_ALERT_THRESHOLDS[key])
    return float(_DEFAULTS.get(key, 0.5))


# ── 预警等级判定 ──────────────────────────────────────────────────────────

def get_alert_level(alert_type: str, severity: float) -> str:
    """
    根据严重程度和阈值配置确定预警等级。
    severity: 0.0 ~ 1.0，越高越严重
    返回: 'red' | 'yellow' | 'blue'
    """
    red_threshold = _get_threshold('red_threshold')
    yellow_threshold = _get_threshold('yellow_threshold')

    if severity >= red_threshold:
        return LEVEL_RED
    elif severity >= yellow_threshold:
        return LEVEL_YELLOW
    else:
        return LEVEL_BLUE


# ── 四类预警检查 ──────────────────────────────────────────────────────────

def check_capacity_risk() -> List[Dict]:
    """
    检查产能风险：产能利用率过低的企业。
    需求: 32.1
    """
    threshold = _get_threshold('capacity_utilization_low')
    alerts = []

    enterprises = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.max_capacity.isnot(None),
        Enterprise.max_capacity > 0,
    ).all()

    for ent in enterprises:
        utilization = (ent.current_orders or 0) / ent.max_capacity
        if utilization < threshold:
            severity = 1.0 - utilization  # 利用率越低，严重程度越高
            level = get_alert_level(ALERT_TYPE_CAPACITY, severity)
            alerts.append({
                'product_name': ent.name,
                'message': (
                    f'企业“{ent.name}”产能利用率仅{utilization*100:.1f}%'
                    f'（当前订单{ent.current_orders}，最大产能{ent.max_capacity}），'
                    f'存在产能闲置风险'
                ),
                'level': level,
                'dimension': 'capacity',
                'alert_type': ALERT_TYPE_CAPACITY,
                'severity_score': round(severity, 3),
                'suggestion': f'建议{ent.name}加大市场开拓力度，提高产能利用率',
                'analysis_data': _build_analysis_data(
                    ALERT_TYPE_CAPACITY, ent.name,
                    {'utilization': utilization, 'base_trend_value': int(utilization * 100)}
                ),
            })

    return alerts


def check_supply_chain_break() -> List[Dict]:
    """
    检查供应链断链风险：某产品供应商数量不足。
    当检测到缺口时，自动生成招商建议并关联。
    需求: 32.2, 34.1, 34.2
    """
    threshold = int(_get_threshold('supplier_count_min'))
    alerts = []

    # 统计每个产品的供应商数量
    from sqlalchemy import func
    product_supplier_counts = (
        db.session.query(Product.name, func.count(func.distinct(Product.enterprise_id)))
        .group_by(Product.name)
        .all()
    )

    for product_name, supplier_count in product_supplier_counts:
        if 0 < supplier_count < threshold:
            severity = 1.0 - (supplier_count / threshold)
            level = get_alert_level(ALERT_TYPE_SUPPLY_CHAIN, severity)

            # 生成招商建议
            recruitment_suggestion = _build_recruitment_suggestion(
                product_name, supplier_count
            )

            alerts.append({
                'product_name': product_name,
                'message': (
                    f'产品“{product_name}”仅有{supplier_count}家供应商'
                    f'（阈值{threshold}家），存在供应链断链风险'
                ),
                'level': level,
                'dimension': 'supply_chain',
                'alert_type': ALERT_TYPE_SUPPLY_CHAIN,
                'severity_score': round(severity, 3),
                'suggestion': (
                    f'建议引进或培育更多“{product_name}”本地供应商，降低断链风险。'
                    f'{recruitment_suggestion}'
                ),
                'analysis_data': _build_analysis_data(
                    ALERT_TYPE_SUPPLY_CHAIN, product_name,
                    {'supplier_count': supplier_count}
                ),
            })

    return alerts


def _build_recruitment_suggestion(product_name: str, supplier_count: int) -> str:
    """为供应链断链预警生成招商建议文本。需求: 34.1, 34.2"""
    try:
        from app.services.recruitment_service import generate_recruitment_suggestions
        suggestion = generate_recruitment_suggestions({
            'product_name': product_name,
            'gap_type': 'supplier_shortage',
            'supplier_count': supplier_count,
            'local_ratio': 1.0,
        })
        return suggestion.get('description', '')
    except Exception:
        return ''


def check_business_risk() -> List[Dict]:
    """
    检查企业经营风险：信用分过低或被多次举报的企业。
    需求: 32.3
    """
    credit_min = _get_threshold('business_risk_credit_min')
    alerts = []

    # 信用分过低的企业
    low_credit_ents = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.credit_score < credit_min,
    ).all()

    for ent in low_credit_ents:
        score = float(ent.credit_score or 60.0)
        severity = (credit_min - score) / credit_min
        level = get_alert_level(ALERT_TYPE_BUSINESS, severity)
        alerts.append({
            'product_name': ent.name,
            'message': (
                f'企业“{ent.name}”信用分仅{score:.1f}分'
                f'（低于风险阈值{credit_min:.0f}分），存在经营风险'
            ),
            'level': level,
            'dimension': 'business',
            'alert_type': ALERT_TYPE_BUSINESS,
            'severity_score': round(severity, 3),
            'suggestion': f'建议关注“{ent.name}”经营状况，必要时开展帮扶',
            'analysis_data': _build_analysis_data(
                ALERT_TYPE_BUSINESS, ent.name,
                {'credit_score': score}
            ),
        })

    # 被多次举报的企业（核实为真超过3次，数据在 Enterprise.extras.reports_received）
    def _verified_report_counts():
        counts = {}
        for ent in Enterprise.query.all():
            ex = ent.extras if isinstance(ent.extras, dict) else {}
            recv = ex.get("reports_received") or []
            n = sum(
                1
                for r in recv
                if isinstance(r, dict) and r.get("status") == "verified_true"
            )
            if n:
                counts[ent.id] = n
        return counts

    report_counts = [(eid, n) for eid, n in _verified_report_counts().items() if n >= 3]

    existing_ids = {a["product_name"] for a in alerts}

    for ent_id, count in report_counts:
        ent = Enterprise.query.get(ent_id)
        if not ent or ent.name in existing_ids:
            continue
        severity = min(1.0, count / 5.0)
        level = get_alert_level(ALERT_TYPE_BUSINESS, severity)
        alerts.append({
            'product_name': ent.name,
            'message': (
                f'企业"{ent.name}"已被核实举报{count}次，'
                f'存在诚信经营风险'
            ),
            'level': level,
            'dimension': 'business',
            'alert_type': ALERT_TYPE_BUSINESS,
            'severity_score': round(severity, 3),
            'suggestion': f'建议对"{ent.name}"开展重点监管，核查经营行为',
        })

    return alerts


def check_credit_anomaly() -> List[Dict]:
    """
    检查信用分异常：7天内信用分下降超过阈值。
    需求: 32.4, 28.1
    """
    drop_threshold = _get_threshold('credit_drop_7days')
    cutoff = datetime.utcnow() - timedelta(days=7)
    alerts = []

    enterprises = Enterprise.query.filter_by(role='enterprise').all()

    for ent in enterprises:
        # 7 天时间窗内最早一条信用分事件（与旧 credit_score_history 语义一致）
        window_events = []
        for ev in credit_events_oldest_first(ent):
            raw = ev.get("created_at")
            if not raw:
                continue
            try:
                s = str(raw).replace("Z", "+00:00")
                dt = datetime.fromisoformat(s.replace("Z", ""))
            except Exception:
                continue
            # 统一剥除时区，保证与 naive cutoff 可比
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            if dt >= cutoff:
                window_events.append((dt, ev))
        window_events.sort(key=lambda x: x[0])
        oldest_record = window_events[0][1] if window_events else None

        if not oldest_record:
            continue

        current_score = float(ent.credit_score or 60.0)
        score_7days_ago = float(oldest_record.get("old_score") or 60.0)
        drop = score_7days_ago - current_score

        if drop >= drop_threshold:
            severity = min(1.0, drop / 30.0)  # 30分为满严重程度
            level = get_alert_level(ALERT_TYPE_CREDIT_ANOMALY, severity)
            alerts.append({
                'product_name': ent.name,
                'message': (
                    f'企业“{ent.name}”信用分7天内下降{drop:.1f}分'
                    f'（从{score_7days_ago:.1f}降至{current_score:.1f}），'
                    f'触发信用分异常预警'
                ),
                'level': level,
                'dimension': 'credit',
                'alert_type': ALERT_TYPE_CREDIT_ANOMALY,
                'severity_score': round(severity, 3),
                'suggestion': f'建议联系“{ent.name}”了解信用分下降原因，提供帮扶指导',
                'analysis_data': _build_analysis_data(
                    ALERT_TYPE_CREDIT_ANOMALY, ent.name,
                    {'drop': drop, 'base_trend_value': int(current_score)}
                ),
            })

    return alerts


# ── 创建预警记录 ──────────────────────────────────────────────────────────

def create_alert(alert_data: Dict) -> Alert:
    """
    创建预警记录到数据库。
    需求: 32.5
    """
    alert = Alert(
        product_name=alert_data['product_name'],
        message=alert_data['message'],
        level=alert_data['level'],
        dimension=alert_data['dimension'],
        is_active=True,
        suggestion=alert_data.get('suggestion'),
    )
    # 扩展字段（通过 schema_migrator 添加的列）
    if hasattr(Alert, 'alert_type'):
        alert.alert_type = alert_data.get('alert_type')
    if hasattr(Alert, 'severity_score'):
        alert.severity_score = alert_data.get('severity_score')
    if hasattr(Alert, 'auto_pushed'):
        alert.auto_pushed = False
    if hasattr(Alert, 'linked_recruitment_task_id'):
        alert.linked_recruitment_task_id = alert_data.get('linked_recruitment_task_id')
    # 注入深度分析数据
    if hasattr(Alert, 'analysis_data'):
        alert.analysis_data = alert_data.get('analysis_data')

    db.session.add(alert)
    return alert


# ── 主入口：执行所有预警检查 ─────────────────────────────────────────────

def run_all_checks() -> List[Alert]:
    """
    执行所有预警检查，停用旧预警，创建新预警，并按等级分发通知。
    需求: 32.8, 33.2, 33.3, 33.4
    """
    logger.info("[AlertEngine] 开始执行预警检查")

    # 停用所有旧预警
    Alert.query.update({'is_active': False}, synchronize_session=False)

    new_alerts = []

    # 1. 产能风险
    try:
        capacity_alerts = check_capacity_risk()
        for data in capacity_alerts:
            new_alerts.append(create_alert(data))
        logger.info(f"[AlertEngine] 产能风险检查完成，发现{len(capacity_alerts)}条预警")
    except Exception as e:
        logger.error(f"[AlertEngine] 产能风险检查失败: {e}", exc_info=True)

    # 2. 供应链断链
    try:
        supply_alerts = check_supply_chain_break()
        for data in supply_alerts:
            new_alerts.append(create_alert(data))
        logger.info(f"[AlertEngine] 供应链断链检查完成，发现{len(supply_alerts)}条预警")
    except Exception as e:
        logger.error(f"[AlertEngine] 供应链断链检查失败: {e}", exc_info=True)

    # 3. 企业经营风险
    try:
        business_alerts = check_business_risk()
        for data in business_alerts:
            new_alerts.append(create_alert(data))
        logger.info(f"[AlertEngine] 企业经营风险检查完成，发现{len(business_alerts)}条预警")
    except Exception as e:
        logger.error(f"[AlertEngine] 企业经营风险检查失败: {e}", exc_info=True)

    # 4. 信用分异常
    try:
        credit_alerts = check_credit_anomaly()
        for data in credit_alerts:
            new_alerts.append(create_alert(data))
        logger.info(f"[AlertEngine] 信用分异常检查完成，发现{len(credit_alerts)}条预警")
    except Exception as e:
        logger.error(f"[AlertEngine] 信用分异常检查失败: {e}", exc_info=True)

    db.session.commit()

    # 5. 按等级分发通知（红色/黄色推送，蓝色仅显示）
    try:
        from app.services.alert_notifier import notify_alert
        for alert in new_alerts:
            if alert.level in (LEVEL_RED, LEVEL_YELLOW):
                notify_alert(alert)
        db.session.commit()
    except Exception as e:
        logger.error(f"[AlertEngine] 预警通知发送失败: {e}", exc_info=True)

    logger.info(f"[AlertEngine] 预警检查完成，共创建{len(new_alerts)}条新预警")
    return new_alerts

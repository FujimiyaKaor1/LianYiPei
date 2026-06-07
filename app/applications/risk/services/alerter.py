from datetime import datetime

from config import DEFAULT_ALERT_THRESHOLDS

from app import db
from app.models import Alert, Enterprise, Product

# 默认进口依赖度（无 DB 数据时使用）
_DEFAULT_IMPORT_RISKS = {
    '芯片': 0.8, '光刻机': 0.9, '高端传感器': 0.7, '特种钢材': 0.5, '精密轴承': 0.6
}

def _get_import_risks():
    """从 Product.import_risk JSON 与内置默认合并"""
    out = dict(_DEFAULT_IMPORT_RISKS)
    for p in Product.query.all():
        ir = p.import_risk if isinstance(p.import_risk, dict) else {}
        r = ir.get("import_ratio")
        if r is not None:
            try:
                out[p.name] = float(r)
            except (TypeError, ValueError):
                pass
    return out
LOCAL_PROVINCE = '四川'
CRITICAL_PRODUCTS = ['芯片', '电机', '特种钢材', '电路板', '高端传感器', '光刻机', '精密轴承']

# 产品与可培育企业类型映射
CHAIN_FILL_SUGGESTIONS = {
    '芯片': '建议培育或引进本地半导体设计、封装企业',
    '电机': '建议扶持本地电机、电控生产企业',
    '特种钢材': '建议引进特种合金、精密铸造企业',
    '电路板': '建议培育PCB制造、电子元器件企业',
    '高端传感器': '建议引进MEMS、工业传感器研发企业',
    '光刻机': '建议引进高端装备制造、光学器件企业',
    '精密轴承': '建议扶持精密机械加工、轴承制造企业',
}

def get_threshold(dimension, default):
    """从 config.DEFAULT_ALERT_THRESHOLDS 读取预警阈值"""
    v = DEFAULT_ALERT_THRESHOLDS.get(dimension)
    return float(v) if v is not None else default

def _gen_suggestion(product_name, dimension):
    """生成补链建议"""
    base = CHAIN_FILL_SUGGESTIONS.get(product_name, f'建议培育或引进本地{product_name}相关企业')
    if dimension == 'import':
        return base + '；优先考虑国产替代'
    if dimension == 'interprovincial':
        return base + '；加强本地配套'
    return base

def check_import_dependency(product_name, threshold=None):
    threshold = threshold if threshold is not None else get_threshold('import', 0.6)
    import_risks = _get_import_risks()
    if product_name in import_risks and import_risks[product_name] > threshold:
        return {
            'product_name': product_name,
            'message': f"{product_name}进口依赖度{import_risks[product_name]*100:.0f}%，来源国集中，存在断供风险",
            'level': 'red',
            'dimension': 'import',
            'suggestion': _gen_suggestion(product_name, 'import')
        }
    return None

def check_interprovincial_dependency(product_name, threshold=None):
    threshold = threshold if threshold is not None else get_threshold('interprovincial', 0.7)
    products = Product.query.filter_by(name=product_name).all()
    if not products:
        return None
    provinces = {}
    for p in products:
        ent = Enterprise.query.get(p.enterprise_id)
        if ent and ent.address:
            province = ent.address[:2] if len(ent.address) >= 2 else ent.address
            provinces[province] = provinces.get(province, 0) + 1
    total = sum(provinces.values())
    if total == 0:
        return None
    local_count = provinces.get(LOCAL_PROVINCE, 0)
    interprovincial_ratio = 1 - local_count / total
    if interprovincial_ratio > threshold:
        return {
            'product_name': product_name,
            'message': f"{product_name}省外采购占比{interprovincial_ratio*100:.0f}%，跨省依赖度高",
            'level': 'orange',
            'dimension': 'interprovincial',
            'suggestion': _gen_suggestion(product_name, 'interprovincial')
        }
    return None

def check_local_supplier_count(product_name, threshold=None):
    threshold = int(threshold) if threshold is not None else int(get_threshold('local', 3))
    products = Product.query.filter_by(name=product_name).all()
    supplier_count = len(set(p.enterprise_id for p in products))
    if 0 < supplier_count < threshold:
        return {
            'product_name': product_name,
            'message': f"本地供应商仅{supplier_count}家，配套能力弱",
            'level': 'yellow',
            'dimension': 'local',
            'suggestion': _gen_suggestion(product_name, 'local')
        }
    return None

def create_alert(alert_data):
    alert = Alert(
        product_name=alert_data['product_name'],
        message=alert_data['message'],
        level=alert_data['level'],
        dimension=alert_data['dimension'],
        suggestion=alert_data.get('suggestion')
    )
    db.session.add(alert)
    return alert

def check_green_risk():
    """绿色风险预警：检测关键产品供应链中高污染/高能耗企业占比过高的情况。"""
    green_alerts = []
    for product_name in CRITICAL_PRODUCTS:
        products = Product.query.filter_by(name=product_name).all()
        if not products:
            continue
        supplier_ids = list(set(p.enterprise_id for p in products))
        suppliers = Enterprise.query.filter(Enterprise.id.in_(supplier_ids)).all()
        if not suppliers:
            continue

        total = len(suppliers)
        high_carbon = [s for s in suppliers if (getattr(s, 'carbon_emission_level', '') or '').upper() in ('C', 'D')]
        no_green = [s for s in suppliers if not getattr(s, 'is_green_factory', False)]

        if total > 0 and len(high_carbon) / total >= 0.5:
            green_names = [s.name for s in suppliers if getattr(s, 'is_green_factory', False)]
            suggestion = (
                f'该环节{len(high_carbon)}/{total}家供应商碳排放等级为C/D。'
                + (f'建议优先选择绿色企业：{"、".join(green_names[:3])}' if green_names else '建议引进绿色低碳供应商')
            )
            green_alerts.append({
                'product_name': product_name,
                'message': f'{product_name}供应链中{round(len(high_carbon)/total*100)}%的企业为高碳排放(C/D级)',
                'level': 'orange',
                'dimension': 'green',
                'suggestion': suggestion,
            })

        if total > 0 and len(no_green) == total:
            green_alerts.append({
                'product_name': product_name,
                'message': f'{product_name}供应链无绿色工厂认证企业，存在合规风险',
                'level': 'yellow',
                'dimension': 'green',
                'suggestion': f'建议培育或引进具有绿色工厂认证的{product_name}供应商',
            })

    return green_alerts


def run_all_checks():
    for a in Alert.query.all():
        a.is_active = False
    alerts = []
    for product in CRITICAL_PRODUCTS:
        alert_data = check_import_dependency(product)
        if alert_data:
            alerts.append(create_alert(alert_data))
            continue
        alert_data = check_interprovincial_dependency(product)
        if alert_data:
            alerts.append(create_alert(alert_data))
            continue
        alert_data = check_local_supplier_count(product)
        if alert_data:
            alerts.append(create_alert(alert_data))

    # 绿色风险预警
    for alert_data in check_green_risk():
        alerts.append(create_alert(alert_data))

    db.session.commit()
    return alerts

def generate_chain_risk_report():
    """生成补链风险报告"""
    run_all_checks()
    active = Alert.query.filter_by(is_active=True).order_by(Alert.level, Alert.created_at.desc()).all()
    lines = [
        '# 产业链补链风险报告',
        f'生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}',
        '',
        '## 预警汇总',
        f'共 {len(active)} 条预警',
        '',
        '## 预警详情',
    ]
    for a in active:
        lines.append(f'### {a.product_name} [{a.level}]')
        lines.append(f'- 风险维度：{a.dimension}')
        lines.append(f'- 预警信息：{a.message}')
        if a.suggestion:
            lines.append(f'- 补链建议：{a.suggestion}')
        lines.append('')
    return '\n'.join(lines)

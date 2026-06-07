"""
招商决策服务 (RecruitmentService)
- 产业链缺口分析
- 招商建议生成
- 潜在企业推荐（工商数据API模拟）
- 招商任务管理
需求: 34.1-34.7, 36.1-36.7, 37.1-37.7
"""
from __future__ import annotations

import logging
import random
from datetime import datetime, date
from typing import List, Dict, Optional

from app import db
from app.models import Enterprise, Inquiry, Product, RecruitmentTask

logger = logging.getLogger(__name__)

# ── 产业链缺口分析 ────────────────────────────────────────────────────────

def analyze_supply_chain_gaps(include_neo4j: bool = True) -> List[Dict]:
    """
    分析产业链缺口：
    1. 供应商数量不足（< 3家）
    2. 本地化不足（本地供应商占比 < 30%）
    3. 历史未匹配成功的产品
    4. （可选）Neo4j 图谱缺口
    需求: 34.1, 34.2, 34.3, 36.1, 36.2, 36.3
    """
    gaps = []

    # ── 1. 从 MySQL 统计每个产品的供应商数量 ──────────────────────────────
    from sqlalchemy import func
    product_counts = (
        db.session.query(
            Product.name,
            func.count(func.distinct(Product.enterprise_id)).label('supplier_count')
        )
        .group_by(Product.name)
        .all()
    )

    product_supplier_map: Dict[str, int] = {
        row.name: row.supplier_count for row in product_counts
    }

    # ── 2. 从 Neo4j 获取上下游关系，识别缺口节点（可跳过以加快首屏） ────────
    neo4j_gaps = _analyze_neo4j_gaps() if include_neo4j else []

    # ── 3. 统计本地供应商占比（以 city 字段判断是否本地） ─────────────────
    local_ratio_map = _calc_local_ratio()

    # ── 4. 统计历史未匹配成功的产品（有需求但无供应） ─────────────────────
    unmatched_products = _get_unmatched_products()

    # ── 合并缺口信息 ──────────────────────────────────────────────────────
    processed = set()

    for product_name, supplier_count in product_supplier_map.items():
        if supplier_count >= 3:
            continue
        gap = _build_gap(
            product_name=product_name,
            gap_type='supplier_shortage',
            supplier_count=supplier_count,
            local_ratio=local_ratio_map.get(product_name, 1.0),
            is_unmatched=product_name in unmatched_products,
        )
        gaps.append(gap)
        processed.add(product_name)

    # 本地化不足（供应商够但本地比例低）
    for product_name, local_ratio in local_ratio_map.items():
        if product_name in processed:
            continue
        if local_ratio < 0.30:
            supplier_count = product_supplier_map.get(product_name, 0)
            gap = _build_gap(
                product_name=product_name,
                gap_type='localization_shortage',
                supplier_count=supplier_count,
                local_ratio=local_ratio,
                is_unmatched=product_name in unmatched_products,
            )
            gaps.append(gap)
            processed.add(product_name)

    # 历史未匹配成功
    for product_name in unmatched_products:
        if product_name in processed:
            continue
        gap = _build_gap(
            product_name=product_name,
            gap_type='unmatched',
            supplier_count=product_supplier_map.get(product_name, 0),
            local_ratio=local_ratio_map.get(product_name, 1.0),
            is_unmatched=True,
        )
        gaps.append(gap)
        processed.add(product_name)

    # Neo4j 图谱中发现的缺口节点
    for neo_gap in neo4j_gaps:
        if neo_gap['product_name'] not in processed:
            gaps.append(neo_gap)
            processed.add(neo_gap['product_name'])

    # 按紧迫程度排序
    gaps.sort(key=lambda g: g['urgency_score'], reverse=True)
    logger.info(f"[RecruitmentService] 产业链缺口分析完成，发现{len(gaps)}个缺口")
    return gaps


def _build_gap(
    product_name: str,
    gap_type: str,
    supplier_count: int,
    local_ratio: float,
    is_unmatched: bool,
) -> Dict:
    """构建缺口数据结构。"""
    # 紧迫程度评分 0~1
    urgency = 0.0
    if gap_type == 'supplier_shortage':
        urgency = max(0.5, 1.0 - supplier_count / 3.0)
    elif gap_type == 'localization_shortage':
        urgency = max(0.3, 1.0 - local_ratio)
    elif gap_type == 'unmatched':
        urgency = 0.6

    if is_unmatched:
        urgency = min(1.0, urgency + 0.2)

    urgency_label = '紧急' if urgency >= 0.7 else ('较高' if urgency >= 0.4 else '一般')

    return {
        'product_name': product_name,
        'gap_type': gap_type,
        'gap_type_label': _gap_type_label(gap_type),
        'supplier_count': supplier_count,
        'local_ratio': round(local_ratio, 3),
        'local_ratio_pct': f'{local_ratio * 100:.1f}%',
        'is_unmatched': is_unmatched,
        'affected_enterprise_count': _count_affected_enterprises(product_name),
        'urgency_score': round(urgency, 3),
        'urgency_label': urgency_label,
        'suggestion': generate_recruitment_suggestions({
            'product_name': product_name,
            'gap_type': gap_type,
            'supplier_count': supplier_count,
            'local_ratio': local_ratio,
        }),
    }


def _count_affected_enterprises(product_name: str) -> int:
    """统计有该产品需求的企业数量。"""
    from sqlalchemy import func
    result = (
        db.session.query(func.count(func.distinct(Inquiry.poster_id)))
        .join(Product, Inquiry.product_id == Product.id)
        .filter(Product.name == product_name, Inquiry.direction == 'demand')
        .scalar()
    )
    return result or 0


def _calc_local_ratio() -> Dict[str, float]:
    """
    计算每个产品的本地供应商占比。
    以供应商企业的 city 字段判断是否本地（取最多的城市为"本地"）。
    需求: 34.3
    """
    from sqlalchemy import func
    # 获取所有产品-企业-城市
    rows = (
        db.session.query(Product.name, Enterprise.city)
        .join(Enterprise, Product.enterprise_id == Enterprise.id)
        .all()
    )

    product_cities: Dict[str, List[str]] = {}
    for product_name, city in rows:
        product_cities.setdefault(product_name, []).append(city or '')

    # 找出每个产品最多的城市作为"本地"
    ratio_map: Dict[str, float] = {}
    for product_name, cities in product_cities.items():
        if not cities:
            ratio_map[product_name] = 1.0
            continue
        from collections import Counter
        city_counter = Counter(c for c in cities if c)
        if not city_counter:
            ratio_map[product_name] = 1.0
            continue
        top_city, top_count = city_counter.most_common(1)[0]
        ratio_map[product_name] = top_count / len(cities)

    return ratio_map


def _get_unmatched_products() -> set:
    """
    获取历史上有需求但从未成功匹配的产品名称集合。
    需求: 34.4
    """
    # 有需求的产品
    demand_products = set(
        row[0] for row in
        db.session.query(Product.name)
        .join(Inquiry, Inquiry.product_id == Product.id)
        .filter(Inquiry.direction == 'demand')
        .distinct()
        .all()
    )
    # 有供应的产品
    supply_products = set(
        row[0] for row in
        db.session.query(Product.name)
        .join(Inquiry, Inquiry.product_id == Product.id)
        .filter(Inquiry.direction == 'supply')
        .distinct()
        .all()
    )
    return demand_products - supply_products


def _analyze_neo4j_gaps() -> List[Dict]:
    """
    基于 Neo4j 图数据分析上下游关系，识别缺口节点。
    需求: 36.1, 36.2
    """
    try:
        from app.services.graph_manager import run_query
        # 查找有下游依赖但在 MySQL 中没有供应商的产品
        query = """
        MATCH (p:Product)-[:SUPPLIES_TO]->(downstream:Product)
        WITH downstream.name AS product_name, count(p) AS upstream_count
        RETURN product_name, upstream_count
        ORDER BY upstream_count DESC
        LIMIT 50
        """
        results = run_query(query, None, retry=1, retry_sleep=0.3) or []
        gaps = []
        for row in results:
            product_name = row.get('product_name', '')
            if not product_name:
                continue
            # 检查 MySQL 中是否有供应商
            from sqlalchemy import func
            supplier_count = (
                db.session.query(func.count(func.distinct(Product.enterprise_id)))
                .filter(Product.name == product_name)
                .scalar()
            ) or 0
            if supplier_count < 3:
                gaps.append({
                    'product_name': product_name,
                    'gap_type': 'graph_gap',
                    'gap_type_label': '图谱缺口',
                    'supplier_count': supplier_count,
                    'local_ratio': 1.0,
                    'local_ratio_pct': '100.0%',
                    'is_unmatched': False,
                    'affected_enterprise_count': _count_affected_enterprises(product_name),
                    'urgency_score': round(max(0.3, 1.0 - supplier_count / 3.0), 3),
                    'urgency_label': '较高' if supplier_count < 2 else '一般',
                    'suggestion': generate_recruitment_suggestions({
                        'product_name': product_name,
                        'gap_type': 'graph_gap',
                        'supplier_count': supplier_count,
                        'local_ratio': 1.0,
                    }),
                })
        return gaps
    except Exception as e:
        logger.warning(f"[RecruitmentService] Neo4j 缺口分析失败（跳过）: {e}")
        return []


def _gap_type_label(gap_type: str) -> str:
    return {
        'supplier_shortage': '供应商不足',
        'localization_shortage': '本地化不足',
        'unmatched': '历史未匹配',
        'graph_gap': '图谱缺口',
    }.get(gap_type, gap_type)


# ── 招商建议生成 ──────────────────────────────────────────────────────────

def generate_recruitment_suggestions(gap: Dict) -> Dict:
    """
    根据缺口信息生成招商建议。
    需求: 34.1, 34.2, 34.5, 34.6, 34.7
    """
    product_name = gap.get('product_name', '')
    gap_type = gap.get('gap_type', '')
    supplier_count = gap.get('supplier_count', 0)
    local_ratio = gap.get('local_ratio', 1.0)

    # 推断企业类型
    enterprise_type = _infer_enterprise_type(product_name)

    # 预计投资规模
    investment_scale = _estimate_investment_scale(product_name, gap_type)

    # 招商优先级
    priority = 'high' if gap_type in ('supplier_shortage', 'unmatched') else 'normal'
    if supplier_count == 0:
        priority = 'high'

    # 建议描述
    if gap_type == 'supplier_shortage':
        desc = (
            f'"{product_name}"当前仅有{supplier_count}家供应商，'
            f'建议引进{3 - supplier_count}家以上{enterprise_type}，'
            f'预计投资规模{investment_scale}。'
        )
    elif gap_type == 'localization_shortage':
        desc = (
            f'"{product_name}"本地供应商占比仅{local_ratio*100:.1f}%，'
            f'建议引进本地{enterprise_type}，'
            f'预计投资规模{investment_scale}。'
        )
    elif gap_type == 'unmatched':
        desc = (
            f'"{product_name}"历史上有需求但无法匹配供应，'
            f'建议引进{enterprise_type}填补空白，'
            f'预计投资规模{investment_scale}。'
        )
    else:
        desc = (
            f'建议引进"{product_name}"相关{enterprise_type}，'
            f'预计投资规模{investment_scale}。'
        )

    return {
        'product_name': product_name,
        'enterprise_type': enterprise_type,
        'investment_scale': investment_scale,
        'priority': priority,
        'priority_label': '高优先级' if priority == 'high' else '普通',
        'description': desc,
        'target_count': max(1, 3 - supplier_count) if gap_type == 'supplier_shortage' else 2,
    }


def _infer_enterprise_type(product_name: str) -> str:
    """根据产品名称推断所需企业类型。"""
    keywords = {
        '电子': '电子元器件制造企业',
        '芯片': '半导体/集成电路企业',
        '钢铁': '钢铁冶炼加工企业',
        '化工': '精细化工企业',
        '纺织': '纺织服装企业',
        '机械': '机械装备制造企业',
        '汽车': '汽车零部件企业',
        '食品': '食品加工企业',
        '医药': '医药制造企业',
        '新能源': '新能源设备企业',
        '光伏': '光伏组件制造企业',
        '锂电': '锂电池制造企业',
        '塑料': '塑料制品企业',
        '包装': '包装材料企业',
    }
    for kw, etype in keywords.items():
        if kw in product_name:
            return etype
    return '相关制造企业'


def _estimate_investment_scale(product_name: str, gap_type: str) -> str:
    """估算投资规模。"""
    high_investment_keywords = ['芯片', '半导体', '新能源', '光伏', '锂电', '汽车']
    mid_investment_keywords = ['机械', '钢铁', '化工', '医药']

    for kw in high_investment_keywords:
        if kw in product_name:
            return '5000万元以上'
    for kw in mid_investment_keywords:
        if kw in product_name:
            return '1000-5000万元'
    return '500-1000万元'


# ── 潜在企业推荐 ──────────────────────────────────────────────────────────

def recommend_potential_enterprises(gap: Dict) -> List[Dict]:
    """
    推荐潜在招商企业。
    调用工商数据API（模拟实现），根据经营范围、规模、专利数量筛选，按匹配度排序。
    需求: 34.4, 34.5, 37.1-37.7
    """
    product_name = gap.get('product_name', '')
    enterprise_type = gap.get('suggestion', {}).get('enterprise_type', '制造企业')

    # 1. 先从平台内部数据库查找相关企业
    internal_candidates = _find_internal_candidates(product_name)

    # 2. 调用工商数据API（模拟）
    external_candidates = _mock_industrial_commerce_api(product_name, enterprise_type)

    # 3. 合并并去重
    all_candidates = internal_candidates + external_candidates
    seen_names = set()
    unique_candidates = []
    for c in all_candidates:
        if c['name'] not in seen_names:
            seen_names.add(c['name'])
            unique_candidates.append(c)

    # 4. 计算匹配度评分并排序
    scored = [_score_candidate(c, product_name) for c in unique_candidates]
    scored.sort(key=lambda x: x['match_score'], reverse=True)

    return scored[:10]  # 返回前10家


def _find_internal_candidates(product_name: str) -> List[Dict]:
    """从平台内部数据库查找相关企业。"""
    enterprises = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.business_scope.isnot(None),
    ).limit(50).all()

    candidates = []
    for ent in enterprises:
        scope = ent.business_scope or ''
        # 简单关键词匹配
        if any(kw in scope for kw in product_name.split()):
            candidates.append({
                'name': ent.name,
                'source': 'internal',
                'city': ent.city or '未知',
                'registered_capital': ent.registered_capital or 0,
                'business_scope': scope[:100],
                'patent_count': ent.patent_count or 0,
                'credit_score': float(ent.credit_score or 70),
                'is_green_factory': ent.is_green_factory or False,
                'contact': ent.contact or '',
                'phone': ent.phone or '',
            })
    return candidates


def _mock_industrial_commerce_api(product_name: str, enterprise_type: str) -> List[Dict]:
    """
    工商数据API查询（优先调用真实接口，降级为模拟数据）。
    需求: 37.1, 37.2
    """
    try:
        from app.services.external_data_service import industrial_commerce_service
        filters = {'enterprise_type': enterprise_type}
        results = industrial_commerce_service.query_enterprises(product_name, filters)
        if results:
            # 规范化字段名与内部格式一致
            normalized = []
            for item in results:
                normalized.append({
                    'name': item.get('name', ''),
                    'source': item.get('source', 'industrial_commerce_api'),
                    'city': item.get('location', ''),
                    'registered_capital': item.get('registered_capital', ''),
                    'business_scope': item.get('business_scope', ''),
                    'patent_count': item.get('patent_count', 0),
                    'credit_score': 70.0,
                    'is_green_factory': False,
                    'contact': item.get('contact', ''),
                    'phone': '',
                    'registration_no': '',
                    'established_year': None,
                })
            return normalized
    except Exception:
        pass

    # 降级：生成模拟数据
    mock_enterprises = []
    cities = ['深圳', '广州', '东莞', '佛山', '惠州', '珠海', '中山', '江门']
    enterprise_suffixes = ['科技有限公司', '实业有限公司', '制造有限公司', '工业有限公司', '集团有限公司']

    base_names = [
        f'{product_name}专业{enterprise_type[:4]}',
        f'华南{product_name}制造',
        f'粤港澳{product_name}供应链',
        f'智能{product_name}科技',
        f'绿色{product_name}工业',
    ]

    random.seed(hash(product_name) % 10000)

    for i, base in enumerate(base_names):
        city = cities[i % len(cities)]
        suffix = enterprise_suffixes[i % len(enterprise_suffixes)]
        capital = random.choice([500, 1000, 2000, 5000, 10000])
        patents = random.randint(0, 50)
        mock_enterprises.append({
            'name': f'{city}{base}{suffix}',
            'source': 'mock',
            'city': city,
            'registered_capital': capital,
            'business_scope': f'主营{product_name}相关产品的研发、生产、销售及技术服务',
            'patent_count': patents,
            'credit_score': round(random.uniform(65, 95), 1),
            'is_green_factory': random.choice([True, False]),
            'contact': f'联系人{i+1}',
            'phone': f'0755-{random.randint(10000000, 99999999)}',
            'registration_no': f'91440{random.randint(100000000, 999999999)}',
            'established_year': random.randint(2005, 2020),
        })

    return mock_enterprises


def _score_candidate(candidate: Dict, product_name: str) -> Dict:
    """
    计算候选企业的匹配度评分。
    需求: 37.3, 37.4, 37.5
    """
    score = 0.0

    # 经营范围匹配度（0-40分）
    scope = candidate.get('business_scope', '')
    scope_score = 0
    for kw in product_name:
        if kw in scope:
            scope_score += 5
    scope_score = min(40, scope_score)
    score += scope_score

    # 注册资本规模（0-20分）
    capital = candidate.get('registered_capital', 0)
    if capital >= 5000:
        score += 20
    elif capital >= 1000:
        score += 15
    elif capital >= 500:
        score += 10
    else:
        score += 5

    # 专利数量（0-20分）
    patents = candidate.get('patent_count', 0)
    score += min(20, patents * 2)

    # 信用分（0-10分）
    credit = candidate.get('credit_score', 70)
    credit_bonus = min(10, max(0, (credit - 60) / 4))
    score += credit_bonus

    # 绿色工厂加分（0-10分）
    if candidate.get('is_green_factory'):
        score += 10

    # 内部企业加分（已在平台注册）
    if candidate.get('source') == 'internal':
        score += 5

    candidate['match_score'] = round(min(100, score), 1)
    candidate['match_level'] = (
        '高度匹配' if score >= 70 else
        ('较好匹配' if score >= 50 else '一般匹配')
    )
    return candidate


# ── 招商任务管理 ──────────────────────────────────────────────────────────

def create_recruitment_task(task_data: Dict) -> RecruitmentTask:
    """
    从招商建议创建招商任务。
    需求: 34.6, 34.7, 38.1
    """
    task = RecruitmentTask(
        task_name=task_data.get('task_name', f'招商任务-{task_data.get("target_product", "")}'),
        target_product=task_data.get('target_product'),
        target_enterprise_name=task_data.get('target_enterprise_name'),
        target_enterprise_location=task_data.get('target_enterprise_location'),
        assigned_to=task_data.get('assigned_to'),
        assigned_by=task_data.get('assigned_by'),
        priority=task_data.get('priority', 'normal'),
        status='pending',
        progress_notes=task_data.get('progress_notes'),
        deadline=task_data.get('deadline'),
    )
    db.session.add(task)
    db.session.commit()
    logger.info(f"[RecruitmentService] 创建招商任务: {task.task_name}")
    return task


def get_recruitment_tasks(status: Optional[str] = None, page: int = 1, per_page: int = 20) -> Dict:
    """获取招商任务列表。需求: 38.2"""
    q = RecruitmentTask.query
    if status:
        q = q.filter(RecruitmentTask.status == status)
    total = q.count()
    tasks = q.order_by(RecruitmentTask.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        'total': total,
        'page': page,
        'per_page': per_page,
        'tasks': [_task_to_dict(t) for t in tasks],
    }


def update_recruitment_task(task_id: int, update_data: Dict) -> Optional[RecruitmentTask]:
    """更新招商任务进度。需求: 38.3"""
    task = RecruitmentTask.query.get(task_id)
    if not task:
        return None
    for field in ('status', 'progress_notes', 'priority', 'deadline'):
        if field in update_data:
            setattr(task, field, update_data[field])
    task.updated_at = datetime.utcnow()
    db.session.commit()
    return task


def generate_recruitment_list() -> Dict:
    """
    生成完整招商清单（缺口分析 + 建议 + 潜在企业）。
    需求: 36.4, 36.5, 36.6, 36.7
    """
    gaps = analyze_supply_chain_gaps()
    result = []
    for gap in gaps:
        enterprises = recommend_potential_enterprises(gap)
        result.append({
            'gap': gap,
            'potential_enterprises': enterprises[:5],
        })
    return {
        'total_gaps': len(gaps),
        'items': result,
        'generated_at': datetime.utcnow().isoformat(),
    }


def track_task_progress(task_id: int) -> Optional[Dict]:
    """
    跟踪招商任务进展，返回任务详情及进展历史。
    需求: 38.5, 38.6, 38.7
    """
    task = RecruitmentTask.query.get(task_id)
    if not task:
        return None

    # 检查是否逾期
    is_overdue = False
    days_until_deadline = None
    if task.deadline:
        today = date.today()
        delta = (task.deadline - today).days
        days_until_deadline = delta
        is_overdue = delta < 0 and task.status not in ('signed', 'failed')

    STATUS_LABELS = {
        'pending': '待跟进',
        'contacted': '已联系',
        'negotiating': '洽谈中',
        'signed': '已签约',
        'failed': '已终止',
    }
    PRIORITY_LABELS = {'high': '高优先级', 'normal': '普通', 'low': '低优先级'}

    return {
        **_task_to_dict(task),
        'status_label': STATUS_LABELS.get(task.status, task.status),
        'priority_label': PRIORITY_LABELS.get(task.priority, task.priority),
        'is_overdue': is_overdue,
        'days_until_deadline': days_until_deadline,
        'assignee_name': task.assignee.name if task.assignee else None,
        'assigner_name': task.assigner.name if task.assigner else None,
    }


def notify_overdue_tasks() -> int:
    """
    检查逾期未完成的招商任务并发送提醒。
    需求: 38.8
    """
    from app.services.alert_notifier import send_message
    today = date.today()
    overdue_tasks = RecruitmentTask.query.filter(
        RecruitmentTask.deadline < today,
        RecruitmentTask.status.notin_(['signed', 'failed']),
    ).all()

    notified = 0
    for task in overdue_tasks:
        # 通知接收人
        if task.assigned_to:
            send_message(
                recipient_id=task.assigned_to,
                message_type='system',
                title=f'招商任务逾期提醒：{task.task_name}',
                content=f'招商任务"{task.task_name}"已于{task.deadline}截止，请尽快处理或更新状态。',
                link_url='/recruitment/tasks',
                priority='high',
            )
        # 通知派单人
        if task.assigned_by and task.assigned_by != task.assigned_to:
            send_message(
                recipient_id=task.assigned_by,
                message_type='system',
                title=f'招商任务逾期提醒：{task.task_name}',
                content=f'您派发的招商任务"{task.task_name}"已逾期，当前状态：{task.status}。',
                link_url='/recruitment/tasks',
                priority='high',
            )
        notified += 1

    logger.info(f"[RecruitmentService] 逾期任务提醒：共{notified}个任务")
    return notified


def _task_to_dict(task: RecruitmentTask) -> Dict:
    return {
        'id': task.id,
        'task_name': task.task_name,
        'target_product': task.target_product,
        'target_enterprise_name': task.target_enterprise_name,
        'target_enterprise_location': task.target_enterprise_location,
        'priority': task.priority,
        'status': task.status,
        'progress_notes': task.progress_notes,
        'deadline': task.deadline.isoformat() if task.deadline else None,
        'created_at': task.created_at.isoformat() if task.created_at else None,
        'updated_at': task.updated_at.isoformat() if task.updated_at else None,
        'assigned_to': task.assigned_to,
        'assigned_by': task.assigned_by,
    }

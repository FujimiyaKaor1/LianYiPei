import hashlib
import re
from datetime import date, datetime

from flask import Blueprint, render_template, request, jsonify, session
from flask_login import current_user
from app.authz import role_required
from app.services.matcher import match_suppliers, DEFAULT_WEIGHTS
from app.services.intent_parser import extract_weights_from_nl
from app.models import Enterprise

match = Blueprint('match', __name__)


def _merge_dynamic_weights(dynamic_weights):
    """将 Ollama 返回的部分维度权重合并进 DEFAULT_WEIGHTS 并归一化。"""
    if not isinstance(dynamic_weights, dict) or not dynamic_weights:
        return None
    merged = dict(DEFAULT_WEIGHTS)
    for k, v in dynamic_weights.items():
        if k in merged and isinstance(v, (int, float)):
            merged[k] = float(v)
    total_w = sum(merged.values()) or 1.0
    return {k: v / total_w for k, v in merged.items()}


def _guard_clean_product_keyword(extracted: str, user_text: str, max_len: int = 10) -> str:
    """
    兜底清洗：保证用于召回的 product 尽量是短名词。
    模型若返回「离我最近的电机」等长句，压缩为「电机」；过长或空则取用户原文逗号首段后再尝试截断。
    """
    raw = (extracted or "").strip()
    fallback_clause = user_text.replace("，", ",").split(",")[0].strip()

    if len(raw) > max_len or not raw:
        raw = fallback_clause

    # 去掉句首常见动词/套话（单次）
    raw = re.sub(
        r"^[\s，,]*(找|需要|想要|想买|求购|采购|帮找|有没有|哪家|给我)?(一?(家|个|几处|几家))?",
        "",
        raw,
        count=1,
    )
    raw = raw.strip()

    # 「的」字后较短尾巴往往是核心名词（如：离我最近的电机 → 电机）
    if len(raw) > max_len and "的" in raw:
        tail = raw.rsplit("的", 1)[-1].strip()
        if 1 <= len(tail) <= max_len * 2:
            raw = tail

    raw = raw.strip()
    if len(raw) > max_len or not raw:
        raw = fallback_clause
        if len(raw) > max_len and "的" in raw:
            tail = raw.rsplit("的", 1)[-1].strip()
            if 1 <= len(tail) <= max_len * 2:
                raw = tail

    raw = raw.strip()
    if not raw:
        raw = user_text[:500].strip()
    return raw


# ---------------------------------------------------------------------------
# Intent recognition engine (keyword-based; upgrade to LLM later)
# ---------------------------------------------------------------------------

INTENT_RULES = [
    {
        'keywords': ['距离近', '近一点', '近的', '同城', '本地', '附近', '最近'],
        'action': 'boost_distance',
        'weight_delta': {'distance': 0.20},
        'reply': '好的，已优先考虑距离因素，为您重新排序。距离近的供应商会排在前面。',
    },
    {
        'keywords': ['便宜', '价格低', '性价比', '成本', '省钱', '实惠'],
        'action': 'boost_capacity',
        'weight_delta': {'capacity': 0.15, 'product': -0.05},
        'reply': '好的，已为您优先推荐产能充足（通常报价更优）的供应商。',
    },
    {
        'keywords': ['急单', '加急', '紧急', '赶工', '快速交付', '着急'],
        'action': 'filter_capacity',
        'weight_delta': {'capacity': 0.20},
        'filters': {'min_capacity': 80},
        'reply': '好的，已筛选产能较高、能接急单的供应商，并提升产能权重。',
    },
    {
        'keywords': ['专利', '技术强', '研发', '技术实力', '有专利', '创新'],
        'action': 'boost_tech',
        'weight_delta': {'tech': 0.25},
        'filters': {'min_patent': 1},
        'reply': '好的，已优先推荐拥有专利的技术型企业，技术匹配度权重已提升。',
    },
    {
        'keywords': ['合作过', '老供应商', '历史', '信任', '熟悉的', '合作'],
        'action': 'boost_history',
        'weight_delta': {'history': 0.25},
        'reply': '好的，已优先展示有过历史合作记录的供应商。',
    },
    {
        'keywords': ['信用好', '信誉', '信用高', '可靠', '靠谱'],
        'action': 'filter_credit',
        'weight_delta': {},
        'filters': {'min_credit': 80},
        'reply': '好的，已筛选信用评分80分以上的优质供应商。',
    },
    {
        'keywords': ['产能大', '大批量', '量大', '规模大', '产能高'],
        'action': 'boost_capacity_hard',
        'weight_delta': {'capacity': 0.25},
        'filters': {'min_capacity': 60},
        'reply': '好的，已优先推荐产能较大的供应商，适合大批量采购。',
    },
    {
        'keywords': ['环保', '低碳', '绿色', '节能', '清洁能源', '碳排放', '碳中和', '减碳'],
        'action': 'boost_green',
        'weight_delta': {'green': 0.30},
        'filters': {},
        'reply': '好的，已启用绿色低碳优先模式，绿色匹配度权重大幅提升。优先推荐绿色工厂和低碳排放企业。',
    },
    {
        'keywords': ['绿色工厂', '绿色认证', '认证企业'],
        'action': 'filter_green',
        'weight_delta': {'green': 0.25},
        'filters': {'green_only': True},
        'reply': '好的，已筛选出具有绿色工厂认证的企业。',
    },
    {
        'keywords': ['重置', '恢复默认', '清除偏好', '重新来', '初始'],
        'action': 'reset',
        'reply': '好的，已恢复为默认匹配权重。',
    },
]


def _parse_intent(user_msg):
    """Parse user message and return (action, weight_delta, filters, reply)."""
    msg = user_msg.strip().lower()
    for rule in INTENT_RULES:
        for kw in rule['keywords']:
            if kw in msg:
                return (
                    rule['action'],
                    rule.get('weight_delta', {}),
                    rule.get('filters', {}),
                    rule['reply'],
                )
    return None, {}, {}, None


def _build_help_reply():
    return (
        '我是链易配AI助手，可以帮您调整匹配偏好。试试对我说：\n'
        '• "距离近的" — 优先推荐附近供应商\n'
        '• "便宜一点" — 优先推荐性价比高的\n'
        '• "能接急单" — 筛选产能充足的企业\n'
        '• "有专利的" — 优先技术型企业\n'
        '• "合作过的" — 优先历史合作伙伴\n'
        '• "信用好的" — 筛选高信用企业\n'
        '• "重置" — 恢复默认权重'
    )

def _get_industry_codes():
    return [
        ('', '请选择（可选）'),
        ('C34', 'C34 通用设备制造业'),
        ('C35', 'C35 专用设备制造业'),
        ('C36', 'C36 汽车制造业'),
        ('C37', 'C37 电气机械和器材制造业'),
        ('C38', 'C38 计算机、通信和电子设备'),
        ('C39', 'C39 仪器仪表制造业'),
        ('C33', 'C33 金属制品业'),
        ('C32', 'C32 黑色金属冶炼和压延'),
    ]

@match.route('/', methods=['GET'])
@role_required('enterprise')
def index():
    from app.routes.main import _render_spa
    return _render_spa()

@match.route('/api', methods=['POST'])
@role_required('enterprise')
def api_match():
    """匹配接口，返回结果包含五维得分明细"""
    data = request.get_json() or {}
    product_name = data.get('product_name', '').strip()
    industry_code = data.get('industry_code')
    if not product_name and not industry_code:
        return jsonify({'error': '缺少产品名称或行业编码'}), 400

    quantity = data.get('quantity', 100)
    lat = data.get('latitude')
    lng = data.get('longitude')
    sort_by = data.get('sort_by', 'score')

    demand_location = None
    if lat and lng:
        demand_location = {'lat': float(lat), 'lng': float(lng)}

    demand_ent_id = current_user.id if current_user.is_authenticated else None

    label_types = data.get('label_types') or None

    results = match_suppliers(
        demand_product=product_name or None,
        demand_location=demand_location,
        demand_quantity=int(quantity),
        demand_ent_id=demand_ent_id,
        demand_industry_code=industry_code,
        sort_by=sort_by,
        label_types=label_types,
    )

    return jsonify({'results': results})


@role_required('enterprise')
def ai_match_view():
    """
    POST /api/match/ai（在 api 蓝图注册）：Ollama qwen2.5 提取权重 → match_suppliers。
    JSON: { "text": "...", "quantity"?, "industry_code"?, "latitude"?, "longitude"?, "sort_by"?, "green_priority"? }
    """
    data = request.get_json(silent=True) or {}
    user_text = (data.get('text') or '').strip()
    if not user_text:
        return jsonify({'error': '缺少 text'}), 400

    ai_params = extract_weights_from_nl(user_text)
    raw_product = ai_params.get('product')
    if isinstance(raw_product, str):
        target_product = raw_product.strip()
    elif raw_product is not None:
        target_product = str(raw_product).strip()
    else:
        target_product = ''

    target_product = _guard_clean_product_keyword(target_product, user_text)
    ai_params['product'] = target_product

    merged = _merge_dynamic_weights(ai_params.get('weights'))
    if merged is not None:
        session['chat_weights'] = merged

    quantity = data.get('quantity', 100)
    sort_by = data.get('sort_by', 'score')
    industry_code = data.get('industry_code')

    demand_location = None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat is not None and lng is not None:
        try:
            demand_location = {'lat': float(lat), 'lng': float(lng)}
        except (TypeError, ValueError):
            demand_location = None
    elif current_user.is_authenticated and getattr(current_user, 'latitude', None) is not None and getattr(
        current_user, 'longitude', None
    ) is not None:
        demand_location = {'lat': float(current_user.latitude), 'lng': float(current_user.longitude)}

    demand_ent_id = current_user.id if current_user.is_authenticated else None

    if not target_product and not industry_code:
        return jsonify({
            'error': '未能识别产品或行业：请补充 industry_code，或改写需求描述',
            'ai_intent': ai_params,
        }), 400

    results = match_suppliers(
        demand_product=target_product or None,
        demand_location=demand_location,
        demand_quantity=int(quantity),
        demand_ent_id=demand_ent_id,
        demand_industry_code=industry_code or None,
        sort_by=sort_by,
        custom_weights=merged,
        filters=None,
        green_priority=bool(data.get('green_priority', False)),
    )

    return jsonify({
        'status': 'success',
        'results': results,
        'ai_intent': ai_params,
        'parsed_intent': ai_params,
    })


@match.route('/api/ai-match', methods=['POST'])
@role_required('enterprise')
def api_ai_match():
    """自然语言匹配：Ollama 提取 product + weights → match_suppliers 召回与重排（含雷达维度得分）。"""
    data = request.get_json() or {}
    query = (
        (data.get('query') or data.get('message') or data.get('natural_language') or '')
        .strip()
    )
    if not query:
        return jsonify({'error': '缺少自然语言 query（可用字段：query / message / natural_language）'}), 400

    intent = extract_weights_from_nl(query)
    product_name = (intent.get('product') or '').strip()
    if not product_name and data.get('use_full_query_as_product', True):
        product_name = query[:500]
    product_name = _guard_clean_product_keyword(product_name, query)
    intent['product'] = product_name

    industry_code = data.get('industry_code')
    quantity = data.get('quantity', 100)
    sort_by = data.get('sort_by', 'score')

    demand_location = None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat is not None and lng is not None:
        try:
            demand_location = {'lat': float(lat), 'lng': float(lng)}
        except (TypeError, ValueError):
            demand_location = None
    elif current_user.is_authenticated and getattr(current_user, 'latitude', None) and getattr(
        current_user, 'longitude', None
    ):
        demand_location = {'lat': float(current_user.latitude), 'lng': float(current_user.longitude)}

    demand_ent_id = current_user.id if current_user.is_authenticated else None

    merged = _merge_dynamic_weights(intent.get('weights'))
    custom_weights = merged if merged is not None else dict(DEFAULT_WEIGHTS)

    if not product_name and not industry_code:
        return jsonify({
            'error': '未能识别产品或行业：请补充 industry_code，或改写需求描述',
            'parsed': intent,
            'parsed_intent': intent,
        }), 400

    results = match_suppliers(
        demand_product=product_name or None,
        demand_location=demand_location,
        demand_quantity=int(quantity),
        demand_ent_id=demand_ent_id,
        demand_industry_code=industry_code or None,
        sort_by=sort_by,
        custom_weights=merged,
        filters=None,
        green_priority=bool(data.get('green_priority', False)),
    )

    session['chat_weights'] = dict(custom_weights)

    total_w = sum(custom_weights.values()) or 1.0
    weights_pct = {k: round(v / total_w * 100) for k, v in custom_weights.items()}

    return jsonify({
        'results': results,
        'product': product_name,
        'weights': custom_weights,
        'weights_pct': weights_pct,
        'parsed_intent': intent,
        'llm': {
            'error': None,
            'raw': None,
        },
    })


@match.route('/api/ai_match', methods=['POST'])
@role_required('enterprise')
def ai_match_endpoint():
    """AI 智能匹配：Ollama 意图解析 + 动态权重匹配。JSON: query（或 text）、quantity、industry_code 等可选。"""
    data = request.get_json(silent=True) or {}
    user_query = (data.get('query') or data.get('text') or '').strip()
    if not user_query:
        return jsonify({'error': '缺少 query'}), 400

    intent = extract_weights_from_nl(user_query)
    merged = _merge_dynamic_weights(intent.get('weights'))
    if merged is not None:
        session['chat_weights'] = merged

    product_name = (intent.get('product') or '').strip() or user_query[:500]
    product_name = _guard_clean_product_keyword(product_name, user_query)
    intent['product'] = product_name
    industry_code = data.get('industry_code')
    quantity = data.get('quantity', 100)
    sort_by = data.get('sort_by', 'score')

    demand_location = None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat is not None and lng is not None:
        try:
            demand_location = {'lat': float(lat), 'lng': float(lng)}
        except (TypeError, ValueError):
            demand_location = None
    elif current_user.is_authenticated and getattr(current_user, 'latitude', None) and getattr(
        current_user, 'longitude', None
    ):
        demand_location = {'lat': float(current_user.latitude), 'lng': float(current_user.longitude)}

    if not product_name and not industry_code:
        return jsonify({
            'error': '未能识别产品或行业：请补充 industry_code，或改写需求描述',
            'parsed_intent': intent,
        }), 400

    results = match_suppliers(
        demand_product=product_name or None,
        demand_location=demand_location,
        demand_quantity=int(quantity),
        demand_ent_id=current_user.id,
        demand_industry_code=industry_code or None,
        sort_by=sort_by,
        weights=merged,
        filters=None,
        green_priority=bool(data.get('green_priority', False)),
    )

    return jsonify({
        'results': results,
        'parsed_intent': intent,
    })


@match.route('/api/dimensions/<int:enterprise_id>', methods=['GET'])
@role_required('enterprise')
def api_dimensions(enterprise_id):
    """获取指定企业的五维匹配得分（前端按需加载）"""
    enterprise = Enterprise.query.get_or_404(enterprise_id)
    return jsonify({
        'id': enterprise.id,
        'name': enterprise.name,
        'patent_count': enterprise.patent_count or 0,
        'tech_keywords': enterprise.tech_keywords or '',
        'capacity': enterprise.capacity,
        'credit_score': enterprise.credit_score,
    })


@match.route('/api/chat', methods=['POST'])
@role_required('enterprise')
def api_chat():
    """AI供需对话助手：意图识别 → 调整权重 → 重新匹配 → 返回结果。

    Performance: when the action only changes weights (no new DB filters),
    returns ``local_resort: true`` so the client can re-sort in-place using
    the raw dimension scores it already holds — skipping a full DB round-trip.
    """
    data = request.get_json() or {}
    user_msg = (data.get('message') or '').strip()
    if not user_msg:
        return jsonify({'error': '请输入内容'}), 400

    product_name = data.get('product_name', '').strip()
    industry_code = data.get('industry_code')
    quantity = data.get('quantity', 100)

    chat_weights = session.get('chat_weights', dict(DEFAULT_WEIGHTS))
    chat_filters = session.get('chat_filters', {})

    action, weight_delta, new_filters, reply = _parse_intent(user_msg)

    has_new_filters = False
    if action == 'reset':
        chat_weights = dict(DEFAULT_WEIGHTS)
        has_new_filters = bool(chat_filters)
        chat_filters = {}
    elif action:
        for k, v in weight_delta.items():
            chat_weights[k] = max(0.05, chat_weights.get(k, 0.15) + v)
        if new_filters:
            has_new_filters = True
            chat_filters.update(new_filters)
    else:
        reply = _build_help_reply()

    session['chat_weights'] = chat_weights
    session['chat_filters'] = chat_filters

    total_w = sum(chat_weights.values()) or 1.0
    weights_pct = {k: round(v / total_w * 100) for k, v in chat_weights.items()}
    weights_raw = {k: round(v / total_w, 4) for k, v in chat_weights.items()}

    can_local_resort = action and not has_new_filters and bool(data.get('has_local_data'))

    results = None
    if not can_local_resort and (product_name or industry_code):
        demand_location = None
        if current_user.is_authenticated and current_user.latitude and current_user.longitude:
            demand_location = {'lat': current_user.latitude, 'lng': current_user.longitude}
        demand_ent_id = current_user.id if current_user.is_authenticated else None

        results = match_suppliers(
            demand_product=product_name or None,
            demand_location=demand_location,
            demand_quantity=int(quantity),
            demand_ent_id=demand_ent_id,
            demand_industry_code=industry_code or None,
            sort_by='score',
            custom_weights=chat_weights,
            filters=chat_filters,
        )

    return jsonify({
        'reply': reply,
        'action': action,
        'results': results,
        'weights': weights_pct,
        'weights_raw': weights_raw,
        'filters': chat_filters,
        'local_resort': can_local_resort,
    })


@match.route('/api/feedback', methods=['POST'])
@role_required('enterprise')
def api_feedback():
    """反馈上报接口：记录用户点击/联系供应商行为，用于Bandit学习"""
    data = request.get_json() or {}
    supplier_id = data.get('supplier_id')
    product_name = data.get('product_name', '')
    clicked = data.get('clicked', False)
    contacted = data.get('contacted', False)
    dim_scores = data.get('dim_scores', {})
    match_score = data.get('match_score')
    session_id = data.get('session_id')
    
    if not supplier_id:
        return jsonify({'error': '缺少supplier_id'}), 400
    
    buyer_id = current_user.id if current_user.is_authenticated else None
    if not buyer_id:
        return jsonify({'error': '请先登录'}), 401
    
    from app.models import MatchFeedback
    from app import db

    if not session_id:
        session_id = hashlib.md5(f'{buyer_id}{product_name}'.encode()).hexdigest()[:16]

    fb_status = None
    if contacted:
        fb_status = 'contacted'
    elif clicked:
        fb_status = 'clicked'

    feedback = MatchFeedback(
        buyer_id=buyer_id,
        supplier_id=supplier_id,
        product_name=product_name,
        clicked=bool(clicked),
        contacted=bool(contacted),
        status=fb_status,
        dim_scores=dim_scores,
        match_score=float(match_score) if match_score else None,
        session_id=session_id,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent', '')[:255]
    )
    db.session.add(feedback)
    db.session.commit()
    
    try:
        from app.services.bandit import _get_bandit
        bandit = _get_bandit()
        bandit.log_feedback(
            ent_id=buyer_id,
            clicked=bool(clicked or contacted),
            dim_scores=dim_scores
        )
    except Exception:
        pass
    
    return jsonify({'success': True, 'feedback_id': feedback.id})


@match.route('/api/feedback/batch', methods=['POST'])
@role_required('enterprise')
def api_feedback_batch():
    """批量反馈上报：用于页面离开时上报未点击的供应商（负样本）"""
    data = request.get_json() or {}
    product_name = data.get('product_name', '')
    session_id = data.get('session_id')
    results = data.get('results', [])
    
    buyer_id = current_user.id if current_user.is_authenticated else None
    if not buyer_id:
        return jsonify({'error': '请先登录'}), 401
    
    if not results:
        return jsonify({'success': True, 'count': 0})
    
    from app.models import MatchFeedback
    from app import db

    if not session_id:
        session_id = hashlib.md5(f'{buyer_id}{product_name}'.encode()).hexdigest()[:16]

    count = 0
    for r in results:
        supplier_id = r.get('supplier_id') or r.get('id')
        if not supplier_id:
            continue
        dim_scores = r.get('dim_scores') or r.get('dimensions', {})
        if isinstance(dim_scores, dict):
            dim_scores = {k: v.get('score', 0) if isinstance(v, dict) else v for k, v in dim_scores.items()}
        
        feedback = MatchFeedback(
            buyer_id=buyer_id,
            supplier_id=supplier_id,
            product_name=product_name,
            clicked=False,
            contacted=False,
            dim_scores=dim_scores,
            match_score=r.get('score'),
            session_id=session_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255]
        )
        db.session.add(feedback)
        count += 1
    
    db.session.commit()
    
    return jsonify({'success': True, 'count': count})


def _latest_match_feedback(buyer_id, supplier_id, product_name):
    from app.models import MatchFeedback

    q = MatchFeedback.query.filter_by(buyer_id=buyer_id, supplier_id=supplier_id)
    if product_name:
        q = q.filter(MatchFeedback.product_name == product_name)
    return q.order_by(MatchFeedback.created_at.desc()).first()


@role_required('enterprise')
def api_inquiry_send():
    """POST /api/inquiry/send：创建询盘并将对应 match_feedback 置为 contacted。"""
    from app.models import Inquiry, MatchFeedback, Message
    from app import db

    data = request.get_json() or {}
    supplier_id = data.get('supplier_id')
    product_name = (data.get('product_name') or '').strip() or ''
    content = (data.get('content') or '').strip() or '请通过链易配平台联系，沟通合作细节。'
    dim_scores = data.get('dim_scores') or {}
    match_score = data.get('match_score')
    sess_id = data.get('session_id')

    if not supplier_id:
        return jsonify({'error': '缺少 supplier_id'}), 400

    buyer_id = current_user.id if current_user.is_authenticated else None
    if not buyer_id:
        return jsonify({'error': '请先登录'}), 401

    try:
        supplier_id = int(supplier_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'supplier_id 无效'}), 400

    if supplier_id == buyer_id:
        return jsonify({'error': '不能向本企业发起询盘'}), 400

    if not sess_id:
        sess_id = hashlib.md5(f'{buyer_id}{product_name}'.encode()).hexdigest()[:16]

    feedback = _latest_match_feedback(buyer_id, supplier_id, product_name)
    if feedback is None:
        feedback = MatchFeedback(
            buyer_id=buyer_id,
            supplier_id=supplier_id,
            product_name=product_name or None,
            clicked=True,
            contacted=True,
            status='contacted',
            dim_scores=dim_scores,
            match_score=float(match_score) if match_score is not None else None,
            session_id=sess_id,
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
        db.session.add(feedback)
        db.session.flush()
    else:
        feedback.contacted = True
        feedback.clicked = True
        feedback.status = 'contacted'
        if dim_scores:
            feedback.dim_scores = dim_scores
        if match_score is not None:
            try:
                feedback.match_score = float(match_score)
            except (TypeError, ValueError):
                pass
        feedback.updated_at = datetime.utcnow()

    inquiry = Inquiry(
        buyer_id=buyer_id,
        seller_id=supplier_id,
        product_name=product_name or None,
        content=content,
        status='sent',
        match_feedback_id=feedback.id,
    )
    db.session.add(inquiry)
    db.session.flush() # To get inquiry.id

    # 创建消息通知卖家：收件方是卖方，应出现在「销售模式」收件箱（采购/销售按收件企业视角区分）
    buyer_name = current_user.name or "某采购商"
    msg = Message(
        recipient_id=supplier_id,
        message_type='inquiry',
        title=f"新询盘: {product_name or '精密零部件'}",
        content=f"{buyer_name} 向您发起了关于 {product_name or '精密零部件'} 的轻量级询盘，请及时评估商机。",
        link_url=f"/sales-console?inquiry_id={inquiry.id}&buyer_id={buyer_id}&product_name={product_name or ''}",
        priority='high',
        mode='sales',
    )
    db.session.add(msg)
    db.session.commit()

    try:
        from app.services.bandit import _get_bandit

        bandit = _get_bandit()
        bandit.log_feedback(
            ent_id=buyer_id,
            clicked=True,
            dim_scores=feedback.dim_scores or dim_scores,
        )
    except Exception:
        pass

    return jsonify(
        {
            'success': True,
            'inquiry_id': inquiry.id,
            'match_feedback_id': feedback.id,
        }
    )


@role_required('enterprise')
def api_inquiry_sign():
    """POST /api/inquiry/sign：签署合作协议 → intent_signed、模拟链上 Hash、RL 奖励（一次）。"""
    from app.models import Inquiry, MatchFeedback
    from app import db
    from app.services.rl_signal import update_rl_signal

    data = request.get_json() or {}
    match_feedback_id = data.get('match_feedback_id')
    supplier_id = data.get('supplier_id')
    product_name = (data.get('product_name') or '').strip() or ''

    buyer_id = current_user.id if current_user.is_authenticated else None
    if not buyer_id:
        return jsonify({'error': '请先登录'}), 401

    fb = None
    if match_feedback_id is not None:
        try:
            mfid = int(match_feedback_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'match_feedback_id 无效'}), 400
        fb = MatchFeedback.query.filter_by(id=mfid, buyer_id=buyer_id).first()
    elif supplier_id is not None:
        try:
            sid = int(supplier_id)
        except (TypeError, ValueError):
            return jsonify({'error': 'supplier_id 无效'}), 400
        fb = _latest_match_feedback(buyer_id, sid, product_name)
    else:
        return jsonify({'error': '需要 match_feedback_id 或 supplier_id'}), 400

    if not fb:
        return jsonify({'error': '未找到匹配反馈记录'}), 404

    if fb.status == 'intent_signed' and fb.rl_reward_applied:
        return jsonify(
            {
                'success': True,
                'match_feedback_id': fb.id,
                'blockchain_evidence_hash': fb.blockchain_evidence_hash,
                'already_signed': True,
            }
        )

    today_iso = date.today().isoformat()
    evidence = hashlib.sha256(
        f'{fb.id}:{buyer_id}:{fb.supplier_id}:{fb.product_name or ""}:{today_iso}'.encode()
    ).hexdigest()

    fb.status = 'intent_signed'
    fb.clicked = True
    fb.contacted = True
    fb.blockchain_evidence_hash = evidence
    fb.updated_at = datetime.utcnow()

    if not fb.rl_reward_applied:
        update_rl_signal(fb.id, reward=1.0, buyer_id=buyer_id, supplier_id=fb.supplier_id)
        fb.rl_reward_applied = True

    inq = (
        Inquiry.query.filter_by(match_feedback_id=fb.id)
        .order_by(Inquiry.created_at.desc())
        .first()
    )
    if inq:
        inq.status = 'agreement_signed'
        inq.updated_at = datetime.utcnow()

    db.session.commit()

    try:
        from app.services.bandit import _get_bandit

        bandit = _get_bandit()
        bandit.log_feedback(ent_id=buyer_id, clicked=True, dim_scores=fb.dim_scores or {})
    except Exception:
        pass

    return jsonify(
        {
            'success': True,
            'match_feedback_id': fb.id,
            'blockchain_evidence_hash': evidence,
            'already_signed': False,
        }
    )


# ===================================================================
# 绿色低碳 API
# ===================================================================

@match.route('/api/green-priority', methods=['POST'])
@role_required('enterprise')
def api_green_priority():
    """绿色优先匹配接口"""
    data = request.get_json() or {}
    product_name = data.get('product_name', '').strip()
    industry_code = data.get('industry_code')
    quantity = data.get('quantity', 100)
    sort_by = data.get('sort_by', 'score')

    if not product_name and not industry_code:
        return jsonify({'error': '缺少产品名称或行业编码'}), 400

    demand_location = None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat and lng:
        demand_location = {'lat': float(lat), 'lng': float(lng)}
    elif current_user.is_authenticated and current_user.latitude:
        demand_location = {'lat': current_user.latitude, 'lng': current_user.longitude}

    demand_ent_id = current_user.id if current_user.is_authenticated else None
    results = match_suppliers(
        demand_product=product_name or None,
        demand_location=demand_location,
        demand_quantity=int(quantity),
        demand_ent_id=demand_ent_id,
        demand_industry_code=industry_code,
        sort_by=sort_by,
        green_priority=True,
    )
    return jsonify({'results': results, 'mode': 'green_priority'})


@match.route('/api/enterprise/<int:ent_id>/green-profile', methods=['GET'])
@role_required('enterprise')
def api_green_profile(ent_id):
    """获取企业绿色档案"""
    ent = Enterprise.query.get_or_404(ent_id)
    return jsonify({
        'id': ent.id,
        'name': ent.name,
        'is_green_factory': bool(getattr(ent, 'is_green_factory', False)),
        'green_certification': getattr(ent, 'green_certification', None) or [],
        'clean_energy_usage': float(getattr(ent, 'clean_energy_usage', 0) or 0),
        'carbon_emission_level': getattr(ent, 'carbon_emission_level', '') or '',
        'environment_protection_patents': int(getattr(ent, 'environment_protection_patents', 0) or 0),
        'green_supplier_rank': getattr(ent, 'green_supplier_rank', '') or '',
    })


@match.route('/api/carbon-estimate', methods=['POST'])
@role_required('enterprise')
def api_carbon_estimate():
    """碳排放估算接口"""
    from app.services.matcher import estimate_carbon
    data = request.get_json() or {}
    supplier_id = data.get('supplier_id')
    quantity = data.get('quantity', 100)

    if not supplier_id:
        return jsonify({'error': '缺少 supplier_id'}), 400

    supplier = Enterprise.query.get_or_404(supplier_id)
    demand_location = None
    lat, lng = data.get('latitude'), data.get('longitude')
    if lat and lng:
        demand_location = {'lat': float(lat), 'lng': float(lng)}
    elif current_user.is_authenticated and current_user.latitude:
        demand_location = {'lat': current_user.latitude, 'lng': current_user.longitude}

    carbon = estimate_carbon(supplier, demand_location, int(quantity))
    return jsonify({'supplier_id': supplier_id, 'quantity': quantity, 'carbon': carbon})


@match.route('/api/alert/green-risk/list', methods=['GET'])
@role_required('admin')
def api_green_risk_list():
    """获取绿色风险预警列表"""
    from app.models import Alert
    alerts = Alert.query.filter(
        Alert.is_active == True,
        Alert.dimension == 'green'
    ).order_by(Alert.created_at.desc()).limit(20).all()

    return jsonify({'alerts': [{
        'id': a.id,
        'product_name': a.product_name,
        'message': a.message,
        'level': a.level,
        'suggestion': a.suggestion,
        'created_at': a.created_at.isoformat() if a.created_at else None,
    } for a in alerts]})


@match.route('/api/enterprise/<int:enterprise_id>/capacity-signal', methods=['GET'])
@role_required('enterprise')
def api_capacity_signal(enterprise_id):
    """
    获取指定供应商的产能信号。
    需求: 17.1, 17.2, 17.3, 17.4, 17.5, 17.7
    """
    from app.services.matcher import get_capacity_signal
    supplier = Enterprise.query.get_or_404(enterprise_id)
    signal = get_capacity_signal(supplier)
    return jsonify({
        'enterprise_id': enterprise_id,
        'name': supplier.name,
        'capacity_signal': signal,
        'current_orders': supplier.current_orders,
        'max_capacity': supplier.max_capacity,
        'last_order_update': supplier.last_order_update.isoformat() if supplier.last_order_update else None,
    })


@match.route('/result-page')
@role_required('enterprise')
def match_result_page():
    """服务端匹配结果列表示例页（含「查看地理距离」）。SPA 主流程外可选入口。"""
    from app.services.matcher import get_capacity_signal
    suppliers = (
        Enterprise.query.filter(Enterprise.id != current_user.id)
        .order_by(Enterprise.id)
        .limit(30)
        .all()
    )
    # 为每个供应商附加产能信号
    for s in suppliers:
        s._capacity_signal = get_capacity_signal(s)
    return render_template('match_result.html', suppliers=suppliers, buyer=current_user)

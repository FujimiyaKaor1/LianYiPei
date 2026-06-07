import os
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, current_app
from flask_login import current_user, login_required
from app.models import Enterprise, Inquiry, Product, Alert
from app.authz import role_required, user_effective_role, user_session_role

# Enterprise 上 JSON 列（qualifications、data_auth、cooperation_cases、patents、extras、credit_score_events）
# 的读写约定与 10 表清单见 app.enterprise_json_helpers

main = Blueprint('main', __name__)


def _get_initial_data():
    from app.models import Transaction, Alert
    enterprise_count = Enterprise.query.count()
    supply_count = Inquiry.query.filter(
        Inquiry.direction == "supply", Inquiry.status.in_(("open", "active"))
    ).count()
    demand_count = Inquiry.query.filter(
        Inquiry.direction == "demand", Inquiry.status.in_(("open", "active"))
    ).count()
    product_count = Product.query.count()
    transaction_count = Transaction.query.count()
    alert_count = Alert.query.filter_by(is_active=True).count()

    recent_supplies = (
        Inquiry.query.filter(
            Inquiry.direction == "supply", Inquiry.status.in_(("open", "active"))
        )
        .order_by(Inquiry.created_at.desc())
        .limit(8)
        .all()
    )
    recent_demands = (
        Inquiry.query.filter(
            Inquiry.direction == "demand", Inquiry.status.in_(("open", "active"))
        )
        .order_by(Inquiry.created_at.desc())
        .limit(8)
        .all()
    )
    recent_alerts = Alert.query.filter_by(is_active=True).order_by(Alert.created_at.desc()).limit(5).all()

    def _supply_dict(s):
        return {
            'product_name': s.product.name if s.product else (s.product_name or ''),
            'enterprise_name': s.poster.name if s.poster else '',
            'quantity': s.quantity,
            'unit': s.unit or '',
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M:%S') if getattr(s, 'created_at', None) else None,
        }

    def _alert_dict(a):
        return {
            'id': a.id,
            'level': a.level or 'red',
            'product_name': a.product_name or '',
            'message': a.message or '',
        }

    user_name = current_user.name if current_user.is_authenticated else '用户'
    user_role = user_effective_role(current_user) if current_user.is_authenticated else None
    session_role = user_session_role(current_user) if current_user.is_authenticated else None

    return {
        'enterprise_count': enterprise_count,
        'supply_count': supply_count,
        'demand_count': demand_count,
        'product_count': product_count,
        'transaction_count': transaction_count,
        'alert_count': alert_count,
        'recent_supplies': [_supply_dict(s) for s in recent_supplies],
        'recent_demands': [_supply_dict(d) for d in recent_demands],
        'recent_alerts': [_alert_dict(a) for a in recent_alerts],
        'user_name': user_name,
        'is_authenticated': current_user.is_authenticated,
        'user_role': user_role,
        'session_role': session_role,
    }


def _render_spa(title='链易配'):
    return render_template('spa.html', initial_data=_get_initial_data())


@main.route('/')
def index():
    return _render_spa('首页 - 链易配')


@main.route('/workspace')
@main.route('/workspace/')
@main.route('/workspace/<path:path>')
def workspace_spa(path=None):
    """React Shell 扩展路径：意向报价池、合作闭环、客商收藏夹等（同域 SPA）。"""
    return _render_spa('工作台 - 链易配')


@main.route('/settings')
@main.route('/settings/')
def settings_entry_alias():
    """旧路径兼容：进入 SPA 首页内的预警设置模块。"""
    return redirect('/?view=thresholds')


@main.route('/ai-query')
def ai_query_page():
    """已废弃：智能问答独立页已移除，旧链接统一回首页 SPA。"""
    return redirect(url_for('main.index'))


@main.route('/query', methods=['POST'])
def query_alias():
    """Text2SQL / 自然语言查库（仅 nl_query，无通用对话逻辑）。"""
    from app.services.llm_query import nl_query

    data = request.get_json() or {}
    question = (data.get('question') or request.form.get('question') or '').strip()
    if not question:
        return jsonify({'success': False, 'error': '请输入问题'}), 400
    return jsonify(nl_query(question))


@main.route('/clip-match')
def clip_match_page():
    return redirect(url_for('match.index'))


@main.route('/api/clip-match', methods=['POST'])
def api_clip_match():
    from app.services.clip_matcher import clip_available, match_image_to_products
    from app.models import Product
    if not clip_available():
        return jsonify({'success': False, 'error': 'CLIP 未安装。请执行: pip install open-clip-torch torch'})
    f = request.files.get('image')
    if not f:
        return jsonify({'success': False, 'error': '请上传图片'})
    import uuid
    from werkzeug.utils import secure_filename
    from flask import current_app
    ext = os.path.splitext(secure_filename(f.filename) or 'img')[1] or '.jpg'
    fname = f"clip_{uuid.uuid4().hex[:12]}{ext}"
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_dir = current_app.config.get('UPLOAD_FOLDER') or os.path.join(base, 'uploads')
    save_path = os.path.join(upload_dir, fname)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    f.save(save_path)
    try:
        products = Product.query.limit(50).all()
        texts = [f"{p.name} {p.category or ''} {p.industry_code or ''}" for p in products]
        matches = match_image_to_products(save_path, texts, top_k=5)
        return jsonify({'success': True, 'matches': matches})
    finally:
        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except:
                pass


@main.route('/map/view')
@login_required
def map_view_page():
    """高德地图对比页：厂家 vs 商家（当前登录企业）。Query: supplier_id, buyer_id（可选，默认当前用户）。"""
    supplier_id = request.args.get('supplier_id', type=int)
    buyer_id = request.args.get('buyer_id', type=int) or (
        current_user.id if getattr(current_user, 'is_authenticated', False) else None
    )
    return render_template(
        'map_view.html',
        AMAP_JS_KEY=(current_app.config.get('AMAP_JS_KEY') or '').strip(),
        AMAP_SECURITY_JS_CODE=(current_app.config.get('AMAP_SECURITY_JS_CODE') or '').strip(),
        supplier_id=supplier_id,
        buyer_id=buyer_id,
    )


# 与 alerts 蓝图 GET /api/alerts（分页 JSON）路径冲突，故使用独立路径供政府端简单列表
@main.route('/api/admin/recent-alerts')
@role_required('admin')
def api_alerts_public_path():
    alerts = Alert.query.filter_by(is_active=True).order_by(Alert.created_at.desc()).limit(20).all()
    return jsonify(
        [
            {
                'id': a.id,
                'product_name': a.product_name,
                'message': a.message,
                'level': a.level,
                'dimension': a.dimension,
                'suggestion': getattr(a, 'suggestion', None),
                'created_at': a.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            }
            for a in alerts
        ]
    )


@main.route('/api/graph/data')
@role_required('admin')
def api_graph_data_public_path():
    from app.services.graph_manager import get_full_graph

    try:
        nodes, links = get_full_graph()
        return jsonify({'nodes': nodes, 'links': links})
    except Exception as e:
        return jsonify({'error': str(e), 'nodes': [], 'links': []})


@main.route('/api/predict/risk', methods=['GET'])
@role_required('admin')
def api_predict_risk():
    from app.services.forecaster import forecast_supply_demand

    try:
        return jsonify(forecast_supply_demand(horizon=6))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@main.route('/api/enterprise/tags', methods=['GET'])
@login_required
def api_enterprise_tags():
    from app.services.profile import build_enterprise_profile

    qid = request.args.get('enterprise_id', type=int)
    role = user_effective_role(current_user)
    if role == 'enterprise':
        target_id = current_user.id
        if qid is not None and qid != current_user.id:
            return jsonify({'error': '仅可查询本企业标签'}), 403
    else:
        target_id = qid or current_user.id
    prof = build_enterprise_profile(target_id)
    return jsonify(
        {
            'enterprise_id': target_id,
            'supply_tags': prof.get('supply_tags', []),
            'demand_tags': prof.get('demand_tags', []),
        }
    )

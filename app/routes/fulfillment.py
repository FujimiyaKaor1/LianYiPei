"""
履约数据路由
- GET  /fulfillment/dashboard          - 履约数据看板
- GET  /fulfillment/cases              - 案例库管理页面
- POST /fulfillment/cases/<id>/toggle  - 切换案例公开/私密
- POST /api/fulfillment/backflow       - 触发履约数据回流（内部/合同服务调用）
- GET  /api/fulfillment/dashboard-data - 看板数据 API
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required
from app.authz import role_required
from app.models import Enterprise
from app.services.fulfillment_dashboard import (
    build_credit_trend,
    build_delivery_stats,
    build_history,
    build_score_dimensions,
)
from app.services.fulfillment_service import (
    get_all_cases, get_public_cases, toggle_case_visibility,
    trigger_fulfillment_backflow,
)

fulfillment_bp = Blueprint('fulfillment', __name__, url_prefix='/fulfillment')


# ── 履约数据看板 ──────────────────────────────────────────────────────────

@fulfillment_bp.route('/dashboard')
@role_required('enterprise')
def dashboard():
    """履约数据看板页面。需求: 3.1-3.7"""
    return render_template('fulfillment/dashboard.html')


@fulfillment_bp.route('/api/dashboard-data')
@login_required
def dashboard_data():
    """
    返回看板所需数据：
    - 最近12个月信用分趋势
    - 按时交付率 vs 行业平均
    - 信用分构成维度
    - 最近10条信用分变动记录
    """
    eid = current_user.id
    now = datetime.utcnow()
    twelve_months_ago = now - timedelta(days=365)

    trend = build_credit_trend(eid, twelve_months_ago, now)
    delivery_stats = build_delivery_stats(eid, twelve_months_ago)
    dimensions = build_score_dimensions(eid)
    history = build_history(eid)

    ent = Enterprise.query.get(eid)
    current_score = float(ent.credit_score or 60.0) if ent else 60.0

    return jsonify({
        'success': True,
        'current_score': current_score,
        'trend': trend,
        'delivery_stats': delivery_stats,
        'dimensions': dimensions,
        'history': history,
    })


# ── 案例库管理 ────────────────────────────────────────────────────────────

@fulfillment_bp.route('/cases')
@role_required('enterprise')
def cases():
    """案例库管理页面。需求: 8.1-8.7"""
    return render_template('fulfillment/cases.html')


@fulfillment_bp.route('/api/cases')
@login_required
def api_cases():
    """获取当前企业所有案例（含私密）。"""
    all_cases = get_all_cases(current_user.id)
    return jsonify({'success': True, 'cases': all_cases})


@fulfillment_bp.route('/api/cases/<int:case_id>/toggle', methods=['POST'])
@role_required('enterprise')
def toggle_case(case_id: int):
    """切换案例公开/私密。需求: 8.3"""
    data = request.get_json() or {}
    is_public = bool(data.get('is_public', False))
    ok = toggle_case_visibility(case_id, current_user.id, is_public)
    if not ok:
        return jsonify({'success': False, 'message': '案例不存在或无权限'}), 404
    return jsonify({'success': True, 'is_public': is_public})


# ── 履约数据回流 API ──────────────────────────────────────────────────────

@fulfillment_bp.route('/api/backflow', methods=['POST'])
@login_required
def api_backflow():
    """
    触发履约数据回流。
    由合同服务在合同履约完成时调用。
    需求: 6.5, 69.5, 69.6
    """
    data = request.get_json() or {}
    collaboration_code = data.get('collaboration_code', '')
    invoice_info = data.get('invoice_info', {})
    buyer_id = data.get('buyer_id')
    seller_id = data.get('seller_id')

    if not all([collaboration_code, invoice_info, buyer_id, seller_id]):
        return jsonify({'success': False, 'message': '缺少必要参数'}), 400

    result = trigger_fulfillment_backflow(
        collaboration_code=collaboration_code,
        invoice_info=invoice_info,
        buyer_id=int(buyer_id),
        seller_id=int(seller_id),
    )

    status_code = 200 if result['success'] else 500
    return jsonify(result), status_code


# ── 企业画像公开案例 API ──────────────────────────────────────────────────

@fulfillment_bp.route('/api/cases/public/<int:supplier_id>')
def api_public_cases(supplier_id: int):
    """获取供应商公开案例（企业画像页面使用）。需求: 8.7"""
    cases = get_public_cases(supplier_id)
    return jsonify({'success': True, 'cases': cases})

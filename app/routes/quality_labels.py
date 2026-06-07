"""
质量标签路由
- GET  /quality-labels/manage              - 标签管理页面
- GET  /quality-labels/grant-green         - 颁发政府绿标页面
- GET  /quality-labels/inspection          - 链主验厂管理页面
- POST /api/quality-labels/grant-green     - 颁发政府绿标
- POST /api/quality-labels/grant-inspection - 颁发验厂标签
- POST /api/quality-labels/revoke/<id>     - 撤销标签
- POST /api/quality-labels/reinspection    - 申请重新验厂
- GET  /api/quality-labels/enterprise/<id> - 获取企业标签
- POST /api/quality-labels/sync-third-party - 同步第三方评分
需求: 18.1-18.7, 54.1-54.7
"""
from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app.authz import role_required
from app.models import Enterprise
from app.services.quality_label_service import (
    apply_reinspection,
    fetch_third_party_rating,
    get_active_labels,
    get_all_labels,
    grant_government_green_label,
    grant_lead_inspection_label,
    revoke_label,
    sync_third_party_rating,
)

quality_labels_bp = Blueprint('quality_labels', __name__, url_prefix='/quality-labels')


# ── 页面路由 ──────────────────────────────────────────────────────────────

@quality_labels_bp.route('/manage')
@login_required
def manage():
    """质量标签管理页面。需求: 18.1"""
    labels = get_all_labels(current_user.id)
    return render_template('quality_labels/manage.html', labels=labels)


@quality_labels_bp.route('/grant-green')
@role_required('admin')
def grant_green_page():
    """颁发政府绿标页面（政府用户）。需求: 18.2"""
    enterprises = Enterprise.query.filter_by(role='enterprise').order_by(Enterprise.name).all()
    return render_template('quality_labels/grant_green.html', enterprises=enterprises)


@quality_labels_bp.route('/inspection')
@login_required
def inspection_page():
    """链主验厂管理页面。需求: 18.3, 54.1-54.7"""
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        from flask import abort
        abort(403)
    enterprises = Enterprise.query.filter_by(role='enterprise').order_by(Enterprise.name).all()
    return render_template('quality_labels/inspection.html', enterprises=enterprises)


# ── API 路由 ──────────────────────────────────────────────────────────────

@quality_labels_bp.route('/api/grant-green', methods=['POST'])
@role_required('admin')
def api_grant_green():
    """颁发政府绿标。需求: 18.2"""
    data = request.get_json() or {}
    enterprise_id = data.get('enterprise_id')
    if not enterprise_id:
        return jsonify({'success': False, 'message': '缺少企业ID'}), 400

    result = grant_government_green_label(
        enterprise_id=int(enterprise_id),
        issuer_id=current_user.id,
        label_name=data.get('label_name', '政府绿色认证'),
        certificate_no=data.get('certificate_no', ''),
        valid_days=int(data.get('valid_days', 365)),
    )
    status = 200 if result['success'] else 400
    return jsonify(result), status


@quality_labels_bp.route('/api/grant-inspection', methods=['POST'])
@login_required
def api_grant_inspection():
    """颁发链主验厂标签。需求: 18.3, 54.1-54.4"""
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        return jsonify({'success': False, 'message': '只有链主企业可以颁发验厂标签'}), 403

    data = request.get_json() or {}
    enterprise_id = data.get('enterprise_id')
    if not enterprise_id:
        return jsonify({'success': False, 'message': '缺少企业ID'}), 400

    result = grant_lead_inspection_label(
        enterprise_id=int(enterprise_id),
        issuer_id=current_user.id,
        label_name=data.get('label_name', '链主验厂通过'),
        certificate_no=data.get('certificate_no', ''),
        valid_days=int(data.get('valid_days', 365)),
        inspection_notes=data.get('inspection_notes', ''),
    )
    status = 200 if result['success'] else 400
    return jsonify(result), status


@quality_labels_bp.route('/api/revoke/<int:label_id>', methods=['POST'])
@login_required
def api_revoke(label_id: int):
    """撤销质量标签。需求: 18.7"""
    data = request.get_json() or {}
    result = revoke_label(
        label_id=label_id,
        operator_id=current_user.id,
        reason=data.get('reason', ''),
    )
    status = 200 if result['success'] else 400
    return jsonify(result), status


@quality_labels_bp.route('/api/reinspection', methods=['POST'])
@login_required
def api_reinspection():
    """申请重新验厂。需求: 54.6"""
    data = request.get_json() or {}
    issuer_id = data.get('issuer_id')
    if not issuer_id:
        return jsonify({'success': False, 'message': '缺少链主企业ID'}), 400

    result = apply_reinspection(
        enterprise_id=current_user.id,
        issuer_id=int(issuer_id),
        reason=data.get('reason', ''),
    )
    return jsonify(result)


@quality_labels_bp.route('/api/enterprise/<int:enterprise_id>', methods=['GET'])
@login_required
def api_get_labels(enterprise_id: int):
    """获取企业质量标签。需求: 18.1"""
    labels = get_active_labels(enterprise_id)
    return jsonify({'success': True, 'labels': labels})


@quality_labels_bp.route('/api/sync-third-party', methods=['POST'])
@login_required
def api_sync_third_party():
    """同步第三方评分。需求: 18.4"""
    data = request.get_json() or {}
    enterprise_id = data.get('enterprise_id', current_user.id)
    source = data.get('source', '企查查')

    # 先获取评分
    ent = Enterprise.query.get(int(enterprise_id))
    if not ent:
        return jsonify({'success': False, 'message': '企业不存在'}), 404

    rating_data = fetch_third_party_rating(ent.name, source)
    if not rating_data.get('success'):
        return jsonify({'success': False, 'message': '获取第三方评分失败'}), 500

    result = sync_third_party_rating(
        enterprise_id=int(enterprise_id),
        rating_source=source,
        rating_value=rating_data['rating'],
        rating_detail=rating_data.get('detail', ''),
    )
    result['rating'] = rating_data['rating']
    return jsonify(result)

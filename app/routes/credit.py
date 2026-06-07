"""
信用分相关API路由
GET  /api/credit/score/<id>      - 获取企业信用分和权益
GET  /api/credit/history/<id>    - 获取信用分变更历史
POST /api/credit/appeal          - 申诉信用分扣除
"""
from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from app.authz import role_required
from app.errors import APIError, ERR_FORBIDDEN, ERR_ENTERPRISE_NOT_FOUND, ERR_CREDIT_RECORD_NOT_FOUND
from app.models import Enterprise
from app.services.credit_score_events import count_credit_events, find_credit_event
from app.services.credit_engine import (
    check_credit_privileges, get_credit_history, update_credit_score
)

credit_bp = Blueprint('credit', __name__)


@credit_bp.route('/api/credit/score/<int:enterprise_id>', methods=['GET'])
@login_required
def get_credit_score(enterprise_id: int):
    """获取企业信用分和权益信息。"""
    # 企业只能查自己，管理员可查所有
    if current_user.role != 'admin' and current_user.id != enterprise_id:
        raise APIError.forbidden('无权限查看其他企业信用分', ERR_FORBIDDEN)

    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        raise APIError.not_found('企业不存在', ERR_ENTERPRISE_NOT_FOUND)

    privileges = check_credit_privileges(enterprise_id)
    score = float(ent.credit_score or 60.0)
    level = '优秀' if score >= 90 else ('良好' if score >= 75 else ('一般' if score >= 60 else '较差'))

    return jsonify({
        'success': True,
        'enterprise_id': enterprise_id,
        'credit_score': score,
        'level': level,
        'privileges': privileges,
    })


@credit_bp.route('/api/credit/history/<int:enterprise_id>', methods=['GET'])
@login_required
def get_credit_history_api(enterprise_id: int):
    """获取信用分变更历史。"""
    if current_user.role != 'admin' and current_user.id != enterprise_id:
        raise APIError.forbidden('无权限查看其他企业信用分历史', ERR_FORBIDDEN)

    limit = request.args.get('limit', 10, type=int)
    offset = request.args.get('offset', 0, type=int)

    if limit < 1 or limit > 100:
        raise APIError.bad_request('limit 须在 1-100 之间')
    if offset < 0:
        raise APIError.bad_request('offset 不能为负数')

    ent = Enterprise.query.get(enterprise_id)
    total = count_credit_events(ent) if ent else 0
    records = get_credit_history(enterprise_id, limit=limit)

    return jsonify({
        'success': True,
        'total': total,
        'limit': limit,
        'offset': offset,
        'records': records,
    })


@credit_bp.route('/api/credit/appeal', methods=['POST'])
@role_required('enterprise')
def appeal_credit():
    """申诉信用分扣除。"""
    data = request.get_json() or {}
    history_id = data.get('history_id')
    reason = (data.get('reason') or '').strip()

    if not history_id or not reason:
        raise APIError.bad_request('请提供申诉记录ID和申诉理由')

    ent = Enterprise.query.get(current_user.id)
    if not ent:
        raise APIError.not_found('企业不存在', ERR_ENTERPRISE_NOT_FOUND)
    record = find_credit_event(ent, str(history_id))

    if not record:
        raise APIError.not_found('记录不存在', ERR_CREDIT_RECORD_NOT_FOUND)

    if float(record.get("change_value") or 0) >= 0:
        raise APIError.bad_request('只能对扣分记录提出申诉')

    from app.services.collaboration_service import send_message
    admins = Enterprise.query.filter_by(role='admin').all()
    for admin in admins:
        send_message(
            recipient_id=admin.id,
            message_type='system',
            title=f'信用分申诉：{current_user.name}',
            content=f'企业 {current_user.name} 对信用分变更记录#{history_id}（{float(record.get("change_value") or 0):+.1f}分）提出申诉。\n申诉理由：{reason}',
            link_url='/admin/credit-appeals',
            priority='normal',
        )

    return jsonify({'success': True, 'message': '申诉已提交，管理员将在5个工作日内处理'})

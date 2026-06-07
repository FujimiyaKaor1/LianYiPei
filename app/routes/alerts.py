"""
预警路由：
- GET  /api/alerts                          - 获取预警列表（支持筛选、分页）
- POST /api/alerts/:id/assign               - 派发预警任务
- POST /api/alert-workflows/:id/start       - 开始处理
- POST /api/alert-workflows/:id/submit      - 提交处理结果
- POST /api/alert-workflows/:id/review      - 审核处理结果
- GET  /api/alert-workflows/stats           - 处置统计
- GET  /dashboard/alert-rules               - 预警规则配置页面
- GET  /dashboard/alert-center              - 预警中心页面
- GET  /dashboard/alert-workflow/:id        - 工作流处置页面
- GET  /dashboard/alert-stats               - 预警统计分析页面
需求: 32.1-32.8, 33.1-33.7, 35.1-35.8
"""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, render_template
from flask_login import login_required, current_user
from config import DEFAULT_ALERT_THRESHOLDS
from app import db
from app.authz import role_required
from app.models import Alert, Enterprise

alerts_bp = Blueprint('alerts', __name__)
logger = logging.getLogger('app.ops')


# ── 预警列表 API ──────────────────────────────────────────────────────────

@alerts_bp.route('/api/alerts', methods=['GET'])
@login_required
def get_alerts():
    """
    获取预警列表，支持按等级、类型、状态筛选，支持分页。
    需求: 33.1, 33.2, 33.3, 33.4, 33.5
    """
    level = request.args.get('level')          # red / yellow / blue
    alert_type = request.args.get('alert_type')  # capacity_risk / supply_chain_break / business_risk / credit_anomaly
    is_active = request.args.get('is_active')  # true / false
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)

    q = Alert.query

    if level:
        q = q.filter(Alert.level == level)
    if alert_type and hasattr(Alert, 'alert_type'):
        q = q.filter(Alert.alert_type == alert_type)
    if is_active is not None:
        active_bool = is_active.lower() == 'true'
        q = q.filter(Alert.is_active == active_bool)
    else:
        q = q.filter(Alert.is_active == True)

    total = q.count()
    alerts = q.order_by(
        Alert.level.desc(),   # red > yellow > blue
        Alert.created_at.desc()
    ).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'alerts': [_alert_to_dict(a) for a in alerts],
    })


# ── 派发预警任务 API ──────────────────────────────────────────────────────

@alerts_bp.route('/api/alerts/<int:alert_id>/assign', methods=['POST'])
@login_required
def assign_alert(alert_id: int):
    """
    派发预警任务给指定处理人。
    需求: 35.1, 35.2
    """
    from app.services.alert_workflow_service import assign_workflow

    Alert.query.get_or_404(alert_id)
    data = request.get_json() or {}

    assigned_to = data.get('assigned_to')   # 处理人企业ID
    deadline_str = data.get('deadline')     # 要求完成时间 ISO格式

    if not assigned_to:
        return jsonify({'error': '缺少 assigned_to 参数'}), 400

    deadline = None
    if deadline_str:
        try:
            deadline = datetime.fromisoformat(deadline_str.replace('Z', '+00:00'))
        except ValueError:
            return jsonify({'error': 'deadline 格式无效，请使用 ISO 格式'}), 400

    try:
        workflow = assign_workflow(
            alert_id,
            int(assigned_to),
            current_user.id,
            deadline=deadline,
        )
    except ValueError as e:
        return jsonify({'error': str(e)}), 409

    logger.info(
        'alert assign alert_id=%s workflow_id=%s -> %s',
        alert_id,
        workflow.id,
        assigned_to,
    )
    db.session.commit()

    return jsonify({
        'success': True,
        'workflow_id': workflow.id,
        'message': '预警任务已派发',
    })


# ── 预警规则配置页面 ──────────────────────────────────────────────────────

@alerts_bp.route('/dashboard/alert-rules')
@login_required
@role_required('admin')
def alert_rules_page():
    """
    预警规则配置页面。
    需求: 32.2, 32.3, 48.1-48.8
    """
    thresholds = dict(DEFAULT_ALERT_THRESHOLDS)
    change_logs = []

    return render_template(
        'dashboard/alert_rules.html',
        thresholds=thresholds,
        change_logs=change_logs,
    )


# ── 预警中心页面 ──────────────────────────────────────────────────────────

@alerts_bp.route('/dashboard/alert-center')
@login_required
@role_required('admin')
def alert_center():
    """
    预警中心页面：按等级分类展示预警列表、统计数据、筛选搜索。
    需求: 33.1, 33.2, 33.3, 33.4, 33.5, 33.7
    """
    from app.services.alert_notifier import get_alert_stats

    level = request.args.get('level', '')
    alert_type = request.args.get('alert_type', '')
    keyword = request.args.get('q', '')
    alert_id = request.args.get('alert_id', type=int)

    q = Alert.query.filter_by(is_active=True)
    if level:
        q = q.filter(Alert.level == level)
    if alert_type and hasattr(Alert, 'alert_type'):
        q = q.filter(Alert.alert_type == alert_type)
    if keyword:
        q = q.filter(
            (Alert.product_name.ilike(f'%{keyword}%')) |
            (Alert.message.ilike(f'%{keyword}%'))
        )

    # 红色置顶，再按时间倒序
    alerts = q.order_by(
        Alert.level.desc(),
        Alert.created_at.desc()
    ).limit(200).all()

    # 分组
    red_alerts = [a for a in alerts if a.level == 'red']
    yellow_alerts = [a for a in alerts if a.level == 'yellow']
    blue_alerts = [a for a in alerts if a.level == 'blue']

    stats = get_alert_stats()

    # 高亮指定预警
    highlighted = None
    if alert_id:
        highlighted = Alert.query.get(alert_id)

    return render_template(
        'dashboard/alert_center.html',
        red_alerts=red_alerts,
        yellow_alerts=yellow_alerts,
        blue_alerts=blue_alerts,
        stats=stats,
        level=level,
        alert_type=alert_type,
        keyword=keyword,
        highlighted=highlighted,
    )


# ── 手动触发预警检查 ──────────────────────────────────────────────────────

@alerts_bp.route('/api/alerts/run-checks', methods=['POST'])
@login_required
@role_required('admin')
def trigger_alert_checks():
    """手动触发预警检查（管理员用）。"""
    from app.services.alert_engine import run_all_checks
    alerts = run_all_checks()
    logger.info('alert_engine manual run generated=%s', len(alerts))
    return jsonify({
        'success': True,
        'alert_count': len(alerts),
        'message': f'预警检查完成，共生成{len(alerts)}条预警',
    })


# ── 内部工具 ──────────────────────────────────────────────────────────────

def _alert_to_dict(alert: Alert) -> dict:
    d = {
        'id': alert.id,
        'product_name': alert.product_name,
        'message': alert.message,
        'level': alert.level,
        'dimension': alert.dimension,
        'is_active': alert.is_active,
        'suggestion': alert.suggestion,
        'created_at': alert.created_at.isoformat() if alert.created_at else None,
    }
    if hasattr(alert, 'alert_type'):
        d['alert_type'] = alert.alert_type
    if hasattr(alert, 'severity_score'):
        d['severity_score'] = alert.severity_score

    # 注入深度分析字段（链小易 AI 风险解读）
    analysis = getattr(alert, 'analysis_data', None) or {}
    d['risk_reason'] = analysis.get('risk_reason', '')
    d['impact_scope'] = analysis.get('impact_scope', '')
    d['ai_suggestions'] = analysis.get('ai_suggestions', [])
    d['data_source_info'] = analysis.get('data_source_info', {})
    d['historical_trend'] = analysis.get('historical_trend', [])

    return d



def _log_operation(op_type: str, target: str, target_id, detail: str):
    logger.info(
        'alerts_op type=%s target=%s target_id=%s user=%s detail=%s',
        op_type,
        target,
        target_id,
        current_user.id if current_user.is_authenticated else None,
        detail,
    )


# ── 工作流：开始处理 ──────────────────────────────────────────────────────

@alerts_bp.route('/api/alert-workflows/<int:workflow_id>/start', methods=['POST'])
@login_required
def start_workflow(workflow_id: int):
    """处理人接受任务，状态 pending → processing。需求: 35.3"""
    from app.services.alert_workflow_service import start_processing
    try:
        wf = start_processing(workflow_id, current_user.id)
        db.session.commit()
        return jsonify({'success': True, 'status': wf.status})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ── 工作流：提交处理结果 ──────────────────────────────────────────────────

@alerts_bp.route('/api/alert-workflows/<int:workflow_id>/submit', methods=['POST'])
@login_required
def submit_workflow(workflow_id: int):
    """提交处理结果和证据。需求: 35.3, 35.4"""
    from app.services.alert_workflow_service import submit_result
    data = request.get_json() or {}
    handling_notes = data.get('handling_notes', '').strip()
    evidence_urls = data.get('evidence_urls', [])

    if not handling_notes:
        return jsonify({'error': '处理说明不能为空'}), 400

    try:
        wf = submit_result(workflow_id, current_user.id, handling_notes, evidence_urls)
        db.session.commit()
        return jsonify({'success': True, 'status': wf.status, 'workflow_id': wf.id})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ── 工作流：审核 ──────────────────────────────────────────────────────────

@alerts_bp.route('/api/alert-workflows/<int:workflow_id>/review', methods=['POST'])
@login_required
@role_required('admin')
def review_workflow(workflow_id: int):
    """审核处理结果。需求: 35.5, 35.6, 35.7"""
    from app.services.alert_workflow_service import review_workflow as do_review
    data = request.get_json() or {}
    approved = data.get('approved', False)
    review_notes = data.get('review_notes', '')

    try:
        wf = do_review(workflow_id, current_user.id, approved, review_notes)
        db.session.commit()
        return jsonify({
            'success': True,
            'status': wf.status,
            'review_result': wf.review_result,
        })
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


# ── 工作流：统计 API ──────────────────────────────────────────────────────

@alerts_bp.route('/api/alert-workflows/stats', methods=['GET'])
@login_required
@role_required('admin')
def workflow_stats_api():
    """预警处置统计数据。需求: 33.7, 35.8"""
    from app.services.alert_workflow_service import get_workflow_stats
    return jsonify(get_workflow_stats())


# ── 工作流：我的任务列表 API ──────────────────────────────────────────────

@alerts_bp.route('/api/alert-workflows/mine', methods=['GET'])
@login_required
def my_workflows():
    """获取当前用户的工作流任务。"""
    from app.services.alert_workflow_service import get_my_workflows
    status = request.args.get('status')
    return jsonify(get_my_workflows(current_user.id, status))


# ── 工作流处置页面 ────────────────────────────────────────────────────────

@alerts_bp.route('/dashboard/alert-workflow/<int:workflow_id>')
@login_required
def alert_workflow_page(workflow_id: int):
    """
    预警处置详情页：填写处理记录、上传证据、审核。
    需求: 35.1-35.5
    """
    from app.services.alert_workflow_service import (
        get_workflow_detail,
        get_workflows_for_alert,
    )

    try:
        wf = get_workflow_detail(workflow_id)
    except ValueError:
        from flask import abort
        abort(404)

    alert = Alert.query.get_or_404(wf['alert_id'])
    all_workflows = get_workflows_for_alert(alert.id)
    all_workflows.sort(key=lambda x: x.get('id') or 0, reverse=True)

    return render_template(
        'dashboard/alert_workflow.html',
        workflow=wf,
        alert=alert,
        all_workflows=all_workflows,
        current_user=current_user,
    )


# ── 预警统计分析页面 ──────────────────────────────────────────────────────

@alerts_bp.route('/dashboard/alert-stats')
@login_required
@role_required('admin')
def alert_stats_page():
    """
    预警统计分析页面：响应时间、处置率、趋势图。
    需求: 33.7, 35.8
    """
    from app.services.alert_workflow_service import get_workflow_stats
    stats = get_workflow_stats()
    return render_template('dashboard/alert_stats.html', stats=stats)

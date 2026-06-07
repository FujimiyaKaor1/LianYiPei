"""
管理员后台路由：
- 信用分规则配置
- 数据质量监控
- 操作日志审计
- API密钥管理
- 举报处理
- 演示模式
"""
import logging
from datetime import datetime

from flask import Blueprint, jsonify, request, render_template
from sqlalchemy import and_, or_
from flask_login import current_user
from config import (
    DEFAULT_ALERT_THRESHOLDS,
    DEFAULT_CREDIT_RULES,
    disable_runtime_collab_api_key,
    register_runtime_collab_api_key,
    _RUNTIME_COLLAB_API_KEYS,
    _collab_api_keys_list,
)
from app.authz import role_required
from app.models import Enterprise
from app import db

admin_panel_bp = Blueprint('admin_panel', __name__)
logger = logging.getLogger('app.ops')


# ══════════════════════════════════════════════════════════════════════════
# /admin/dashboard/api/* 兼容路由（前端管理员控制台调用这些路径）
# ══════════════════════════════════════════════════════════════════════════


@admin_panel_bp.route('/dashboard/api/stats', methods=['GET'])
@role_required('admin')
def admin_dashboard_stats():
    """代理 /dashboard/api/stats —— 前端管理员控制台大屏统计"""
    from app.routes.dashboard import api_stats as _stats
    return _stats()


@admin_panel_bp.route('/dashboard/api/alerts', methods=['GET'])
@role_required('admin')
def admin_dashboard_alerts():
    """代理 /dashboard/api/alerts —— 前端管理员控制台预警列表"""
    from app.routes.dashboard import api_alerts as _alerts
    return _alerts()


@admin_panel_bp.route('/dashboard/api/run-alerts', methods=['POST'])
@role_required('admin')
def admin_dashboard_run_alerts():
    """代理 /dashboard/api/run-alerts —— 手动触发预警生成"""
    from app.routes.dashboard import run_alerts as _run_alerts
    return _run_alerts()


# ── 信用分规则配置 ────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/config/credit-rules', methods=['GET'])
@role_required('admin')
def get_credit_rules():
    rules = [
        {
            'id': i + 1,
            'rule_type': k,
            'score_change': float(v),
            'description': '',
            'max_per_month': None,
            'is_active': True,
        }
        for i, (k, v) in enumerate(sorted(DEFAULT_CREDIT_RULES.items()))
    ]
    return jsonify({'rules': rules})


@admin_panel_bp.route('/api/config/credit-rules', methods=['POST'])
@role_required('admin')
def add_credit_rule():
    data = request.get_json() or {}
    rule_type = (data.get('rule_type') or '').strip()
    score_change = data.get('score_change')
    change_reason = (data.get('change_reason') or '').strip()

    if not rule_type or score_change is None:
        return jsonify({'error': '缺少 rule_type 或 score_change'}), 400
    if not change_reason:
        return jsonify({'error': '请填写变更原因'}), 400

    DEFAULT_CREDIT_RULES[rule_type] = float(score_change)
    logger.info('credit_rule create %s %s reason=%s', rule_type, score_change, change_reason)
    return jsonify({'success': True, 'rule_id': len(DEFAULT_CREDIT_RULES)})


@admin_panel_bp.route('/api/config/credit-rules/<int:rule_id>', methods=['PUT'])
@role_required('admin')
def update_credit_rule(rule_id: int):
    data = request.get_json() or {}
    change_reason = (data.get('change_reason') or '').strip()
    if not change_reason:
        return jsonify({'error': '请填写变更原因'}), 400

    keys = sorted(DEFAULT_CREDIT_RULES.keys())
    if rule_id < 1 or rule_id > len(keys):
        return jsonify({'error': '规则不存在'}), 404
    rk = keys[rule_id - 1]

    if 'score_change' in data:
        DEFAULT_CREDIT_RULES[rk] = float(data['score_change'])
    logger.info('credit_rule update %s reason=%s', rk, change_reason)
    return jsonify({'success': True})


@admin_panel_bp.route('/api/config/credit-rules/<int:rule_id>', methods=['DELETE'])
@role_required('admin')
def delete_credit_rule(rule_id: int):
    data = request.get_json() or {}
    change_reason = (data.get('change_reason') or '').strip()
    if not change_reason:
        return jsonify({'error': '请填写变更原因'}), 400

    keys = sorted(DEFAULT_CREDIT_RULES.keys())
    if rule_id < 1 or rule_id > len(keys):
        return jsonify({'error': '规则不存在'}), 404
    rk = keys[rule_id - 1]
    DEFAULT_CREDIT_RULES.pop(rk, None)
    logger.info('credit_rule delete %s reason=%s', rk, change_reason)
    return jsonify({'success': True})


# ── 预警阈值配置 ──────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/config/alert-thresholds', methods=['GET'])
@role_required('admin')
def get_alert_thresholds():
    thresholds = [
        {
            'id': i + 1,
            'dimension': k,
            'threshold_value': float(v),
            'description': '',
            'updated_at': None,
        }
        for i, (k, v) in enumerate(sorted(DEFAULT_ALERT_THRESHOLDS.items()))
    ]
    return jsonify({'thresholds': thresholds})


@admin_panel_bp.route('/api/config/alert-thresholds', methods=['POST'])
@role_required('admin')
def upsert_alert_threshold():
    data = request.get_json() or {}
    dimension = (data.get('dimension') or '').strip()
    threshold_value = data.get('threshold_value')

    if not dimension or threshold_value is None:
        return jsonify({'error': '缺少 dimension 或 threshold_value'}), 400

    try:
        tv = float(threshold_value)
    except (TypeError, ValueError):
        return jsonify({'error': 'threshold_value 无效'}), 400

    if dimension == 'local':
        DEFAULT_ALERT_THRESHOLDS[dimension] = int(tv)
    else:
        DEFAULT_ALERT_THRESHOLDS[dimension] = tv

    logger.info('alert_threshold update %s=%s', dimension, threshold_value)
    return jsonify({'success': True})


# ── API密钥管理 ───────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/api-keys', methods=['GET'])
@role_required('admin')
def list_api_keys():
    rows = []
    for i, kv in enumerate(_collab_api_keys_list()):
        rows.append(
            {
                'id': -(i + 1),
                'key_name': f'env[{i}]',
                'organization': 'COLLAB_API_KEYS',
                'permissions': ['verify_code'],
                'rate_limit': 100,
                'is_active': True,
                'created_at': None,
                'last_used_at': None,
                'key_preview': (kv[:8] + '...') if len(kv) >= 8 else kv,
            }
        )
    for k in _RUNTIME_COLLAB_API_KEYS:
        rows.append(
            {
                'id': k['id'],
                'key_name': k.get('key_name', ''),
                'organization': 'runtime',
                'permissions': ['verify_code'],
                'rate_limit': 100,
                'is_active': k.get('is_active', True),
                'created_at': k.get('created_at'),
                'last_used_at': None,
                'key_preview': (k['key_value'][:8] + '...') if len(k.get('key_value', '')) >= 8 else k.get('key_value', ''),
            }
        )
    return jsonify({'api_keys': rows})


@admin_panel_bp.route('/api/api-keys', methods=['POST'])
@role_required('admin')
def create_api_key():
    data = request.get_json() or {}
    key_name = (data.get('key_name') or '').strip()

    if not key_name:
        return jsonify({'error': '缺少 key_name'}), 400

    rid, key_value = register_runtime_collab_api_key(key_name)
    logger.info('api_key create id=%s name=%s', rid, key_name)

    return jsonify({
        'success': True,
        'api_key_id': rid,
        'key_value': key_value,
        'message': '请妥善保存API密钥，此后不再显示完整密钥',
    })


@admin_panel_bp.route('/api/api-keys/<int:key_id>/disable', methods=['PUT'])
@role_required('admin')
def disable_api_key(key_id: int):
    if key_id <= 0:
        return jsonify({'error': '环境变量中的密钥请在服务器上修改 COLLAB_API_KEYS'}), 400
    if not disable_runtime_collab_api_key(key_id):
        return jsonify({'error': '密钥不存在'}), 404
    logger.info('api_key disable id=%s', key_id)
    return jsonify({'success': True})


# ── 举报处理 ──────────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/reports', methods=['GET'])
@role_required('admin')
def list_reports():
    from app.services.report_records_service import list_reports as _list

    status = request.args.get('status', 'pending')
    reports = _list(status=status, limit=50)
    return jsonify({'reports': reports})


@admin_panel_bp.route('/api/reports/<int:report_id>/handle', methods=['PUT'])
@role_required('admin')
def handle_report(report_id: int):
    """处理举报：verified_true 或 verified_false。"""
    from app.services.report_records_service import find_report, handle_report as _apply_report
    from app.services.credit_engine import update_credit_score
    from app.services.collaboration_service import send_message

    data = request.get_json() or {}
    result = data.get('result')  # verified_true / verified_false
    notes = (data.get('notes') or '').strip()

    if result not in ('verified_true', 'verified_false'):
        return jsonify({'error': 'result 必须为 verified_true 或 verified_false'}), 400

    found = find_report(report_id)
    if not found:
        return jsonify({'error': '举报记录不存在'}), 404
    ent, r, _idx = found
    reporter_id = int(r.get('reporter_id') or 0)
    reported_id = ent.id
    rtype = r.get('report_type') or ''

    if result == 'verified_true':
        update_credit_score(reported_id, 'report_verified', reason=f'举报核实：{rtype}')
        send_message(
            recipient_id=reported_id,
            message_type='system',
            title='举报核实通知',
            content='经核实，针对贵司的举报成立，信用分已按规则调整。如有异议请申诉。',
            priority='high',
        )
    else:
        update_credit_score(reporter_id, 'report_false', reason='举报不实')
        send_message(
            recipient_id=reporter_id,
            message_type='system',
            title='举报结果通知',
            content='您的举报经核实为不实，举报方信用分已按规则调整。',
            priority='normal',
        )

    _apply_report(report_id, current_user.id, result, notes)
    logger.info('report handled id=%s result=%s', report_id, result)
    db.session.commit()
    return jsonify({'success': True})


# ── 操作日志 ──────────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/operation-logs', methods=['GET'])
@role_required('admin')
def get_operation_logs():
    """原 operation_logs 表已删除，请使用服务器日志或 log 聚合；此处返回空列表。"""
    return jsonify({
        'total': 0,
        'logs': [],
        'message': '操作日志已改为标准 logging（logger app.ops），不再落库。',
    })


# ── 数据质量监控 ──────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/data-quality', methods=['GET'])
@role_required('admin')
def data_quality_overview():
    """数据质量概览。"""
    total = Enterprise.query.filter_by(role='enterprise').count()
    dormant = Enterprise.query.filter_by(role='enterprise', is_dormant=True).count()
    complete = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.address.isnot(None),
        Enterprise.industry_code.isnot(None),
        Enterprise.tech_keywords.isnot(None),
    ).count()

    return jsonify({
        'total_enterprises': total,
        'dormant_count': dormant,
        'dormant_rate': round(dormant / total * 100, 1) if total > 0 else 0,
        'complete_profile_count': complete,
        'complete_rate': round(complete / total * 100, 1) if total > 0 else 0,
    })


# ── 演示模式 ──────────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/demo/generate', methods=['POST'])
@role_required('admin')
def generate_demo_data():
    """生成演示数据。"""
    from app.models import Product
    import random

    count = request.get_json().get('count', 10) if request.get_json() else 10
    count = min(50, max(1, int(count)))

    created = 0
    for i in range(count):
        name = f'演示企业_{i+1:03d}'
        if Enterprise.query.filter_by(name=name).first():
            continue
        ent = Enterprise(
            name=name,
            address=f'四川省成都市演示区{i+1}号',
            contact=f'演示联系人{i+1}',
            phone=f'1380000{i:04d}',
            credit_score=random.uniform(60, 95),
            capacity=random.randint(50, 500),
            role='enterprise',
            industry_code=random.choice(['C34', 'C35', 'C36', 'C37', 'C38']),
        )
        ent.set_password('demo123456')
        db.session.add(ent)
        created += 1

    logger.info('demo_data create count=%s', created)
    db.session.commit()
    return jsonify({'success': True, 'created': created})


@admin_panel_bp.route('/api/demo/clear', methods=['DELETE'])
@role_required('admin')
def clear_demo_data():
    """清理演示数据（名称含"演示"的企业）。"""
    data = request.get_json() or {}
    confirm = data.get('confirm', False)
    if not confirm:
        return jsonify({'error': '请传入 confirm=true 确认清理'}), 400

    demo_ents = Enterprise.query.filter(Enterprise.name.like('演示企业_%')).all()
    count = len(demo_ents)
    for ent in demo_ents:
        db.session.delete(ent)

    logger.info('demo_data delete count=%s', count)
    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


# ── 定时任务状态 ──────────────────────────────────────────────────────────

@admin_panel_bp.route('/api/scheduler/status', methods=['GET'])
@role_required('admin')
def get_scheduler_status():
    """获取定时任务调度器状态。"""
    from app.services.scheduler import get_scheduler, get_job_status
    
    scheduler = get_scheduler()
    if scheduler is None:
        return jsonify({
            'running': False,
            'message': '调度器未启动',
            'jobs': []
        })
    
    jobs = get_job_status()
    return jsonify({
        'running': scheduler.running,
        'message': '调度器运行中',
        'jobs': jobs
    })


@admin_panel_bp.route('/api/scheduler/trigger/<job_id>', methods=['POST'])
@role_required('admin')
def trigger_job_manually(job_id: str):
    """手动触发定时任务（用于测试）。"""
    from app.services.scheduler import get_scheduler
    
    scheduler = get_scheduler()
    if scheduler is None:
        return jsonify({'error': '调度器未启动'}), 500
    
    try:
        job = scheduler.get_job(job_id)
        if job is None:
            return jsonify({'error': f'任务不存在: {job_id}'}), 404
        
        # 手动触发任务
        job.modify(next_run_time=datetime.utcnow())
        
        logger.info('scheduler trigger job_id=%s', job_id)
        
        return jsonify({
            'success': True,
            'message': f'任务 {job_id} 已加入执行队列'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════
# 企业注册审核管理
# ══════════════════════════════════════════════════════════════════════════

@admin_panel_bp.route('/verifications')
@role_required('admin')
def verifications_page():
    """企业审核管理页面"""
    return render_template('admin/verifications.html')


@admin_panel_bp.route('/api/verifications', methods=['GET'])
@role_required('admin')
def list_pending_verifications():
    """获取待审核企业列表"""
    status = request.args.get('status', 'pending')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    query = Enterprise.query.filter(Enterprise.role == 'enterprise')
    
    if status == 'pending':
        query = query.filter(Enterprise.verification_status == 'pending')
    elif status == 'approved':
        query = query.filter(Enterprise.verification_status == 'approved')
    elif status == 'rejected':
        query = query.filter(Enterprise.verification_status == 'rejected')
    elif status == 'all':
        pass  # 不过滤
    
    query = query.order_by(Enterprise.registered_at.desc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    items = []
    for ent in pagination.items:
        items.append({
            'id': ent.id,
            'name': ent.name,
            'address': ent.address or '',
            'contact': ent.contact or '',
            'phone': ent.phone or '',
            'verification_status': ent.verification_status,
            'registered_at': ent.registered_at.strftime('%Y-%m-%d %H:%M') if ent.registered_at else '',
            'verified_at': ent.verified_at.strftime('%Y-%m-%d %H:%M') if ent.verified_at else '',
            'rejection_reason': ent.rejection_reason or '',
        })
    
    return jsonify({
        'items': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
        'pages': pagination.pages,
    })


@admin_panel_bp.route('/api/verifications/<int:enterprise_id>', methods=['GET'])
@role_required('admin')
def get_verification_detail(enterprise_id: int):
    """获取企业审核详情"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent or ent.role != 'enterprise':
        return jsonify({'error': '企业不存在'}), 404
    
    # 获取该企业已发布的产品数量
    product_count = ent.products.count() if hasattr(ent, 'products') else 0
    
    # 获取该企业发起的询价/供应数量
    from app.models import Inquiry
    inquiry_count = Inquiry.query.filter_by(poster_id=enterprise_id).count()
    
    return jsonify({
        'id': ent.id,
        'name': ent.name,
        'address': ent.address or '',
        'contact': ent.contact or '',
        'phone': ent.phone or '',
        'email': getattr(ent, 'email', '') or '',
        'industry_code': ent.industry_code or '',
        'business_scope': ent.business_scope or '',
        'registered_capital': getattr(ent, 'registered_capital', None),
        'registered_at': ent.registered_at.strftime('%Y-%m-%d %H:%M:%S') if ent.registered_at else '',
        'province': getattr(ent, 'province', '') or '',
        'city': getattr(ent, 'city', '') or '',
        'longitude': getattr(ent, 'longitude', None),
        'latitude': getattr(ent, 'latitude', None),
        'credit_score': getattr(ent, 'credit_score', 0) or 0,
        'capacity': getattr(ent, 'capacity', 0) or 0,
        'verification_status': ent.verification_status,
        'verified_at': ent.verified_at.strftime('%Y-%m-%d %H:%M:%S') if ent.verified_at else '',
        'rejection_reason': ent.rejection_reason or '',
        'product_count': product_count,
        'inquiry_count': inquiry_count,
    })


@admin_panel_bp.route('/api/verifications/<int:enterprise_id>/approve', methods=['POST'])
@role_required('admin')
def approve_enterprise(enterprise_id: int):
    """审核通过企业"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent or ent.role != 'enterprise':
        return jsonify({'error': '企业不存在'}), 404
    
    if ent.verification_status != 'pending':
        return jsonify({'error': '该企业已审核过'}), 400
    
    ent.verification_status = 'approved'
    ent.is_verified = True
    ent.verified_by = current_user.id
    ent.verified_at = datetime.utcnow()
    
    db.session.commit()
    
    # 记录操作日志
    logger.info('enterprise approved id=%s name=%s by=%s', enterprise_id, ent.name, current_user.id)
    
    # 发送消息通知企业（如果需要可扩展）
    from app.services.collaboration_service import send_message
    send_message(
        recipient_id=enterprise_id,
        message_type='system',
        title='注册审核通过通知',
        content='恭喜！您的企业注册已通过审核，现在可以登录使用链易配平台的所有功能。',
        priority='normal',
    )
    
    return jsonify({'success': True, 'message': '已审核通过'})


@admin_panel_bp.route('/api/verifications/<int:enterprise_id>/reject', methods=['POST'])
@role_required('admin')
def reject_enterprise(enterprise_id: int):
    """驳回企业注册"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent or ent.role != 'enterprise':
        return jsonify({'error': '企业不存在'}), 404
    
    if ent.verification_status != 'pending':
        return jsonify({'error': '该企业已审核过'}), 400
    
    data = request.get_json() or {}
    reason = (data.get('reason') or '').strip()
    
    if not reason:
        return jsonify({'error': '请填写驳回原因'}), 400
    
    ent.verification_status = 'rejected'
    ent.is_verified = False
    ent.verified_by = current_user.id
    ent.verified_at = datetime.utcnow()
    ent.rejection_reason = reason
    
    db.session.commit()
    
    logger.info('enterprise rejected id=%s name=%s reason=%s by=%s', 
                 enterprise_id, ent.name, reason, current_user.id)
    
    # 发送消息通知企业
    from app.services.collaboration_service import send_message
    send_message(
        recipient_id=enterprise_id,
        message_type='system',
        title='注册审核驳回通知',
        content=f'很抱歉，您的企业注册申请已被驳回。原因：{reason}。如有疑问，请联系管理员。',
        priority='normal',
    )
    
    return jsonify({'success': True, 'message': '已驳回'})


@admin_panel_bp.route('/api/verifications/<int:enterprise_id>/reset', methods=['POST'])
@role_required('admin')
def reset_verification(enterprise_id: int):
    """重置企业审核状态（重新审核）"""
    ent = Enterprise.query.get(enterprise_id)
    if not ent or ent.role != 'enterprise':
        return jsonify({'error': '企业不存在'}), 404
    
    ent.verification_status = 'pending'
    ent.is_verified = False
    ent.verified_by = None
    ent.verified_at = None
    ent.rejection_reason = None
    
    db.session.commit()
    
    logger.info('enterprise verification reset id=%s name=%s by=%s', 
                 enterprise_id, ent.name, current_user.id)
    
    return jsonify({'success': True, 'message': '已重置为待审核'})


@admin_panel_bp.route('/api/verifications/stats', methods=['GET'])
@role_required('admin')
def verification_stats():
    """获取审核统计"""
    total = Enterprise.query.filter(Enterprise.role == 'enterprise').count()
    pending = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.verification_status == 'pending'
    ).count()
    approved = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.verification_status == 'approved'
    ).count()
    rejected = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.verification_status == 'rejected'
    ).count()
    
    return jsonify({
        'total': total,
        'pending': pending,
        'approved': approved,
        'rejected': rejected,
    })


# ══════════════════════════════════════════════════════════════════════════
# 企业定期抽查管理
# ══════════════════════════════════════════════════════════════════════════

@admin_panel_bp.route('/enterprise-checks')
@role_required('admin')
def enterprise_checks_page():
    """企业抽查管理页面"""
    from app.services.enterprise_check_service import get_check_config, get_check_history
    config = get_check_config()
    history = get_check_history(limit=20)
    return render_template('admin/enterprise_checks.html', config=config, history=history)


@admin_panel_bp.route('/api/enterprise-checks/config', methods=['GET'])
@role_required('admin')
def get_enterprise_check_config():
    """获取抽查配置"""
    from app.services.enterprise_check_service import get_check_config
    return jsonify(get_check_config())


@admin_panel_bp.route('/api/enterprise-checks/config', methods=['PUT'])
@role_required('admin')
def update_enterprise_check_config():
    """更新抽查配置"""
    from config import EXTERNAL_INTERFACES
    data = request.get_json() or {}
    
    if 'enterprise_check' not in EXTERNAL_INTERFACES:
        EXTERNAL_INTERFACES['enterprise_check'] = {}
    
    allowed_fields = ['enabled', 'check_interval_hours', 'sample_size', 'auto_delist_enabled']
    for field in allowed_fields:
        if field in data:
            EXTERNAL_INTERFACES['enterprise_check'][field] = data[field]
    
    logger.info('enterprise_check_config updated by %s: %s', current_user.id, data)
    
    return jsonify({'success': True, 'message': '配置已更新'})


@admin_panel_bp.route('/api/enterprise-checks/run', methods=['POST'])
@role_required('admin')
def run_enterprise_check():
    """手动执行企业抽查"""
    from app.services.enterprise_check_service import batch_check_enterprises
    result = batch_check_enterprises(force=True)
    return jsonify(result)


@admin_panel_bp.route('/api/enterprise-checks/<int:enterprise_id>', methods=['POST'])
@role_required('admin')
def check_single_enterprise_api(enterprise_id: int):
    """单独检查一家企业"""
    from app.services.enterprise_check_service import check_single_enterprise
    result = check_single_enterprise(enterprise_id)
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@admin_panel_bp.route('/api/enterprise-checks/<int:enterprise_id>/restore', methods=['POST'])
@role_required('admin')
def restore_enterprise_api(enterprise_id: int):
    """恢复企业正常状态"""
    from app.services.enterprise_check_service import restore_enterprise
    data = request.get_json() or {}
    reason = data.get('reason', '')
    result = restore_enterprise(enterprise_id, reason)
    if result.get('success'):
        return jsonify(result)
    else:
        return jsonify(result), 400


@admin_panel_bp.route('/api/enterprise-checks/history', methods=['GET'])
@role_required('admin')
def get_check_history_api():
    """获取抽查历史。format=flat 供 React 风控中心（按企业一行）；默认批量结构兼容 enterprise_checks.html。"""
    from app.services.enterprise_check_service import get_check_history, get_check_history_flat
    limit = request.args.get('limit', 20, type=int)
    fmt = (request.args.get('format') or '').lower()
    if fmt == 'flat':
        history = get_check_history_flat(limit=limit)
    else:
        history = get_check_history(limit=limit)
    return jsonify({'history': history})


@admin_panel_bp.route('/api/enterprise-checks/stats', methods=['GET'])
@role_required('admin')
def enterprise_check_stats():
    """获取企业状态统计"""
    total = Enterprise.query.filter(Enterprise.role == 'enterprise').count()
    bad = ('注销', '吊销', '清算')
    # 未抽查时 business_status 多为 NULL，应计为「正常」而非 0
    active = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.is_dormant.is_(False),
        or_(
            Enterprise.business_status.is_(None),
            Enterprise.business_status == '',
            and_(Enterprise.business_status.isnot(None), ~Enterprise.business_status.in_(bad)),
        ),
    ).count()
    abnormal = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.business_status.in_(list(bad)),
    ).count()
    dormant = Enterprise.query.filter(
        Enterprise.role == 'enterprise',
        Enterprise.is_dormant == True
    ).count()
    
    return jsonify({
        'total': total,
        'active': active,
        'abnormal': abnormal,
        'dormant': dormant,
    })


@admin_panel_bp.route('/api/enterprise-checks/abnormal-list', methods=['GET'])
@role_required('admin')
def enterprise_abnormal_list():
    """获取异常企业列表"""
    abnormal_ents = (
        Enterprise.query
        .filter(
            Enterprise.role == 'enterprise',
            Enterprise.business_status.in_(['注销', '吊销', '清算'])
        )
        .order_by(Enterprise.biz_data_updated_at.desc())
        .limit(50)
        .all()
    )
    return jsonify({
        'items': [
            {
                'id': e.id,
                'name': e.name,
                'business_status': e.business_status,
                'checked_at': e.biz_data_updated_at.strftime('%Y-%m-%d %H:%M') if e.biz_data_updated_at else '',
            }
            for e in abnormal_ents
        ]
    })

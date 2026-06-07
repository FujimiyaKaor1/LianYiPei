"""
链主企业管理路由
Lead Enterprise Management Routes

需求: 53.1-53.7, 54.1-54.7, 55.1-55.7
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from app.services.lead_enterprise_service import LeadEnterpriseService
from app.models import Enterprise

bp = Blueprint('lead_enterprise', __name__, url_prefix='/lead-enterprise')


@bp.route('/onboarding', methods=['GET'])
@login_required
def onboarding_page():
    """
    链主入驻申请页面
    需求: 53.1, 53.2
    """
    # 检查是否已经是链主企业
    if current_user.is_lead_enterprise:
        flash('您已经是链主企业', 'info')
        return redirect(url_for('lead_enterprise.dashboard'))
    
    existing_application = LeadEnterpriseService.get_pending_onboarding_application(
        current_user.id
    )

    return render_template(
        'lead_enterprise/onboarding.html',
        existing_application=existing_application,
    )


@bp.route('/api/onboarding/submit', methods=['POST'])
@login_required
def api_submit_onboarding():
    """
    提交链主入驻申请
    需求: 53.1, 53.2
    """
    data = request.get_json()
    
    result = LeadEnterpriseService.submit_onboarding_application(
        enterprise_id=current_user.id,
        application_data=data
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/admin/applications', methods=['GET'])
@login_required
def admin_applications_page():
    """
    管理员审核链主入驻申请页面
    需求: 53.3
    """
    if current_user.role not in ('admin', 'government'):
        abort(403)
    
    status = request.args.get('status', 'pending')
    applications = LeadEnterpriseService.get_onboarding_applications(status=status)
    
    return render_template('lead_enterprise/admin_applications.html',
                         applications=applications,
                         current_status=status)


@bp.route('/api/admin/applications/<int:application_id>/review', methods=['POST'])
@login_required
def api_review_application(application_id):
    """
    审核链主入驻申请
    需求: 53.3, 53.4
    """
    if current_user.role not in ('admin', 'government'):
        return jsonify({'success': False, 'message': '无权操作'}), 403
    
    data = request.get_json()
    approved = data.get('approved', False)
    review_notes = data.get('review_notes', '')
    
    result = LeadEnterpriseService.review_onboarding_application(
        application_id=application_id,
        reviewer_id=current_user.id,
        approved=approved,
        review_notes=review_notes
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/dashboard', methods=['GET'])
@login_required
def dashboard():
    """
    链主企业控制台
    需求: 53.6, 53.7
    """
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        flash('只有链主企业可以访问', 'warning')
        return redirect(url_for('dashboard.main'))
    
    # 计算贡献度
    contribution = LeadEnterpriseService.calculate_contribution(current_user.id)
    
    # 获取供应商展示控制列表
    display_controls = LeadEnterpriseService.get_supplier_display_controls(current_user.id)
    
    return render_template('lead_enterprise/dashboard.html',
                         contribution=contribution,
                         display_controls=display_controls)


@bp.route('/suppliers/import', methods=['GET', 'POST'])
@login_required
def import_suppliers():
    """
    批量导入供应商名单
    需求: 53.5
    """
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        abort(403)
    
    if request.method == 'GET':
        return render_template('lead_enterprise/import_suppliers.html')
    
    # POST - 处理导入
    data = request.get_json()
    supplier_ids = data.get('supplier_ids', [])
    
    result = LeadEnterpriseService.import_supplier_list(
        lead_enterprise_id=current_user.id,
        supplier_ids=supplier_ids
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/suppliers/display-control', methods=['GET'])
@login_required
def display_control_page():
    """
    供应商展示控制管理页面
    需求: 55.1-55.7
    """
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        flash('只有链主企业可以访问', 'warning')
        return redirect(url_for('dashboard.main'))
    
    display_controls = LeadEnterpriseService.get_supplier_display_controls(current_user.id)
    
    return render_template('lead_enterprise/display_control.html',
                         display_controls=display_controls)


@bp.route('/api/suppliers/<int:supplier_id>/display-control', methods=['POST'])
@login_required
def api_configure_display_control(supplier_id):
    """
    配置供应商展示控制
    需求: 55.1, 55.2, 55.3, 55.4
    """
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        return jsonify({'success': False, 'message': '只有链主企业可以配置展示控制'}), 403
    
    data = request.get_json()
    display_mode = data.get('display_mode', 'public')
    
    result = LeadEnterpriseService.configure_supplier_display(
        lead_enterprise_id=current_user.id,
        supplier_id=supplier_id,
        display_mode=display_mode
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/api/display-control/<int:lead_enterprise_id>/authorize', methods=['POST'])
@login_required
def api_authorize_display_control(lead_enterprise_id):
    """
    供应商授权/撤销展示控制
    需求: 55.5, 55.6
    """
    data = request.get_json()
    authorized = data.get('authorized', False)
    
    result = LeadEnterpriseService.authorize_display_control(
        supplier_id=current_user.id,
        lead_enterprise_id=lead_enterprise_id,
        authorized=authorized
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/api/contribution', methods=['GET'])
@login_required
def api_get_contribution():
    """
    获取链主企业贡献度统计
    需求: 53.7
    """
    if not current_user.is_lead_enterprise and current_user.role not in ('admin',):
        return jsonify({'success': False, 'message': '只有链主企业可以查看贡献度'}), 403
    
    contribution = LeadEnterpriseService.calculate_contribution(current_user.id)
    
    return jsonify({
        'success': True,
        'data': contribution
    }), 200

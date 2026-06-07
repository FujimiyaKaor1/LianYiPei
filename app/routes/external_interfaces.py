"""
外部数据接口配置管理路由
需求: 60.1-60.8
"""
from flask import Blueprint, render_template, request, jsonify
from flask_login import current_user
from app.authz import role_required
from app.services.external_data_service import interface_manager
from app.services.operation_logger import log_operation

bp = Blueprint('external_interfaces', __name__, url_prefix='/admin/external-interfaces')


@bp.route('/')
@role_required('admin')
def index():
    """外部接口配置管理页面"""
    configs = interface_manager.get_all_configs()
    return render_template('external_interfaces/index.html', configs=configs)


@bp.route('/api/configs', methods=['GET'])
@role_required('admin')
def list_configs():
    """获取所有接口配置"""
    configs = interface_manager.get_all_configs()
    return jsonify({'success': True, 'data': configs})


@bp.route('/api/configs/<interface_type>', methods=['GET'])
@role_required('admin')
def get_config(interface_type: str):
    """获取单个接口配置"""
    config = interface_manager.get_config(interface_type)
    if not config:
        return jsonify({'success': False, 'message': '接口配置不存在'}), 404
    return jsonify({'success': True, 'data': config})


@bp.route('/api/configs/<interface_type>', methods=['PUT'])
@role_required('admin')
def update_config(interface_type: str):
    """更新接口配置"""
    data = request.get_json() or {}
    result = interface_manager.update_config(interface_type, data)
    if result['success']:
        log_operation(current_user.id, 'update', 'external_interface_config', None,
                      f'更新外部接口配置: {interface_type}')
    status = 200 if result['success'] else 400
    return jsonify(result), status


@bp.route('/api/configs/<interface_type>/check', methods=['POST'])
@role_required('admin')
def check_availability(interface_type: str):
    """手动测试接口可用性"""
    result = interface_manager.check_interface_availability(interface_type)
    log_operation(current_user.id, 'check', 'external_interface_config', None,
                  f'测试接口可用性: {interface_type} -> {result.get("status")}')
    return jsonify(result)


@bp.route('/api/configs/check-all', methods=['POST'])
@role_required('admin')
def check_all():
    """检查所有接口可用性"""
    results = interface_manager.check_all_interfaces()
    return jsonify({'success': True, 'data': results})

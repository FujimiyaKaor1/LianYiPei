"""
数据授权路由
"""
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from app.services.data_authorization_service import DataAuthorizationService

bp = Blueprint('data_authorization', __name__, url_prefix='/data-authorization')

data_auth_service = DataAuthorizationService()


@bp.route('/')
@login_required
def index():
    """数据授权管理页面"""
    authorizations = data_auth_service.get_authorizations(current_user.id)
    return render_template('data_authorization/manage.html', authorizations=authorizations)


@bp.route('/api/data-authorization', methods=['POST'])
@login_required
def authorize_data():
    """
    授权数据接入
    
    POST /api/data-authorization
    Body: {
        "data_type": "power_consumption" | "invoice_data"
    }
    """
    data = request.get_json()
    
    if not data or 'data_type' not in data:
        return jsonify({
            'success': False,
            'message': '缺少必需参数: data_type'
        }), 400
    
    result = data_auth_service.authorize_data(
        enterprise_id=current_user.id,
        data_type=data['data_type']
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/api/data-authorization/<int:auth_id>', methods=['DELETE'])
@login_required
def revoke_authorization(auth_id):
    """
    撤销数据授权
    
    DELETE /api/data-authorization/:id
    """
    result = data_auth_service.revoke_authorization(
        authorization_id=auth_id,
        enterprise_id=current_user.id
    )
    
    if result['success']:
        return jsonify(result), 200
    else:
        return jsonify(result), 400


@bp.route('/api/data-authorization', methods=['GET'])
@login_required
def get_authorizations():
    """
    获取授权列表
    
    GET /api/data-authorization
    """
    authorizations = data_auth_service.get_authorizations(current_user.id)
    
    return jsonify({
        'success': True,
        'data': authorizations
    }), 200

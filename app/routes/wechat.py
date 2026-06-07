"""
微信推送相关路由
"""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.services.wechat_push_service import wechat_push_service
from app.models import db, Enterprise
import logging

logger = logging.getLogger(__name__)

# 使用 /api/wechat 前缀，与前端 Vite 代理 /api 一致，开发环境无需单独代理 /wechat
bp = Blueprint('wechat', __name__, url_prefix='/api/wechat')


@bp.route('/settings')
@login_required
def settings():
    """微信推送设置页面"""
    return render_template('wechat/settings.html')


@bp.route('/bind', methods=['POST'])
@login_required
def bind():
    """绑定微信账号"""
    try:
        data = request.get_json()
        wechat_type = data.get('wechat_type')  # work_wechat 或 service_account
        wechat_openid = data.get('wechat_openid')
        wechat_userid = data.get('wechat_userid')  # 企业微信需要
        
        if not wechat_type or not wechat_openid:
            return jsonify({
                'success': False,
                'message': '缺少必要参数'
            }), 400
        
        # 绑定微信账号
        success = wechat_push_service.bind_wechat_account(
            enterprise_id=current_user.id,
            wechat_type=wechat_type,
            wechat_openid=wechat_openid,
            wechat_userid=wechat_userid
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '微信账号绑定成功'
            })
        else:
            return jsonify({
                'success': False,
                'message': '绑定失败，请稍后重试'
            }), 500
            
    except Exception as e:
        logger.error(f"Error binding WeChat account: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/bind-openid', methods=['POST'])
@login_required
def bind_openid():
    """手动绑定 OpenID（Demo 模式）"""
    try:
        data = request.get_json()
        from app.services.wechat_push_service import bind_openid as _bind, normalize_wechat_openid

        openid = normalize_wechat_openid(data.get('openid') or '')
        if not openid:
            return jsonify({'success': False, 'message': '请提供有效的 OpenID（勿含空格，可从测试号后台完整复制）'}), 400

        ok = _bind(current_user.id, openid)
        if ok:
            return jsonify({'success': True, 'message': '绑定成功'})
        return jsonify({'success': False, 'message': '绑定失败，请稍后重试'}), 500
    except Exception as e:
        logger.error(f'Error binding openid: {e}')
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/unbind', methods=['POST'])
@login_required
def unbind():
    """解绑微信账号"""
    try:
        success = wechat_push_service.unbind_wechat_account(current_user.id)
        
        if success:
            return jsonify({
                'success': True,
                'message': '微信账号已解绑'
            })
        else:
            return jsonify({
                'success': False,
                'message': '解绑失败'
            }), 500
            
    except Exception as e:
        logger.error(f"Error unbinding WeChat account: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/preference', methods=['POST'])
@login_required
def set_preference():
    """设置推送偏好"""
    try:
        data = request.get_json()
        preference = data.get('preference')  # all, urgent_only, off
        
        if preference not in ['all', 'urgent_only', 'off']:
            return jsonify({
                'success': False,
                'message': '无效的推送偏好'
            }), 400
        
        success = wechat_push_service.set_push_preference(
            enterprise_id=current_user.id,
            preference=preference
        )
        
        if success:
            return jsonify({
                'success': True,
                'message': '推送偏好已更新'
            })
        else:
            return jsonify({
                'success': False,
                'message': '更新失败'
            }), 500
            
    except Exception as e:
        logger.error(f"Error setting push preference: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@bp.route('/test-push', methods=['POST'])
@login_required
def test_push():
    """测试推送（微信失败时会回退站内消息，仍返回 200 并说明渠道）"""
    try:
        try:
            link = url_for('wechat.settings', _external=True)
        except Exception:
            link = ''

        result = wechat_push_service.push_message(
            enterprise_id=current_user.id,
            title='测试推送',
            content='这是一条测试推送消息，如果您收到此消息，说明微信推送配置成功！',
            url=link or None,
            is_urgent=False,
        )

        if result.get('success'):
            body = {
                'success': True,
                'message': (result.get('message') or '测试推送已处理').strip(),
                'channel': result.get('channel'),
                'wechat_ok': bool(result.get('wechat_ok')),
            }
            if not result.get('wechat_ok'):
                body['wechat_errcode'] = result.get('wechat_errcode')
                body['wechat_errmsg'] = result.get('wechat_errmsg')
                body['wechat_detail'] = result.get('wechat_detail')
                body['wechat_private_template_ids'] = result.get('wechat_private_template_ids')
                body['wechat_template_list_api_error'] = result.get('wechat_template_list_api_error')
                body['wechat_config_appid_prefix'] = result.get('wechat_config_appid_prefix')
                body['wechat_attempted_template_id'] = result.get('wechat_attempted_template_id')
            return jsonify(body)

        return jsonify({
            'success': False,
            'message': result.get('message') or '推送失败，请检查配置与后端日志',
            'wechat_ok': False,
        }), 500

    except Exception as e:
        logger.error('Error testing push: %s', e, exc_info=True)
        return jsonify({
            'success': False,
            'message': str(e),
        }), 500


@bp.route('/callback/work-wechat', methods=['GET', 'POST'])
def work_wechat_callback():
    """企业微信回调接口（用于验证和接收消息）"""
    if request.method == 'GET':
        # 验证URL
        msg_signature = request.args.get('msg_signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        
        # TODO: 实现签名验证逻辑
        # 这里简化处理，实际应该验证签名
        return echostr
    
    elif request.method == 'POST':
        # 接收企业微信推送的消息
        # TODO: 实现消息处理逻辑
        return 'success'


@bp.route('/callback/service-account', methods=['GET', 'POST'])
def service_account_callback():
    """微信服务号回调接口（用于验证和接收消息）"""
    if request.method == 'GET':
        # 验证URL
        signature = request.args.get('signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        
        # TODO: 实现签名验证逻辑
        return echostr
    
    elif request.method == 'POST':
        # 接收微信服务号推送的消息
        # TODO: 实现消息处理逻辑
        return 'success'

"""
微信推送相关路由
"""
import hashlib
import hmac
from datetime import datetime

from flask import Blueprint, current_app, make_response, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.services.wechat_push_service import wechat_push_service
from app.models import db, Enterprise
import logging

logger = logging.getLogger(__name__)

# 使用 /api/wechat 前缀，与前端 Vite 代理 /api 一致，开发环境无需单独代理 /wechat
bp = Blueprint('wechat', __name__, url_prefix='/api/wechat')


def _wechat_callback_token() -> str:
    return (current_app.config.get('WECHAT_CALLBACK_TOKEN') or '').strip()


def _verify_wechat_signature() -> bool:
    token = _wechat_callback_token()
    if not token:
        logger.warning('WECHAT_CALLBACK_TOKEN 未配置，跳过微信回调签名校验')
        return True

    signature = (request.args.get('signature') or '').strip()
    timestamp = (request.args.get('timestamp') or '').strip()
    nonce = (request.args.get('nonce') or '').strip()
    if not signature or not timestamp or not nonce:
        return False

    raw = ''.join(sorted([token, timestamp, nonce]))
    expected = hashlib.sha1(raw.encode('utf-8')).hexdigest()
    return hmac.compare_digest(expected, signature)


def _xml_response(body: str, status: int = 200):
    resp = make_response(body, status)
    resp.headers['Content-Type'] = 'application/xml; charset=utf-8'
    return resp


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


@bp.route('/test-email', methods=['POST'])
@login_required
def test_email():
    """发送测试邮件到当前登录企业在个人账户中保存的邮箱。"""
    try:
        from app.services.email_service import send_email

        ent = Enterprise.query.get(current_user.id)
        if not ent:
            return jsonify({'success': False, 'message': '用户不存在'}), 404

        extras = dict(ent.extras or {})
        to_email = (extras.get('email') or '').strip()
        if not to_email or '@' not in to_email:
            return jsonify({
                'success': False,
                'message': '当前账户未绑定有效邮箱，请先在「个人账户」中填写邮箱',
            }), 400

        send_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        subject = '链易配 - 测试邮件'
        text_body = (
            '您好！\n\n'
            '这是一封来自链易配平台的测试邮件。\n'
            '如果您收到此邮件，说明邮件推送配置成功。\n\n'
            f'发送时间：{send_time}\n'
            '祝您使用愉快！\n\n'
            '—— 链易配平台'
        )
        html_body = f'''
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px 24px;
                    background:#f9fafb;border-radius:12px;border:1px solid #e5e7eb;">
          <h2 style="color:#2563eb;margin-bottom:20px;">链易配 - 测试邮件</h2>
          <p style="color:#374151;line-height:1.8;">您好！</p>
          <p style="color:#374151;line-height:1.8;">这是一封来自<strong>链易配平台</strong>的测试邮件。</p>
          <p style="color:#374151;line-height:1.8;">如果您收到此邮件，说明<strong>邮件推送配置成功</strong>。</p>
          <div style="margin:24px 0;padding:16px;background:#eff6ff;border-radius:8px;border-left:4px solid #2563eb;">
            <p style="color:#1d4ed8;font-size:13px;margin:0;">发送时间：{send_time}</p>
          </div>
          <p style="color:#9ca3af;font-size:12px;">—— 链易配平台</p>
        </div>
        '''

        ok, err = send_email(to_email, subject, text_body, html_body)
        if ok:
            return jsonify({
                'success': True,
                'message': f'测试邮件已发送至 {to_email}，请查收',
            })

        return jsonify({
            'success': False,
            'message': f'发送失败：{err}',
            'hint': '请检查 .env 中 SMTP_* 配置是否正确；QQ/163 邮箱需使用「授权码」而非登录密码',
        }), 500
    except Exception as e:
        logger.error('Error testing email: %s', e, exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


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
        echostr = request.args.get('echostr', '')

        if not _verify_wechat_signature():
            return 'invalid signature', 403
        return echostr
    
    elif request.method == 'POST':
        if not _verify_wechat_signature():
            logger.warning('微信服务号回调签名校验失败 remote=%s', request.remote_addr)
            return 'invalid signature', 403

        try:
            from app.services.wechat_inbound_service import (
                WeChatInboundError,
                build_text_reply,
                handle_wechat_message,
                parse_wechat_xml,
            )

            incoming = parse_wechat_xml(request.get_data() or b'')
            reply = handle_wechat_message(incoming)
            return _xml_response(
                build_text_reply(
                    to_user=incoming.get('from_user', ''),
                    from_user=incoming.get('to_user', ''),
                    content=reply,
                )
            )
        except WeChatInboundError as e:
            logger.warning('微信服务号回调 XML 无效: %s', e)
            return 'success'
        except Exception as e:
            logger.error('微信服务号入站处理失败: %s', e, exc_info=True)
            return 'success'

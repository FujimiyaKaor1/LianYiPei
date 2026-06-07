"""
微信推送服务（极简测试号版本）
只使用微信服务号 / 模板消息 API，适合 Demo 快速验证
"""
import os
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple

from dotenv import dotenv_values
from flask import current_app
from app.models import db, Enterprise
from app.services.message_service import MessageService

logger = logging.getLogger(__name__)


def normalize_wechat_openid(raw: Optional[str]) -> str:
    """去掉首尾与中间空白（避免复制 OpenID 时夹入空格导致微信报 invalid openid）。"""
    if not raw:
        return ''
    return ''.join(str(raw).split())


def normalize_template_id(raw: Optional[str]) -> str:
    """去掉 BOM、零宽字符与首尾空白，避免从网页复制模板 ID 时肉眼不可见字符导致 40037。"""
    if not raw:
        return ''
    s = str(raw).strip().replace('\ufeff', '')
    for z in ('\u200b', '\u200c', '\u200d'):
        s = s.replace(z, '')
    return s.strip()


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ENV_PATH = _PROJECT_ROOT / '.env'


def _load_project_dotenv_flat() -> Dict[str, str]:
    """直接解析项目根 .env，不依赖 os.environ（避免与系统/IDE/多进程注入不一致）。"""
    if not _PROJECT_ENV_PATH.is_file():
        return {}
    out: Dict[str, str] = {}
    for k, v in dotenv_values(_PROJECT_ENV_PATH).items():
        if k is None or v is None:
            continue
        ks = str(k).strip()
        if not ks or ks.startswith('#'):
            continue
        vs = str(v).strip()
        if (vs.startswith('"') and vs.endswith('"')) or (vs.startswith("'") and vs.endswith("'")):
            vs = vs[1:-1].strip()
        out[ks] = vs
    return out


def _flask_config_get(key: str) -> str:
    try:
        v = current_app.config.get(key)
        return (str(v).strip() if v is not None else '') or ''
    except RuntimeError:
        return ''


def _wechat_credentials() -> Tuple[str, str, str, str]:
    """
    (appid, secret, template_id, template_data_keys_csv)。
    优先级：项目根 .env 文件 > Flask config > os.environ。
    """
    f = _load_project_dotenv_flat()

    def pick(file_key: str, cfg_key: str) -> str:
        v = (f.get(file_key) or '').strip()
        if v:
            return v
        v = _flask_config_get(cfg_key)
        if v:
            return v
        return (os.environ.get(cfg_key) or '').strip()

    appid = pick('WECHAT_SERVICE_APPID', 'WECHAT_SERVICE_APPID')
    secret = pick('WECHAT_SERVICE_SECRET', 'WECHAT_SERVICE_SECRET')
    tid = normalize_template_id(pick('WECHAT_TEMPLATE_ID', 'WECHAT_TEMPLATE_ID'))
    keys = pick('WECHAT_TEMPLATE_DATA_KEYS', 'WECHAT_TEMPLATE_DATA_KEYS')
    return appid, secret, tid, keys


def _private_template_list_diag(token: str, attempted_id: str) -> dict:
    """
    40037 时拉取当前 token 下微信登记的模板 ID。
    返回 dict（同时写入日志），供接口回传给前端，避免仅依赖终端输出。
    """
    out: dict = {
        'attempted_template_id': attempted_id,
        'template_ids': [],
        'list_api_error': None,
        'fetch_exception': None,
    }
    try:
        r = requests.get(
            'https://api.weixin.qq.com/cgi-bin/template/get_all_private_template',
            params={'access_token': token},
            timeout=12,
        )
        data = r.json()
        if data.get('errcode'):
            out['list_api_error'] = {'errcode': data.get('errcode'), 'errmsg': data.get('errmsg')}
            logger.error('[WeChatPush] 拉取模板列表失败: %s', data)
            return out
        tlist = data.get('template_list') or []
        ids = [str(t.get('template_id')) for t in tlist if t.get('template_id')]
        out['template_ids'] = ids
        logger.error(
            '[WeChatPush] 40037 诊断：attempted=%r len=%s；微信登记模板数=%s；ids=%s',
            attempted_id,
            len(attempted_id or ''),
            len(ids),
            ids,
        )
        if attempted_id and ids and attempted_id not in ids:
            logger.error(
                '[WeChatPush] .env 中 WECHAT_TEMPLATE_ID 不在微信返回列表中，请改为列表中的整段 ID。'
            )
    except Exception as e:
        out['fetch_exception'] = str(e)
        logger.error('[WeChatPush] 拉取模板列表异常: %s', e)
    return out


def _template_data_keys() -> tuple[str, str]:
    _, _, _, raw = _wechat_credentials()
    raw = raw or 'thing1,time2'
    parts = [p.strip() for p in str(raw).split(',') if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], ''
    return 'thing1', 'time2'


def _clip_template_value(key: str, text: str) -> str:
    """
    微信模板字段按「类型」限长；thing 及常见「内容」类多为 20 字（含中英文）。
    键名为 content 时后台多为事物类，同样按 20 字截断以防 47003。
    """
    if not text:
        return ''
    k = (key or '').lower()
    limit = 20 if (k.startswith('thing') or k == 'content') else 200
    text = str(text).strip()
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 1] + '…'


# ── 全局 Token 缓存（避免频繁刷新；按 appid+secret 区分，避免换号后沿用旧 token）──

_token_cache: Dict[str, Optional[object]] = {
    'token': None,
    'expires_at': None,  # datetime
    'cred_key': None,  # (appid, secret)
}


def _get_access_token() -> Optional[str]:
    """
    获取 access_token，带缓存（有效期 7200s，提前 5min 过期）。
    appid/secret 与发模板消息使用同一套 _wechat_credentials()。
    """
    now = datetime.utcnow()
    appid, secret, _, _ = _wechat_credentials()
    cred_key = (appid, secret)

    exp = _token_cache['expires_at']
    if (
        _token_cache['token']
        and isinstance(exp, datetime)
        and _token_cache.get('cred_key') == cred_key
        and now < exp
    ):
        return str(_token_cache['token'])

    if not appid or not secret:
        logger.error('[WeChatPush] WECHAT_SERVICE_APPID 或 WECHAT_SERVICE_SECRET 未配置')
        return None

    try:
        resp = requests.get(
            'https://api.weixin.qq.com/cgi-bin/token',
            params={'grant_type': 'client_credential', 'appid': appid, 'secret': secret},
            timeout=10,
        )
        data = resp.json()
        if 'access_token' in data:
            _token_cache['token'] = data['access_token']
            _token_cache['cred_key'] = cred_key
            # 7200s 有效期，提前 5min 过期
            _token_cache['expires_at'] = now + timedelta(seconds=7200 - 300)
            logger.info(
                '[WeChatPush] access_token 已刷新 appid=%s env_file=%s',
                (appid[:8] + '…') if len(appid) > 8 else appid,
                str(_PROJECT_ENV_PATH),
            )
            return str(_token_cache['token'])
        else:
            logger.error(f'[WeChatPush] 获取 access_token 失败: {data.get("errmsg", data)}')
            return None
    except Exception as e:
        logger.error(f'[WeChatPush] 请求 access_token 异常: {e}')
        return None


def _invalidate_access_token_cache() -> None:
    _token_cache['token'] = None
    _token_cache['expires_at'] = None
    _token_cache['cred_key'] = None


def _send_template_message_once(token: str, openid: str, template_id: str, title: str, content: str, url: str = '') -> dict:
    """单次模板发送，返回微信 JSON（含 errcode）。"""
    main_key, time_key = _template_data_keys()
    combined = f'{title}: {content}' if content else str(title)
    data = {
        main_key: {'value': _clip_template_value(main_key, combined), 'color': '#FF0000'},
    }
    if time_key:
        time_val = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        data[time_key] = {
            'value': _clip_template_value(time_key, time_val),
            'color': '#173177',
        }
    api_url = f'https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}'
    payload = {
        'touser': openid,
        'template_id': template_id,
        'data': data,
    }
    if url and str(url).strip():
        payload['url'] = url.strip()
    resp = requests.post(api_url, json=payload, timeout=15)
    try:
        return resp.json()
    except ValueError:
        logger.error('[WeChatPush] 模板接口返回非 JSON: %s', resp.text[:500])
        return {'errcode': -1, 'errmsg': 'invalid_json_response'}


def _send_template_message(
    openid: str, template_id: str, title: str, content: str, url: str = ''
) -> tuple[bool, dict]:
    """
    发送微信模板消息。
    返回 (是否成功, 微信侧最后一次响应 dict，失败时含 errcode/errmsg)。
    """
    last: dict = {}
    for attempt in range(2):
        token = _get_access_token()
        if not token:
            return False, {'errcode': -1, 'errmsg': 'no_access_token'}
        try:
            last = _send_template_message_once(token, openid, template_id, title, content, url or '')
            err = last.get('errcode')
            if err == 0:
                logger.info('[WeChatPush] 模板消息已发送至 openid=%s', openid)
                return True, last
            # access_token 失效：清缓存后重试一次
            if err in (40001, 42001, 40014) and attempt == 0:
                logger.warning('[WeChatPush] access_token 失效(err=%s)，刷新后重试', err)
                _invalidate_access_token_cache()
                continue
            logger.error(
                '[WeChatPush] 模板消息发送失败: errcode=%s errmsg=%s template_id_len=%s template_id_tail=%s',
                err,
                last.get('errmsg'),
                len(template_id),
                template_id[-12:] if len(template_id) > 12 else template_id,
            )
            if err == 40037:
                diag = _private_template_list_diag(token, template_id)
                last = {**last, '_template_diag': diag}
                _invalidate_access_token_cache()
            return False, last
        except Exception as e:
            logger.error('[WeChatPush] 发送模板消息异常: %s', e)
            return False, {'errcode': -1, 'errmsg': str(e)}
    return False, last


# ── 绑定 / 解绑 / 偏好 ───────────────────────────────────���───────────────────

def bind_openid(enterprise_id: int, openid: str) -> bool:
    """手动绑定 openid（Demo 模式）"""
    try:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return False
        clean = normalize_wechat_openid(openid)
        if not clean:
            return False
        ent.wechat_service_openid = clean
        ent.wechat_bound = True
        ent.wechat_bound_at = datetime.utcnow()
        db.session.commit()
        logger.info(f'[WeChatPush] 企业 {enterprise_id} 绑定 openid={clean}')
        return True
    except Exception as e:
        logger.error(f'[WeChatPush] 绑定失败: {e}')
        db.session.rollback()
        return False


def unbind_wechat_account(enterprise_id: int) -> bool:
    """解绑微信账号"""
    try:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return False
        ent.wechat_bound = False
        ent.wechat_service_openid = None
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f'[WeChatPush] 解绑失败: {e}')
        db.session.rollback()
        return False


def set_push_preference(enterprise_id: int, preference: str) -> bool:
    """设置推送偏好"""
    try:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return False
        ent.wechat_push_preference = preference
        db.session.commit()
        return True
    except Exception as e:
        logger.error(f'[WeChatPush] 设置偏好失败: {e}')
        db.session.rollback()
        return False


# ── 核心推送逻辑 ────────────────────────────────────────────────────────────

def should_push(ent: Enterprise, is_urgent: bool) -> bool:
    """判断是否应该推送（参考用户偏好）"""
    if not ent.wechat_bound:
        return False
    pref = getattr(ent, 'wechat_push_preference', 'all')
    if pref == 'off':
        return False
    if pref == 'urgent_only' and not is_urgent:
        return False
    return True


def push_message(
    enterprise_id: int,
    title: str,
    content: str,
    url: str = None,
    is_urgent: bool = False,
) -> Dict:
    """
    推送消息到微信模板消息。
    Returns: {'success': bool, 'message': str, 'fallback_to_site': bool}
    """
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return {'success': False, 'message': '企业不存在', 'fallback_to_site': True, 'wechat_ok': False}

    if not should_push(ent, is_urgent):
        return {'success': False, 'message': '推送已关闭或未绑定', 'fallback_to_site': False, 'wechat_ok': False}

    openid = normalize_wechat_openid(ent.wechat_service_openid)
    if not openid:
        return {'success': False, 'message': '未绑定 openid', 'fallback_to_site': True, 'wechat_ok': False}

    _, _, template_id, _ = _wechat_credentials()
    if not template_id:
        fb_ok = _fallback_site_message(enterprise_id, 'system', title, content, url, is_urgent)
        return {
            'success': fb_ok,
            'message': '未配置 WECHAT_TEMPLATE_ID，已写入站内消息' if fb_ok else '未配置模板且站内消息写入失败',
            'fallback_to_site': True,
            'channel': 'site' if fb_ok else None,
            'wechat_ok': False,
        }

    ok, wx_resp = _send_template_message(openid, template_id, title, content, url or '')
    template_diag = wx_resp.pop('_template_diag', None)

    if ok:
        return {
            'success': True,
            'message': '微信推送成功',
            'fallback_to_site': False,
            'channel': 'wechat',
            'wechat_ok': True,
        }

    # 微信失败 -> 回退站内；若站内成功，整体仍视为成功（避免接口误报 500）
    fb_ok = _fallback_site_message(enterprise_id, 'system', title, content, url, is_urgent)
    wx_err = wx_resp.get('errcode')
    wx_msg = wx_resp.get('errmsg') or ''
    detail = f'微信接口 errcode={wx_err} errmsg={wx_msg}' if wx_err is not None else ''
    if wx_err == 40037:
        ids_line = ''
        if template_diag and template_diag.get('template_ids'):
            ids_line = ' 微信当前登记的模板ID：' + ' | '.join(template_diag['template_ids'])
        elif template_diag and template_diag.get('list_api_error'):
            ids_line = f" 拉取模板列表失败：{template_diag['list_api_error']}"
        elif template_diag and template_diag.get('fetch_exception'):
            ids_line = f" 拉取模板列表异常：{template_diag['fetch_exception']}"
        hint = (
            '已写入消息中心。errcode=40037（invalid template_id）。'
            '请核对下方返回的「微信登记的模板ID」与 .env 中 WECHAT_TEMPLATE_ID 是否完全一致（整段复制）。'
            + ids_line
        )
    else:
        hint = (
            '已写入消息中心（微信模板未送达）。请确认 WECHAT_TEMPLATE_DATA_KEYS 与模板 {{关键词.DATA}} 一致；'
            'content/thing 类正文一般不超过 20 字。'
        )
    appid_dbg, _, _, _ = _wechat_credentials()
    return {
        'success': fb_ok,
        'message': hint if fb_ok else '微信与站内消息均失败，请查看后端日志',
        'fallback_to_site': True,
        'channel': 'site' if fb_ok else None,
        'wechat_ok': False,
        'wechat_errcode': wx_err,
        'wechat_errmsg': wx_msg,
        'wechat_detail': detail,
        'wechat_private_template_ids': (template_diag or {}).get('template_ids'),
        'wechat_template_list_api_error': (template_diag or {}).get('list_api_error'),
        'wechat_config_appid_prefix': (appid_dbg[:10] + '…') if len(appid_dbg) > 10 else appid_dbg,
        'wechat_attempted_template_id': (template_diag or {}).get('attempted_template_id'),
    }


def push_with_fallback(
    enterprise_id: int,
    message_type: str,
    title: str,
    content: str,
    url: str = None,
    is_urgent: bool = False,
) -> bool:
    """
    推送消息，失败时自动回退到站内消息。
    微信失败但站内写入成功时返回 True。
    """
    result = push_message(enterprise_id, title, content, url, is_urgent)
    return bool(result.get('success'))


def _fallback_site_message(
    enterprise_id: int,
    message_type: str,
    title: str,
    content: str,
    url: str = None,
    is_urgent: bool = False,
) -> bool:
    """微信推送失败时，回退创建站内消息。返回是否写入成功。"""
    try:
        MessageService.create_message(
            recipient_id=enterprise_id,
            message_type=message_type,
            title=title,
            content=content,
            link_url=url,
            priority='high' if is_urgent else 'normal',
        )
        logger.info('[WeChatPush] fallback 站内消息已创建，企业=%s', enterprise_id)
        return True
    except Exception as e:
        logger.error('[WeChatPush] fallback 站内消息创建失败: %s', e)
        return False


# ── 全局单例（兼容旧代码）────────────────────────────────────────────────────
class WeChatPushService:
    """保留旧类名，委托到模块级函数，保持向后兼容"""

    PREFERENCE_ALL = 'all'
    PREFERENCE_URGENT_ONLY = 'urgent_only'
    PREFERENCE_OFF = 'off'
    PUSH_TYPE_SERVICE_ACCOUNT = 'service_account'
    PUSH_TYPE_WORK_WECHAT = 'work_wechat'

    def bind_wechat_account(self, enterprise_id, wechat_type, wechat_openid, wechat_userid=None):
        return bind_openid(enterprise_id, wechat_openid)

    def unbind_wechat_account(self, enterprise_id):
        return unbind_wechat_account(enterprise_id)

    def set_push_preference(self, enterprise_id, preference):
        return set_push_preference(enterprise_id, preference)

    def should_push(self, enterprise, is_urgent):
        return should_push(enterprise, is_urgent)

    def push_message(self, enterprise_id, title, content, url=None, is_urgent=False, retry_count=0):
        return push_message(enterprise_id, title, content, url, is_urgent)

    def push_with_fallback(self, enterprise_id, message_type, title, content, url=None, is_urgent=False):
        return push_with_fallback(enterprise_id, message_type, title, content, url, is_urgent)


wechat_push_service = WeChatPushService()
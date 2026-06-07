"""
统一错误处理中间件
- 定义错误码体系（1001-9999）
- 统一 JSON 错误响应格式
- 请求日志记录
"""
from __future__ import annotations

import time
import logging
from flask import Flask, jsonify, request, g

logger = logging.getLogger(__name__)

# ── 错误码定义 ────────────────────────────────────────────────────────────

# 通用错误 1001-1099
ERR_MISSING_PARAM       = 1001  # 缺少必填参数
ERR_INVALID_PARAM       = 1002  # 参数格式无效
ERR_UNAUTHORIZED        = 1003  # 未登录
ERR_FORBIDDEN           = 1004  # 权限不足
ERR_NOT_FOUND           = 1005  # 资源不存在
ERR_METHOD_NOT_ALLOWED  = 1006  # 请求方法不允许
ERR_INTERNAL            = 1007  # 服务器内部错误

# 信用分错误 1101-1199
ERR_CREDIT_SCORE_LOW    = 1101  # 信用分不足
ERR_QUOTE_LIMIT         = 1102  # 报价次数已达上限
ERR_CREDIT_RECORD_NOT_FOUND = 1103  # 信用分记录不存在

# 报价错误 1201-1299
ERR_QUOTE_PRICE_INVALID = 1201  # 报价金额无效
ERR_INQUIRY_NOT_FOUND   = 1202  # 询价单不存在
ERR_QUOTE_NOT_FOUND     = 1203  # 报价记录不存在

# 消息错误 1301-1399
ERR_MESSAGE_NOT_FOUND   = 1301  # 消息不存在
ERR_MESSAGE_FORBIDDEN   = 1302  # 无权操作该消息

# 撮合码错误 1401-1499
ERR_CODE_NOT_FOUND      = 1401  # 撮合码不存在
ERR_CODE_API_KEY_INVALID = 1402  # API密钥无效

# 业务错误 2001-2999
ERR_ENTERPRISE_NOT_FOUND = 2001  # 企业不存在
ERR_DUPLICATE_OPERATION  = 2002  # 重复操作


class APIError(Exception):
    """统一 API 异常类。"""

    def __init__(self, message: str, code: int = ERR_INTERNAL, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status

    @staticmethod
    def not_found(message: str = '资源不存在', code: int = ERR_NOT_FOUND) -> 'APIError':
        return APIError(message, code=code, http_status=404)

    @staticmethod
    def forbidden(message: str = '权限不足', code: int = ERR_FORBIDDEN) -> 'APIError':
        return APIError(message, code=code, http_status=403)

    @staticmethod
    def bad_request(message: str, code: int = ERR_INVALID_PARAM) -> 'APIError':
        return APIError(message, code=code, http_status=400)


def _error_response(message: str, code: int, http_status: int):
    return jsonify({
        'success': False,
        'error': {
            'code': code,
            'message': message,
        }
    }), http_status


def register_error_handlers(app: Flask):
    """注册全局错误处理器和请求日志中间件。"""

    # ── 请求日志 ─────────────────────────────────────────────────────────

    @app.before_request
    def _log_request_start():
        g._request_start_time = time.monotonic()

    @app.after_request
    def _log_request_end(response):
        if request.path.startswith('/api/'):
            elapsed_ms = round((time.monotonic() - g.get('_request_start_time', time.monotonic())) * 1000, 1)
            logger.info(
                '%s %s %s %dms',
                request.method,
                request.path,
                response.status_code,
                elapsed_ms,
            )
        return response

    # ── 自定义 APIError ───────────────────────────────────────────────────

    @app.errorhandler(APIError)
    def handle_api_error(exc: APIError):
        return _error_response(exc.message, exc.code, exc.http_status)

    # ── HTTP 标准错误（仅对 /api/ 路径返回 JSON） ─────────────────────────

    @app.errorhandler(400)
    def handle_400(exc):
        if request.path.startswith('/api/'):
            return _error_response('请求参数错误', ERR_MISSING_PARAM, 400)
        return exc

    @app.errorhandler(401)
    def handle_401(exc):
        if request.path.startswith('/api/'):
            return _error_response('请先登录', ERR_UNAUTHORIZED, 401)
        return exc

    @app.errorhandler(403)
    def handle_403(exc):
        if request.path.startswith('/api/'):
            return _error_response('权限不足，禁止访问', ERR_FORBIDDEN, 403)
        return exc

    @app.errorhandler(404)
    def handle_404(exc):
        if request.path.startswith('/api/'):
            return _error_response('接口或资源不存在', ERR_NOT_FOUND, 404)
        return exc

    @app.errorhandler(405)
    def handle_405(exc):
        if request.path.startswith('/api/'):
            return _error_response('请求方法不允许', ERR_METHOD_NOT_ALLOWED, 405)
        return exc

    @app.errorhandler(429)
    def handle_429(exc):
        if request.path.startswith('/api/'):
            return _error_response('请求过于频繁，请稍后再试', ERR_QUOTE_LIMIT, 429)
        return exc

    @app.errorhandler(500)
    def handle_500(exc):
        logger.exception('Internal server error: %s %s', request.method, request.path)
        if request.path.startswith('/api/'):
            return _error_response('服务器内部错误', ERR_INTERNAL, 500)
        return exc

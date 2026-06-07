"""
部分浏览器扩展（如教育类 App 的网页脚本）会向「当前打开的站点源」请求
`/hybridaction/...` 并使用 JSONP（`__callback__`）回调。
本地开发访问 http://127.0.0.1:5000 时，这些请求会打到 Flask，默认 404，
并在扩展脚本内触发 `v[w] is not a function` 类错误。

本蓝图与链易配业务无关，仅返回空 JSON / JSONP，减少终端与控制台噪音。
对外部域名的统计请求 Flask 无法代理，请关闭相关扩展或使用无痕窗口。
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify, request

bp = Blueprint("browser_extension_noop", __name__)


def _noop_response():
    if request.method == "OPTIONS":
        return "", 204
    cb = request.args.get("__callback__") or request.form.get("__callback__")
    if cb:
        return Response(
            f"{cb}({{}});",
            mimetype="application/javascript; charset=utf-8",
        )
    return jsonify({})


@bp.route(
    "/hybridaction/<path:_action>",
    methods=["GET", "POST", "OPTIONS", "HEAD"],
)
def noop_hybridaction(_action: str):
    if request.method == "HEAD":
        return "", 204
    return _noop_response()

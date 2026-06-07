"""RBAC：基于 Flask-Login 的角色校验。"""
from __future__ import annotations

from functools import wraps

from flask import abort, flash, jsonify, redirect, request
from flask_login import current_user, login_required


def user_effective_role(user) -> str:
    """返回 'admin' | 'enterprise'。government 与 admin 等价；兼容仅有 is_admin 而无 role 列的旧数据。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return "enterprise"
    r = getattr(user, "role", None)
    if r == "government":
        return "admin"
    if r in ("admin", "enterprise"):
        return r
    return "admin" if getattr(user, "is_admin", False) else "enterprise"


def user_session_role(user) -> str:
    """SPA 用原始角色：'admin' | 'government' | 'enterprise'（不与 government 合并）。"""
    if user is None or not getattr(user, "is_authenticated", False):
        return "enterprise"
    r = getattr(user, "role", None)
    if r in ("admin", "government", "enterprise"):
        return r
    return "admin" if getattr(user, "is_admin", False) else "enterprise"


def _path_is_api_prefix(path: str) -> bool:
    """顶层 /api/… JSON 接口（不含 /dashboard/api/…）。"""
    return path == "/api" or path.startswith("/api/")


def _path_is_dashboard_area(path: str) -> bool:
    return path == "/dashboard" or path.startswith("/dashboard/")


def _path_is_enterprise_business(path: str) -> bool:
    if path == "/enterprise" or path.startswith("/enterprise/"):
        return True
    if path == "/demand" or path.startswith("/demand/"):
        return True
    if path == "/match" or path.startswith("/match/"):
        return True
    return False


def _role_mismatch_response(required_role: str, effective: str):
    """
    核心原则：API（/api/）→ JSON 403；政府页（/dashboard/）企业越权 → 302；
    企业业务页（/enterprise|/demand|/match）管理员越权 → 302；其余 abort(403)。
    """
    path = request.path

    if _path_is_dashboard_area(path):
        if required_role == "admin" and effective == "enterprise":
            flash("您没有权限访问政府大屏，已为您跳转", "warning")
            return redirect("/enterprise/profile")

    if _path_is_enterprise_business(path):
        if required_role == "enterprise" and effective == "admin":
            flash("管理员无需访问企业业务模块，已为您跳转", "info")
            return redirect("/dashboard/stats")

    if _path_is_api_prefix(path):
        return jsonify({"error": "权限不足，禁止访问"}), 403

    abort(403)


def role_required(required_role: str):
    """
    要求已登录且 current_user 的 role 与 required_role 一致。
    越权时按 request.path 前缀返回 JSON 403、302 重定向或通用 403。
    required_role: 'admin' | 'enterprise'
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapped(*args, **kwargs):
            effective = user_effective_role(current_user)
            if effective != required_role:
                return _role_mismatch_response(required_role, effective)
            return view_func(*args, **kwargs)

        return wrapped

    return decorator

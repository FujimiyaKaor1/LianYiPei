"""
Internal Hermes API.

These endpoints are not user-session APIs. They are intended for the local
Hermes gateway/tool bridge and therefore use a dedicated Bearer token.
"""
from __future__ import annotations

import hmac
from functools import wraps

from flask import Blueprint, current_app, jsonify, request

from app.services.hermes_action_service import (
    HermesActionError,
    execute_action,
    get_alert,
    list_alerts,
    preview_action,
)

bp = Blueprint("hermes", __name__, url_prefix="/api/hermes")


def _json_error(error: str, message: str = "", status_code: int = 400):
    body = {"success": False, "error": error}
    if message:
        body["message"] = message
    return jsonify(body), status_code


def _remote_addr_allowed() -> bool:
    allowed = [
        x.strip()
        for x in str(current_app.config.get("HERMES_ALLOWED_REMOTE_ADDRS", "")).split(",")
        if x.strip()
    ]
    if not allowed:
        allowed = ["127.0.0.1", "::1", "localhost"]

    trust_proxy = bool(current_app.config.get("HERMES_TRUST_PROXY_HEADERS", False))
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",", 1)[0].strip()
    remote = forwarded if trust_proxy and forwarded else (request.remote_addr or "")
    return remote in allowed


def _require_hermes_token(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        expected = (current_app.config.get("HERMES_LIANYIPEI_TOKEN") or "").strip()
        if not expected:
            return _json_error("hermes_token_not_configured", status_code=503)
        if not _remote_addr_allowed():
            return _json_error("forbidden_remote_addr", status_code=403)

        auth = request.headers.get("Authorization", "")
        prefix = "Bearer "
        supplied = auth[len(prefix):].strip() if auth.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, expected):
            return _json_error("unauthorized", status_code=401)
        return fn(*args, **kwargs)

    return wrapper


@bp.get("/alerts")
@_require_hermes_token
def hermes_alerts():
    alerts = list_alerts(
        level=request.args.get("level") or None,
        status=request.args.get("status") or None,
        limit=request.args.get("limit", 20),
    )
    return jsonify({"success": True, "total": len(alerts), "alerts": alerts})


@bp.get("/alerts/<int:alert_id>")
@_require_hermes_token
def hermes_alert_detail(alert_id: int):
    alert = get_alert(alert_id)
    if not alert:
        return _json_error("alert_not_found", status_code=404)
    return jsonify({"success": True, "alert": alert})


@bp.post("/actions/preview")
@_require_hermes_token
def hermes_action_preview():
    data = request.get_json(silent=True) or {}
    try:
        result = preview_action(
            action=data.get("action", ""),
            alert_id=data.get("alert_id"),
            requested_by=data.get("requested_by", "hermes"),
            parameters=data.get("parameters") or {},
        )
        return jsonify(result)
    except HermesActionError as exc:
        return _json_error(exc.code, exc.message, exc.status_code)


@bp.post("/actions/execute")
@_require_hermes_token
def hermes_action_execute():
    data = request.get_json(silent=True) or {}
    try:
        result = execute_action(
            pending_action_id=data.get("pending_action_id", ""),
            confirmation=data.get("confirmation", ""),
        )
        return jsonify(result)
    except HermesActionError as exc:
        return _json_error(exc.code, exc.message, exc.status_code)

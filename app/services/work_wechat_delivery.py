"""Minimal, auditable Enterprise WeChat outbound adapter.

This adapter deliberately sends only text messages to an already-authorized
``wechat_work_userid``. It never discovers users, exposes corp secrets, or
falls back to an unverified contact. Transport state is returned to the RFQ
orchestrator, which persists it in the outbound audit record.
"""

from __future__ import annotations

from datetime import datetime, timedelta
import os
import re
import threading
from typing import Any

import requests
from flask import current_app


_TOKEN_LOCK = threading.Lock()
_TOKEN_CACHE: dict[str, Any] = {"token": "", "expires_at": datetime.min}
_TOKEN_URL = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
_SEND_URL = "https://qyapi.weixin.qq.com/cgi-bin/message/send"
_TOKEN_INVALID_CODES = {40014, 42001, 42007}
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_@.:-]{1,128}$")


def _setting(name: str) -> str:
    try:
        value = current_app.config.get(name)
    except RuntimeError:
        value = None
    return str(value or os.getenv(name) or "").strip()


def _timeout() -> float:
    try:
        return max(3.0, min(float(_setting("WORK_WECHAT_TIMEOUT_SECONDS") or 15), 60.0))
    except (TypeError, ValueError):
        return 15.0


def _credentials() -> tuple[str, str, str]:
    return (
        _setting("WORK_WECHAT_CORPID"),
        _setting("WORK_WECHAT_CORPSECRET"),
        _setting("WORK_WECHAT_AGENTID"),
    )


def _get_access_token(*, force_refresh: bool = False) -> tuple[str | None, str | None]:
    corpid, corpsecret, _agentid = _credentials()
    if not corpid or not corpsecret:
        return None, "work_wechat_not_configured"
    now = datetime.utcnow()
    with _TOKEN_LOCK:
        cached = str(_TOKEN_CACHE.get("token") or "")
        expires_at = _TOKEN_CACHE.get("expires_at")
        if not force_refresh and cached and isinstance(expires_at, datetime) and expires_at > now + timedelta(minutes=5):
            return cached, None
    try:
        response = requests.get(
            _TOKEN_URL,
            params={"corpid": corpid, "corpsecret": corpsecret},
            timeout=_timeout(),
        )
        payload = response.json()
    except (requests.RequestException, ValueError):
        return None, "work_wechat_token_unreachable"
    try:
        error_code = int(payload.get("errcode") or 0)
    except (TypeError, ValueError):
        error_code = -1
    token = str(payload.get("access_token") or "").strip()
    if error_code or not token:
        return None, f"work_wechat_token_error:{error_code or 'invalid_response'}"
    try:
        expires_in = max(300, int(payload.get("expires_in") or 7200))
    except (TypeError, ValueError):
        expires_in = 7200
    with _TOKEN_LOCK:
        _TOKEN_CACHE.update({"token": token, "expires_at": datetime.utcnow() + timedelta(seconds=expires_in)})
    return token, None


def send_text(*, user_id: str, title: str, content: str, url: str | None = None) -> dict[str, Any]:
    """Send an RFQ text message through Enterprise WeChat."""
    user_id = str(user_id or "").strip()
    if not _USER_ID_RE.fullmatch(user_id):
        return {"wechat_ok": False, "status": "failed", "reason": "invalid_work_wechat_userid"}
    _corpid, _corpsecret, agent_id = _credentials()
    if not agent_id:
        return {"wechat_ok": False, "status": "failed", "reason": "work_wechat_not_configured"}
    body = f"{str(title or '').strip()[:200]}\n{str(content or '').strip()[:1800]}"
    if url:
        body = f"{body}\n{str(url).strip()[:300]}"

    for attempt in range(2):
        token, token_error = _get_access_token(force_refresh=attempt == 1)
        if not token:
            return {"wechat_ok": False, "status": "failed", "reason": token_error or "work_wechat_token_error"}
        try:
            response = requests.post(
                _SEND_URL,
                params={"access_token": token},
                json={
                    "touser": user_id,
                    "msgtype": "text",
                    "agentid": int(agent_id),
                    "text": {"content": body},
                    "safe": 0,
                },
                timeout=_timeout(),
            )
            payload = response.json()
        except (requests.RequestException, ValueError):
            return {"wechat_ok": False, "status": "failed", "reason": "work_wechat_send_unreachable"}
        try:
            error_code = int(payload.get("errcode") or 0)
        except (TypeError, ValueError):
            error_code = -1
        if error_code in _TOKEN_INVALID_CODES and attempt == 0:
            continue
        if error_code:
            return {"wechat_ok": False, "status": "failed", "reason": f"work_wechat_send_error:{error_code}"}
        result = {"wechat_ok": True, "status": "sent", "provider": "work_wechat"}
        if payload.get("msgid") is not None:
            result["provider_message_id"] = str(payload["msgid"])[:240]
        return result
    return {"wechat_ok": False, "status": "failed", "reason": "work_wechat_token_error"}


def reset_token_cache() -> None:
    """Clear the process-local token cache for rotation/tests."""
    with _TOKEN_LOCK:
        _TOKEN_CACHE.update({"token": "", "expires_at": datetime.min})

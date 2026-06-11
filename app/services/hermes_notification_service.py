"""
Hermes alert notification bridge.

ChainYiPei keeps its existing WeChat/site-message path as the fallback. When a
local Hermes API server is configured, red alerts are handed to Hermes so it can
summarize the alert and deliver it through the user's Hermes Weixin channel.
"""
from __future__ import annotations

import logging
from typing import Iterable

import requests
from flask import current_app

from app.models import Alert
from app.services.hermes_action_service import alert_to_dict

logger = logging.getLogger(__name__)


def send_alert_to_hermes(alert: Alert, recipient_ids: Iterable[int]) -> dict:
    api_base_url = (current_app.config.get("HERMES_API_SERVER_URL") or "").strip().rstrip("/")
    api_key = (current_app.config.get("HERMES_API_SERVER_KEY") or "").strip()
    if not api_base_url or not api_key:
        return {"success": False, "message": "Hermes API server is not configured"}

    target = (current_app.config.get("HERMES_WEIXIN_TARGET") or "weixin").strip()
    chain_base_url = (current_app.config.get("HERMES_LIANYIPEI_BASE_URL") or "").strip().rstrip("/")
    payload = alert_to_dict(alert)
    alert_url = _absolute_alert_url(chain_base_url, alert.id)
    prompt = _build_hermes_prompt(payload, target, alert_url, list(recipient_ids))

    try:
        resp = requests.post(
            f"{api_base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "hermes-agent",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是链易配的预警助手。收到结构化预警后，先用中文压缩成适合微信阅读的"
                            "短摘要，再通过 send_message 工具发送到指定 Hermes 微信目标。不要修改链易配"
                            "业务数据；需要修改时只给出建议，等待用户确认。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "stream": False,
            },
            timeout=float(current_app.config.get("HERMES_API_TIMEOUT_SECONDS", 30)),
        )
        if resp.status_code >= 400:
            logger.warning(
                "[HermesBridge] Hermes API returned %s: %s",
                resp.status_code,
                resp.text[:500],
            )
            return {
                "success": False,
                "message": f"Hermes API returned {resp.status_code}",
            }
        return {"success": True, "message": "Hermes alert handoff accepted"}
    except Exception as exc:
        logger.warning("[HermesBridge] Hermes alert handoff failed: %s", exc)
        return {"success": False, "message": str(exc)}


def _absolute_alert_url(base_url: str, alert_id: int) -> str:
    path = f"/dashboard/alert-center?alert_id={alert_id}"
    return f"{base_url}{path}" if base_url else path


def _build_hermes_prompt(
    payload: dict,
    target: str,
    alert_url: str,
    recipient_ids: list[int],
) -> str:
    return (
        "请将下面链易配红色预警总结后发送到 Hermes 微信目标。\n"
        f"发送目标：{target}\n"
        f"链易配处置链接：{alert_url}\n"
        f"链易配接收人ID：{recipient_ids}\n\n"
        "微信摘要必须包含：\n"
        "1. 预警对象和等级\n"
        "2. 风险原因\n"
        "3. 影响范围\n"
        "4. 建议的第一步处置\n"
        "5. 可回复的操作提示：查看详情、总结重点、准备派发、准备关闭\n\n"
        f"结构化预警：{payload}"
    )

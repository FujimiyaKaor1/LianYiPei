#!/usr/bin/env python3
"""Exercise Chain XiaoYi through a real listening HTTP service.

This is intentionally smaller than ``chain_xiaoyi_demo.py``: the latter
verifies the complete callback/order workflow in-process, while this command
proves that a browser-facing server is using the configured model and can
create a session and process one buyer sentence.  It never accepts or prints
an API key; the key must already be injected into the server process.

Example::

    ./.venv/bin/python scripts/verify/live_chain_xiaoyi_smoke.py \
      --base-url http://127.0.0.1:5112
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit, urlunsplit

import requests


DEFAULT_BASE_URL = "http://127.0.0.1:5050"
DEMO_BUYER_NAME = "链易配演示·湾区采购中心"
DEMO_BUYER_PASSWORD = "DemoAgent2026!"
DEFAULT_PROMPT = "找广东能做精密连接器的工厂，采购100件，30天内交付"


def normalize_base_url(value: str) -> str:
    """Allow only an origin; never include credentials or query fragments."""
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url 必须是 http(s) 服务地址")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("base_url 不得包含凭据、查询参数或片段")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", "")).rstrip("/")


def _json(response: requests.Response) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"服务返回非 JSON（HTTP {response.status_code}）") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("服务返回格式不是 JSON 对象")
    return payload


def run_live_smoke(base_url: str, *, prompt: str = DEFAULT_PROMPT, timeout: float = 30.0) -> dict:
    """Run one authenticated buyer request and return a redacted summary."""
    origin = normalize_base_url(base_url)
    session = requests.Session()
    status_response = session.get(f"{origin}/api/chain-xiaoyi/model-status", timeout=timeout)
    status = _json(status_response)
    if status_response.status_code != 200 or status.get("active_provider") != "deepseek":
        raise RuntimeError("监听服务未启用 DeepSeek，已拒绝把规则模式当作真实模型结果")

    login_response = session.post(
        f"{origin}/auth/login",
        data={"name": DEMO_BUYER_NAME, "password": DEMO_BUYER_PASSWORD},
        headers={"X-Login-Modal": "1"},
        timeout=timeout,
    )
    if login_response.status_code != 200:
        raise RuntimeError(f"演示采购方登录失败（HTTP {login_response.status_code}）")

    created_response = session.post(
        f"{origin}/api/chain-xiaoyi/sessions",
        json={"surface": "enterprise"},
        timeout=timeout,
    )
    created = _json(created_response)
    session_payload = created.get("session")
    if created_response.status_code not in {200, 201} or not isinstance(session_payload, dict):
        raise RuntimeError("链小易会话创建失败")
    session_id = session_payload.get("id")

    message_response = session.post(
        f"{origin}/api/chain-xiaoyi/sessions/{int(session_id)}/messages",
        json={"content": str(prompt or DEFAULT_PROMPT)[:2000]},
        timeout=timeout,
    )
    message = _json(message_response)
    if message_response.status_code != 200 or message.get("success") is not True:
        raise RuntimeError("自然语言采购请求失败")
    model_status = message.get("model_status") if isinstance(message.get("model_status"), dict) else {}
    if model_status.get("active_provider") != "deepseek":
        raise RuntimeError("本轮请求未由 DeepSeek 执行")
    intent = message.get("intent") if isinstance(message.get("intent"), dict) else {}
    matches = message.get("match_result") if isinstance(message.get("match_result"), dict) else {}
    return {
        "success": True,
        "base_url": origin,
        "model_provider": model_status.get("active_provider"),
        "intent_provider": intent.get("confidence"),
        "product": intent.get("product"),
        "region": intent.get("region"),
        "candidate_count": int(matches.get("total") or 0),
        "task_status": (message.get("task") or {}).get("status"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="链小易真实 HTTP DeepSeek smoke")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = parser.parse_args()
    try:
        result = run_live_smoke(args.base_url, prompt=args.prompt)
    except Exception as exc:
        print(json.dumps({"success": False, "error": type(exc).__name__}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

import json
import os
import re

import requests
from flask import current_app


def extract_weights_from_nl(user_input: str) -> dict:
    url = "http://localhost:11434/api/generate"

    # 【优化】更聪明的兜底：如果 AI 挂了，我们手动取第一个词（通常是产品名）
    # 比如 "电机，离我近" -> 提取出 "电机"
    smart_fallback_word = re.split(r"[，, 。\s]", user_input or "")[0] if user_input else ""

    default_params = {
        "product": smart_fallback_word,
        "weights": {
            "distance": 0.2,
            "capacity": 0.2,
            "tech": 0.2,
            "history": 0.2,
            "product": 0.4,
        },
    }

    model = (
        (os.environ.get("OLLAMA_MODEL") or "").strip()
        or (os.environ.get("BIZMIND_OLLAMA_MODEL") or "").strip()
        or "bizmind"
    )
    payload = {
        "model": model,
        "prompt": f"你是一个参数提取器。只输出JSON。用户输入: '{user_input}'\nJSON:",
        "stream": False,
        "format": "json",
    }

    try:
        # 【关键改动】timeout 从 5 增加到 20
        response = requests.post(url, json=payload, timeout=20)
        if response.status_code == 200:
            content = response.json().get("response", "{}")
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                m = re.search(r"\{[\s\S]*\}", content or "")
                if not m:
                    return default_params
                try:
                    parsed = json.loads(m.group(0))
                except json.JSONDecodeError:
                    return default_params

            if not isinstance(parsed, dict):
                return default_params

            # 【再次加固】确保 product 不会是空字符串或整句话
            if not parsed.get("product"):
                parsed["product"] = smart_fallback_word
            else:
                p = parsed.get("product")
                parsed["product"] = p.strip() if isinstance(p, str) else str(p).strip()

            # 下游 match 需要 weights 五维；模型若未返回则补齐
            if "weights" not in parsed or not isinstance(parsed["weights"], dict):
                parsed["weights"] = dict(default_params["weights"])
            else:
                for key in default_params["weights"]:
                    if key not in parsed["weights"]:
                        parsed["weights"][key] = default_params["weights"][key]
                    else:
                        v = parsed["weights"][key]
                        try:
                            parsed["weights"][key] = float(v)
                        except (TypeError, ValueError):
                            parsed["weights"][key] = default_params["weights"][key]

            return parsed
        return default_params
    except Exception as e:
        try:
            current_app.logger.error(f"Ollama 意图解析异常: {e}")
        except RuntimeError:
            import logging

            logging.getLogger(__name__).error("Ollama 意图解析异常: %s", e)
        return default_params

"""
供应链匹配：自然语言 → LLM 提取产品名与维度权重，供 match_suppliers 使用。
对接项目内 Ollama（invoke_ollama），失败时可由路由层回退为整段文本作关键字。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.services.matcher import DEFAULT_WEIGHTS
from app.services.ollama_client import get_ollama_model_name, invoke_ollama

# 与用户约定一致的系统提示（仅输出 JSON）
MATCH_PARAM_SYSTEM_PROMPT = """你是一个专业的供应链匹配参数提取引擎。用户的输入可能包含产品名称和对供应商维度的偏好。
你的唯一任务是提取这些信息，并严格输出 JSON 格式：
{"product": "提取出的核心产品名称,如果没有则为空", "weights": {"distance": 0.2, "capacity": 0.2, "tech": 0.2, "history": 0.2, "product": 0.4}}

weights 中可出现的键名须与系统一致（按需填写，未提及的维度请省略，由系统与默认值合并后归一化）：
product（产品匹配）, distance（距离）, capacity（产能）, semantic（语义）, tech（技术/专利）, history（历史合作）, gnn（图相似）, credit（信用）, green（绿色低碳）。

规则：如果用户强调了距离近/本地/附近，调高 distance 权重（如0.8）；强调大厂/量大/产能，调高 capacity；强调技术/专利/研发，调高 tech；强调合作过/老客户，调高 history。未提及的保持默认值（合并时再归一化）。
绝不能输出 JSON 以外的任何废话！
"""

_WEIGHT_KEYS = frozenset(DEFAULT_WEIGHTS.keys())


def _extract_json(text_out: str) -> dict[str, Any] | None:
    """从模型输出中提取 JSON（支持 ```json 代码块与前后噪声）。"""
    if not text_out or not text_out.strip():
        return None
    text_out = text_out.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text_out, flags=re.IGNORECASE)
    if m:
        text_out = m.group(1).strip()
    m2 = re.search(r"\{[\s\S]*\}", text_out)
    if m2:
        text_out = m2.group(0).strip()
    try:
        obj = json.loads(text_out)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def merge_llm_weights(llm_weights: Any) -> dict[str, float]:
    """
    以 DEFAULT_WEIGHTS 为基底，用 LLM 给出的部分键覆盖，再整体归一化（与 match_suppliers 行为一致）。
    """
    out: dict[str, float] = {k: float(v) for k, v in DEFAULT_WEIGHTS.items()}
    if not isinstance(llm_weights, dict):
        return out
    for k, v in llm_weights.items():
        if k not in _WEIGHT_KEYS:
            continue
        try:
            fv = float(v)
            if fv >= 0:
                out[k] = fv
        except (TypeError, ValueError):
            continue
    total = sum(out.values())
    if total <= 0:
        return {k: float(v) for k, v in DEFAULT_WEIGHTS.items()}
    return {k: out[k] / total for k in out}


def extract_match_params_from_nl(user_text: str) -> dict[str, Any]:
    """
    调用大模型解析自然语言，返回结构化结果。

    Returns:
        {
            "product": str,
            "weights": dict[str, float],
            "raw_llm": str | None,
            "llm_error": str | None,
        }
    """
    text = (user_text or "").strip()
    empty = {
        "product": "",
        "weights": {k: float(v) for k, v in DEFAULT_WEIGHTS.items()},
        "raw_llm": None,
        "llm_error": None,
    }
    if not text:
        return {**empty, "llm_error": "empty_input"}

    try:
        raw = invoke_ollama(MATCH_PARAM_SYSTEM_PROMPT, text)
    except Exception as e:
        return {
            "product": "",
            "weights": {k: float(v) for k, v in DEFAULT_WEIGHTS.items()},
            "raw_llm": None,
            "llm_error": f"llm_invoke_failed: {e}（请确认 Ollama 已启动并已 ollama pull {get_ollama_model_name()}）",
        }

    parsed = _extract_json(raw)
    if not parsed:
        return {
            "product": "",
            "weights": {k: float(v) for k, v in DEFAULT_WEIGHTS.items()},
            "raw_llm": raw,
            "llm_error": "json_parse_failed",
        }

    product = parsed.get("product")
    if product is None:
        product = ""
    else:
        product = str(product).strip()

    w = merge_llm_weights(parsed.get("weights"))

    return {
        "product": product,
        "weights": w,
        "raw_llm": raw,
        "llm_error": None,
    }

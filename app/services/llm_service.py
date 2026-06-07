"""BizMind /api/chat：直连本机 Ollama（SSE 流式），与 AnythingLLM 解耦。"""
from __future__ import annotations

import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
DEFAULT_BIZMIND_MODEL = "bizmind"

BIZMIND_SYSTEM_PROMPT = (
    "你是「链小易 BizMind」智能助手，专注供应链协作、产业配套与企业服务。"
    "回答简洁、专业，使用中文。"
)


def _ollama_base_url() -> str:
    return (os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")


def _bizmind_ollama_model() -> str:
    return (
        (os.environ.get("BIZMIND_OLLAMA_MODEL") or "").strip()
        or (os.environ.get("OLLAMA_MODEL") or "").strip()
        or DEFAULT_BIZMIND_MODEL
    )


def _bizmind_chat_ollama() -> ChatOllama:
    return ChatOllama(
        model=_bizmind_ollama_model(),
        base_url=_ollama_base_url(),
        temperature=float(os.environ.get("LLM_TEMPERATURE", "0.3")),
        num_predict=int(os.environ.get("LLM_MAX_TOKENS", "2048")),
        timeout=int(float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))),
    )


class BizMindOllamaStreamChain:
    """与路由兼容：提供 stream({"input": str})，逐块 yield 文本增量。"""

    def stream(self, input_config: dict):
        user_input = (input_config.get("input") or "").strip()
        if not user_input:
            yield "你想问我关于供应链的什么问题？"
            return

        llm = _bizmind_chat_ollama()
        messages = [
            SystemMessage(content=BIZMIND_SYSTEM_PROMPT),
            HumanMessage(content=user_input),
        ]
        for chunk in llm.stream(messages):
            delta = plain_text_delta_from_stream_chunk(chunk)
            if delta:
                yield delta


def get_bizmind_chain():
    return BizMindOllamaStreamChain()


def plain_text_delta_from_stream_chunk(chunk) -> str:
    if chunk is None:
        return ""
    if isinstance(chunk, str):
        return chunk
    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return str(content or "")


def sse_event_from_plain_text(text: str) -> str:
    if text == "[DONE]":
        return "data: [DONE]\n\n"
    # JSON 编码避免换行或引号破坏 SSE 行
    return f"data: {json.dumps(text, ensure_ascii=False)}\n\n"


def sse_event_from_error(exc: BaseException) -> str:
    return f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

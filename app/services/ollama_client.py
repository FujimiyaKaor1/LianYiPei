"""本地 Ollama 调用（LangChain），供匹配、Text2SQL 等非 BizMind 流程使用。"""
from __future__ import annotations

import os

from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"
_llm: ChatOllama | None = None
_cached_model: str | None = None


def _ollama_base_url() -> str:
    return (os.environ.get("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL).strip().rstrip("/")


def get_ollama_model_name() -> str:
    """匹配、Text2SQL 等共用：优先 OLLAMA_MODEL，其次 BIZMIND_OLLAMA_MODEL，默认 bizmind（与 `ollama run bizmind` 名称一致）。"""
    name = (os.environ.get("OLLAMA_MODEL") or "").strip()
    if name:
        return name
    name = (os.environ.get("BIZMIND_OLLAMA_MODEL") or "").strip()
    if name:
        return name
    return "bizmind"


def get_chat_ollama() -> ChatOllama:
    global _llm, _cached_model
    model = get_ollama_model_name()
    if _llm is None or _cached_model != model:
        _cached_model = model
        _llm = ChatOllama(
            model=model,
            base_url=_ollama_base_url(),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
            num_predict=int(os.environ.get("LLM_MAX_TOKENS", "512")),
            timeout=int(float(os.environ.get("LLM_TIMEOUT_SECONDS", "120"))),
        )
    return _llm


def message_content(resp: BaseMessage | object) -> str:
    content = getattr(resp, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts).strip()
    return str(content or resp)


def invoke_ollama(system_prompt: str, user_text: str) -> str:
    llm = get_chat_ollama()
    messages: list[SystemMessage | HumanMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_text),
    ]
    resp = llm.invoke(messages)
    return message_content(resp).strip()

"""LangChain-compatible client for DeepSeek's OpenAI-compatible API."""
from __future__ import annotations

import json
import os
from typing import Any, Iterator

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"


def _role(message: BaseMessage) -> str:
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    value = getattr(message, "role", None) or getattr(message, "type", "user")
    return "assistant" if value == "ai" else str(value)


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(str(item.get("text", "")) if isinstance(item, dict) and item.get("type") == "text" else str(item) if isinstance(item, str) else "" for item in value)
    return str(value or "")


def _choice_content(data: dict[str, Any], streaming: bool = False) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return ""
    choice = choices[0]
    payload = choice.get("delta") if streaming else choice.get("message")
    if not isinstance(payload, dict):
        payload = choice.get("message")
    return _text(payload.get("content")) if isinstance(payload, dict) else ""


class DeepSeekChatModel(BaseChatModel):
    api_key: str
    model: str = DEFAULT_DEEPSEEK_MODEL
    base_url: str = DEFAULT_DEEPSEEK_BASE_URL
    temperature: float = 0.3
    timeout: float = 120.0
    max_completion_tokens: int = 2048
    top_p: float | None = None

    @property
    def _llm_type(self) -> str:
        return "deepseek"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, messages: list[BaseMessage], stop: list[str] | None, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": _role(message), "content": _text(message.content)} for message in messages],
            "temperature": self.temperature,
            "stream": stream,
        }
        if self.max_completion_tokens > 0:
            payload["max_tokens"] = self.max_completion_tokens
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if stop is not None:
            payload["stop"] = stop
        return payload

    def _url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager=None, **kwargs: Any) -> ChatResult:
        response = requests.post(self._url(), headers=self._headers(), json=self._payload(messages, stop, False), timeout=self.timeout)
        response.raise_for_status()
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=_choice_content(response.json())))], llm_output={"model": self.model})

    def _stream(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager=None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        response = requests.post(self._url(), headers=self._headers(), json=self._payload(messages, stop, True), timeout=self.timeout, stream=True)
        response.raise_for_status()
        response.encoding = "utf-8"
        try:
            for raw in response.iter_lines(decode_unicode=True):
                line = (raw or "").strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    if line == "[DONE]":
                        break
                    continue
                try:
                    delta = _choice_content(json.loads(line), True)
                except (json.JSONDecodeError, TypeError):
                    continue
                if delta:
                    if run_manager:
                        run_manager.on_llm_new_token(delta)
                    yield ChatGenerationChunk(message=AIMessageChunk(content=delta))
        finally:
            response.close()


def create_deepseek_chat_model_from_env() -> DeepSeekChatModel:
    api_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("缺少 DEEPSEEK_API_KEY 环境变量")
    return DeepSeekChatModel(
        api_key=api_key,
        model=(os.getenv("DEEPSEEK_MODEL") or DEFAULT_DEEPSEEK_MODEL).strip(),
        base_url=(os.getenv("DEEPSEEK_BASE_URL") or DEFAULT_DEEPSEEK_BASE_URL).strip().rstrip("/"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        max_completion_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
    )

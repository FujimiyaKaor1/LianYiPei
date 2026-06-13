"""Xiaomi MiMo chat client for the OpenAI-compatible API."""
from __future__ import annotations

import json
import os
from typing import Any, Iterator

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

DEFAULT_MIMO_BASE_URL = "https://token-plan-cn.xiaomimimo.com/v1"
DEFAULT_MIMO_MODEL = "mimo-v2.5-pro"


def _message_role(message: BaseMessage) -> str:
    if isinstance(message, SystemMessage):
        return "system"
    if isinstance(message, HumanMessage):
        return "user"
    if isinstance(message, AIMessage):
        return "assistant"
    role = getattr(message, "role", None) or getattr(message, "type", "")
    return "assistant" if role == "ai" else str(role or "user")


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content or "")


def _extract_message_content(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    message = choice.get("message") if isinstance(choice, dict) else {}
    if isinstance(message, dict):
        return _content_to_text(message.get("content"))
    return ""


def _extract_stream_delta(data: dict[str, Any]) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    choice = choices[0] if isinstance(choices[0], dict) else {}
    delta = choice.get("delta") if isinstance(choice, dict) else {}
    if isinstance(delta, dict) and delta.get("content") is not None:
        return _content_to_text(delta.get("content"))
    message = choice.get("message") if isinstance(choice, dict) else {}
    if isinstance(message, dict) and message.get("content") is not None:
        return _content_to_text(message.get("content"))
    return ""


class MiMoChatModel(BaseChatModel):
    """LangChain-compatible wrapper around Xiaomi MiMo's documented API."""

    api_key: str
    model: str = DEFAULT_MIMO_MODEL
    base_url: str = DEFAULT_MIMO_BASE_URL
    temperature: float = 0.3
    timeout: float = 120.0
    max_completion_tokens: int = 2048
    top_p: float | None = None

    @property
    def _llm_type(self) -> str:
        return "xiaomi-mimo"

    def _headers(self) -> dict[str, str]:
        return {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _messages_payload(self, messages: list[BaseMessage]) -> list[dict[str, str]]:
        return [
            {
                "role": _message_role(message),
                "content": _content_to_text(message.content),
            }
            for message in messages
        ]

    def _payload(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None,
        stream: bool,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": self._messages_payload(messages),
            "temperature": self.temperature,
            "stream": stream,
        }
        if self.max_completion_tokens > 0:
            payload["max_completion_tokens"] = self.max_completion_tokens
        if self.top_p is not None:
            payload["top_p"] = self.top_p
        if stop is not None:
            payload["stop"] = stop
        return payload

    def _chat_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs: Any,
    ) -> ChatResult:
        response = requests.post(
            self._chat_url(),
            headers=self._headers(),
            json=self._payload(messages, stop, stream=False),
            timeout=self.timeout,
        )
        response.raise_for_status()
        content = _extract_message_content(response.json())
        return ChatResult(
            generations=[
                ChatGeneration(message=AIMessage(content=content)),
            ],
            llm_output={"model": self.model},
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        response = requests.post(
            self._chat_url(),
            headers=self._headers(),
            json=self._payload(messages, stop, stream=True),
            timeout=self.timeout,
            stream=True,
        )
        response.raise_for_status()
        response.encoding = "utf-8"
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if line.startswith("data:"):
                    line = line.removeprefix("data:").strip()
                if line == "[DONE]":
                    break
                try:
                    delta = _extract_stream_delta(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if not delta:
                    continue
                if run_manager:
                    run_manager.on_llm_new_token(delta)
                yield ChatGenerationChunk(message=AIMessageChunk(content=delta))
        finally:
            response.close()


def create_mimo_chat_model_from_env() -> MiMoChatModel:
    api_key = (os.getenv("MIMO_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("缺少 MIMO_API_KEY 环境变量")

    return MiMoChatModel(
        api_key=api_key,
        model=(os.getenv("MIMO_MODEL") or DEFAULT_MIMO_MODEL).strip(),
        base_url=(os.getenv("MIMO_BASE_URL") or DEFAULT_MIMO_BASE_URL).strip().rstrip("/"),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.3")),
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
        max_completion_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
    )

"""LangChain-compatible client for DeepSeek's OpenAI-compatible API."""
from __future__ import annotations

import json
import os
import time
from typing import Any, Iterator

import requests
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

DEFAULT_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
# The Chain XiaoYi default is the vision-capable experimental model.  Keep the
# environment override below for deployments that have an approved fallback,
# but make the vision model the honest out-of-box behavior.
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash-vision-exp"
MAX_INLINE_IMAGE_BYTES = 10 * 1024 * 1024
_RETRYABLE_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504})


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


def _message_content(value: Any) -> str | list[dict[str, Any]]:
    """Prepare LangChain content without dropping vision blocks.

    DeepSeek's OpenAI-compatible endpoint accepts plain strings as well as a
    list of ``text``/``image_url`` blocks.  Older code flattened every list to
    text, which made a vision model receive no image at all.  Validate the
    small supported block vocabulary here so malformed user-controlled
    content fails before a network request and inline data URLs cannot create
    unbounded request bodies.
    """
    if isinstance(value, str):
        return value
    if not isinstance(value, list):
        return str(value or "")

    blocks: list[dict[str, Any]] = []
    for block in value:
        if not isinstance(block, dict):
            raise ValueError("DeepSeek 多模态消息块格式无效")
        block_type = block.get("type")
        if block_type == "text":
            text = block.get("text")
            if not isinstance(text, str):
                raise ValueError("DeepSeek 文本消息块格式无效")
            blocks.append({"type": "text", "text": text})
            continue
        if block_type == "image_url":
            image_url = block.get("image_url")
            if not isinstance(image_url, dict) or not isinstance(image_url.get("url"), str):
                raise ValueError("DeepSeek 图片消息块格式无效")
            url = image_url["url"]
            if url.startswith("data:") and len(url.encode("utf-8")) > MAX_INLINE_IMAGE_BYTES:
                raise ValueError("DeepSeek 图片内容过大")
            normalized_image_url: dict[str, Any] = {"url": url}
            if image_url.get("detail") is not None:
                normalized_image_url["detail"] = image_url["detail"]
            blocks.append({"type": "image_url", "image_url": normalized_image_url})
            continue
        raise ValueError(f"DeepSeek 不支持的消息块类型: {block_type or 'unknown'}")
    return blocks


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
    # Chat completions are safe to retry because the request has no external
    # side effect.  Keep this bounded so a provider outage fails closed in a
    # predictable amount of time instead of multiplying API latency/cost.
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5

    @property
    def _llm_type(self) -> str:
        return "deepseek"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def _payload(self, messages: list[BaseMessage], stop: list[str] | None, stream: bool) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": _role(message), "content": _message_content(message.content)} for message in messages],
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

    def _post_with_retry(self, messages: list[BaseMessage], stop: list[str] | None, stream: bool):
        """POST with bounded retries for transient transport/provider errors."""
        attempts = max(0, min(int(self.max_retries), 5)) + 1
        backoff = max(0.0, min(float(self.retry_backoff_seconds), 10.0))
        payload = self._payload(messages, stop, stream)
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = requests.post(
                    self._url(),
                    headers=self._headers(),
                    json=payload,
                    timeout=self.timeout,
                    **({"stream": True} if stream else {}),
                )
                status_code = getattr(response, "status_code", None)
                if status_code in _RETRYABLE_STATUS_CODES and attempt < attempts - 1:
                    try:
                        response.close()
                    except Exception:
                        pass
                    time.sleep(backoff * (2 ** attempt))
                    continue
                response.raise_for_status()
                return response
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if attempt >= attempts - 1:
                    raise
                time.sleep(backoff * (2 ** attempt))
            except requests.HTTPError as exc:
                last_error = exc
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code not in _RETRYABLE_STATUS_CODES or attempt >= attempts - 1:
                    raise
                time.sleep(backoff * (2 ** attempt))
        if last_error is not None:  # defensive; loop either returns or raises
            raise last_error
        raise RuntimeError("DeepSeek request failed without a response")

    def _generate(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager=None, **kwargs: Any) -> ChatResult:
        response = self._post_with_retry(messages, stop, False)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=_choice_content(response.json())))], llm_output={"model": self.model})

    def _stream(self, messages: list[BaseMessage], stop: list[str] | None = None, run_manager=None, **kwargs: Any) -> Iterator[ChatGenerationChunk]:
        response = self._post_with_retry(messages, stop, True)
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
        max_retries=int(os.getenv("DEEPSEEK_MAX_RETRIES", "2")),
        retry_backoff_seconds=float(os.getenv("DEEPSEEK_RETRY_BACKOFF_SECONDS", "0.5")),
    )

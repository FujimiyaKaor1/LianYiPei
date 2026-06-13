import pytest
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.routes.api import get_llm_instance
from app.services.mimo_client import DEFAULT_MIMO_BASE_URL, DEFAULT_MIMO_MODEL, MiMoChatModel


def test_get_llm_instance_uses_mimo_config(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-test-key")
    monkeypatch.setenv("MIMO_MODEL", "mimo-custom")
    monkeypatch.setenv("MIMO_BASE_URL", "https://example.test/v1/")

    llm = get_llm_instance("mimo")

    assert isinstance(llm, MiMoChatModel)
    assert llm.api_key == "mimo-test-key"
    assert llm.model == "mimo-custom"
    assert llm.base_url == "https://example.test/v1"


def test_get_llm_instance_routes_legacy_deepseek_choice_to_mimo(monkeypatch):
    monkeypatch.setenv("MIMO_API_KEY", "mimo-test-key")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    llm = get_llm_instance("deepseek")

    assert isinstance(llm, MiMoChatModel)
    assert llm.model == DEFAULT_MIMO_MODEL


def test_get_llm_instance_requires_mimo_api_key(monkeypatch):
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="MIMO_API_KEY"):
        get_llm_instance("mimo")


def test_mimo_chat_model_posts_official_api_key_header(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {"message": {"content": "收到，已切换 MiMo。"}},
                ],
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.mimo_client.requests.post", fake_post)
    llm = MiMoChatModel(api_key="mimo-test-key")

    response = llm.invoke(
        [
            SystemMessage(content="你是链易配助手"),
            HumanMessage(content="生成供应商推荐理由"),
        ]
    )

    assert response.content == "收到，已切换 MiMo。"
    assert captured["url"] == f"{DEFAULT_MIMO_BASE_URL}/chat/completions"
    assert captured["headers"]["api-key"] == "mimo-test-key"
    assert captured["json"]["model"] == DEFAULT_MIMO_MODEL
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "你是链易配助手"},
        {"role": "user", "content": "生成供应商推荐理由"},
    ]


def test_mimo_stream_decodes_utf8_sse_bytes_without_charset(monkeypatch):
    expected = "您好，链小易。"
    payload = {
        "choices": [
            {"delta": {"content": expected}},
        ],
    }
    sse_lines = [
        f"data: {json.dumps(payload, ensure_ascii=False)}".encode("utf-8"),
        b"data: [DONE]",
    ]

    class FakeResponse:
        encoding = "ISO-8859-1"

        def raise_for_status(self):
            return None

        def iter_lines(self, decode_unicode=False):
            for line in sse_lines:
                if decode_unicode:
                    yield line.decode(self.encoding)
                else:
                    yield line

        def close(self):
            return None

    monkeypatch.setattr(
        "app.services.mimo_client.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    llm = MiMoChatModel(api_key="mimo-test-key")

    chunks = list(
        llm.stream(
            [
                SystemMessage(content="你是链易配助手"),
                HumanMessage(content="你是什么模型"),
            ],
        ),
    )

    assert "".join(chunk.content for chunk in chunks) == expected

import pytest
import json

from langchain_core.messages import HumanMessage, SystemMessage

from app.routes.api import _build_deepseek_match_reasons, get_llm_instance
from app.services.deepseek_client import DEFAULT_DEEPSEEK_BASE_URL, DEFAULT_DEEPSEEK_MODEL, DeepSeekChatModel


def test_get_llm_instance_uses_deepseek_config(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-custom")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/v1/")

    llm = get_llm_instance("deepseek")

    assert isinstance(llm, DeepSeekChatModel)
    assert llm.api_key == "deepseek-test-key"
    assert llm.model == "deepseek-custom"
    assert llm.base_url == "https://example.test/v1"


def test_get_llm_instance_routes_legacy_mimo_choice_to_deepseek(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "deepseek-test-key")

    llm = get_llm_instance("mimo")

    assert isinstance(llm, DeepSeekChatModel)
    assert llm.model == DEFAULT_DEEPSEEK_MODEL


def test_get_llm_instance_requires_deepseek_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        get_llm_instance("deepseek")


def test_deepseek_chat_model_posts_bearer_authorization(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [
                    {"message": {"content": "收到，已切换 DeepSeek。"}},
                ],
            }

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    monkeypatch.setattr("app.services.deepseek_client.requests.post", fake_post)
    llm = DeepSeekChatModel(api_key="deepseek-test-key")

    response = llm.invoke(
        [
            SystemMessage(content="你是链易配助手"),
            HumanMessage(content="生成供应商推荐理由"),
        ]
    )

    assert response.content == "收到，已切换 DeepSeek。"
    assert captured["url"] == f"{DEFAULT_DEEPSEEK_BASE_URL}/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer deepseek-test-key"
    assert "api-key" not in captured["headers"]
    assert captured["json"]["model"] == DEFAULT_DEEPSEEK_MODEL
    assert captured["json"]["stream"] is False
    assert captured["json"]["messages"] == [
        {"role": "system", "content": "你是链易配助手"},
        {"role": "user", "content": "生成供应商推荐理由"},
    ]


def test_deepseek_stream_decodes_utf8_sse_bytes_without_charset(monkeypatch):
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
        "app.services.deepseek_client.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    llm = DeepSeekChatModel(api_key="deepseek-test-key")

    chunks = list(
        llm.stream(
            [
                SystemMessage(content="你是链易配助手"),
                HumanMessage(content="你是什么模型"),
            ],
        ),
    )

    assert "".join(chunk.content for chunk in chunks) == expected


def test_deepseek_match_explanation_cannot_inject_ids_or_scores(monkeypatch):
    class FakeLlm:
        def invoke(self, _messages):
            return type("Response", (), {"content": json.dumps([
                {"id": 7, "reason": "基于输入事实", "ai_score": 99},
                {"id": 999, "reason": "伪造企业", "ai_score": 100},
            ], ensure_ascii=False)})()

    monkeypatch.setattr("app.routes.api.get_llm_instance", lambda _choice: FakeLlm())
    reasons, scores, degraded, fallback = _build_deepseek_match_reasons(
        "电机", [{"id": 7, "name": "数据库企业", "score": 61, "dimensions": {}, "reasons": []}]
    )

    assert reasons == {7: "基于输入事实"}
    assert scores == {}
    assert degraded is False
    assert fallback is None

import json

from app.services.llm_service import sse_event_from_error


def _event_payload(event: str):
    prefix = "data: "
    assert event.startswith(prefix)
    return json.loads(event.removeprefix(prefix).strip())


def test_sse_error_explains_local_ollama_connection_failure():
    event = sse_event_from_error(
        ConnectionError("HTTPConnectionPool(host='localhost', port=11434): Connection refused"),
    )

    payload = _event_payload(event)

    assert "本地 Ollama 未启动" in payload["error"]
    assert "切换 MiMo 云端模型" in payload["error"]


def test_sse_error_explains_cloud_auth_failure():
    event = sse_event_from_error(RuntimeError("401 Unauthorized"))

    payload = _event_payload(event)

    assert "云端 MiMo 鉴权失败" in payload["error"]

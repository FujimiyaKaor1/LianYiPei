"""Enterprise WeChat outbound adapter and RFQ channel authorization tests."""

from __future__ import annotations

from app.services.rfq_delivery import deliver_rfq, normalize_channels
from app.services.work_wechat_delivery import reset_token_cache, send_text


class _Response:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_work_wechat_adapter_gets_token_and_sends_text(app, monkeypatch):
    calls = {"get": [], "post": []}
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", "corp-demo")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPSECRET", "secret-demo")
    monkeypatch.setitem(app.config, "WORK_WECHAT_AGENTID", "100001")
    reset_token_cache()

    monkeypatch.setattr(
        "app.services.work_wechat_delivery.requests.get",
        lambda *args, **kwargs: (calls["get"].append((args, kwargs)) or _Response({"errcode": 0, "access_token": "token-demo", "expires_in": 7200})),
    )
    monkeypatch.setattr(
        "app.services.work_wechat_delivery.requests.post",
        lambda *args, **kwargs: (calls["post"].append((args, kwargs)) or _Response({"errcode": 0, "msgid": 12345})),
    )

    with app.app_context():
        result = send_text(user_id="supplier-001", title="询价", content="请报价")

    assert result == {"wechat_ok": True, "status": "sent", "provider": "work_wechat", "provider_message_id": "12345"}
    assert len(calls["get"]) == 1
    assert len(calls["post"]) == 1
    assert calls["post"][0][1]["json"]["touser"] == "supplier-001"
    assert calls["post"][0][1]["json"]["agentid"] == 100001
    assert "corp-demo" not in repr(result)


def test_work_wechat_adapter_refreshes_expired_token_once(app, monkeypatch):
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPID", "corp-demo")
    monkeypatch.setitem(app.config, "WORK_WECHAT_CORPSECRET", "secret-demo")
    monkeypatch.setitem(app.config, "WORK_WECHAT_AGENTID", "100001")
    reset_token_cache()
    tokens = iter(["token-old", "token-new"])
    get_calls = []

    def fake_get(*_args, **_kwargs):
        get_calls.append(True)
        return _Response({"errcode": 0, "access_token": next(tokens), "expires_in": 7200})

    post_calls = []

    def fake_post(_url, *, params, **_kwargs):
        post_calls.append(params["access_token"])
        return _Response({"errcode": 42001} if len(post_calls) == 1 else {"errcode": 0})

    monkeypatch.setattr("app.services.work_wechat_delivery.requests.get", fake_get)
    monkeypatch.setattr("app.services.work_wechat_delivery.requests.post", fake_post)
    with app.app_context():
        result = send_text(user_id="supplier-001", title="询价", content="请报价")
    assert result["wechat_ok"] is True
    assert get_calls == [True, True]
    assert post_calls == ["token-old", "token-new"]


def test_rfq_work_wechat_requires_explicit_supplier_authorization(_db, test_supplier, monkeypatch):
    test_supplier.wechat_work_userid = "supplier-001"
    test_supplier.extras = {
        "trust_profile": {"claim_status": "claimed", "contact_authorized": True},
        "communication_authorizations": {"work_wechat": True},
    }
    _db.session.commit()
    monkeypatch.setattr(
        "app.services.rfq_delivery.send_work_wechat_text",
        lambda **_kwargs: {"wechat_ok": True, "status": "sent", "provider_message_id": "m-1"},
    )

    assert "work_wechat" in normalize_channels(["work_wechat"], include_site=False)
    with _db.session.no_autoflush:
        result = deliver_rfq(test_supplier, "询价", "请报价", ["work_wechat"], include_site=False)
    assert result["channels"]["work_wechat"]["status"] == "sent"
    assert result["channels"]["work_wechat"]["provider_message_id"] == "m-1"


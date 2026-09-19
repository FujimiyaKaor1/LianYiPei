"""IMAP inbound quote worker tests (all network clients are injected)."""

from __future__ import annotations

from email.message import EmailMessage
import hashlib
import hmac
import json

from app.services.email_quote_poller import (
    EmailPollConfig,
    build_callback_request,
    parse_inbound_email,
    poll_once,
)


def _raw_email(*, message_id="<mail-1@example.com>", body="报价 #12 单价12元"):
    message = EmailMessage()
    message["Message-ID"] = message_id
    message["From"] = "Sales <sales@supplier.example>"
    message["Subject"] = "Re: 询价 #12"
    message.set_content(body)
    return message.as_bytes()


def test_parse_inbound_email_extracts_safe_plain_text_payload():
    payload = parse_inbound_email(_raw_email())
    assert payload["event_id"] == "<mail-1@example.com>"
    assert payload["from_email"] == "Sales <sales@supplier.example>"
    assert payload["subject"] == "Re: 询价 #12"
    assert payload["text"].startswith("报价 #12")
    assert len(payload) == 4


def test_build_callback_request_signs_raw_json_without_exposing_secret():
    raw, headers = build_callback_request(
        {"event_id": "mail-1", "from_email": "sales@example.com", "text": "报价 #1 单价2元"},
        "worker-secret",
    )
    assert json.loads(raw)["event_id"] == "mail-1"
    assert headers["X-Lianyipei-Signature"].startswith("sha256=")
    assert len(headers["X-Lianyipei-Signature"]) == 71
    assert headers["X-Lianyipei-Signature"] == "sha256=" + hmac.new(
        b"worker-secret", raw, hashlib.sha256
    ).hexdigest()


def test_poll_once_marks_only_successfully_forwarded_messages_seen():
    class FakeIMAP:
        instances = []

        def __init__(self, host, port, timeout):
            self.host, self.port, self.timeout = host, port, timeout
            self.seen = []
            self.logged_out = False
            FakeIMAP.instances.append(self)

        def login(self, username, password):
            assert username == "worker@example.com"
            assert password == "password"
            return "OK", []

        def select(self, folder, readonly=False):
            assert folder == "INBOX"
            assert readonly is False
            return "OK", [b"2"]

        def search(self, charset, query):
            assert query == "UNSEEN"
            return "OK", [b"1 2"]

        def fetch(self, message_id, query):
            return "OK", [(b"meta", _raw_email(message_id=f"<mail-{message_id.decode()}@example.com>"))]

        def store(self, message_id, action, flags):
            self.seen.append((message_id, action, flags))
            return "OK", []

        def close(self):
            return "OK", []

        def logout(self):
            self.logged_out = True
            return "BYE", []

    posted = []

    def post(url, data, headers, timeout):
        posted.append((url, json.loads(data), headers, timeout))
        return type("Response", (), {"status_code": 200, "text": "ok"})()

    result = poll_once(
        EmailPollConfig(
            enabled=True,
            host="imap.example.com",
            port=993,
            username="worker@example.com",
            password="password",
            folder="INBOX",
            callback_url="http://127.0.0.1:5051/api/chain-xiaoyi/email-quote-inbound",
            callback_secret="worker-secret",
            batch_size=10,
            timeout=4,
        ),
        imap_factory=FakeIMAP,
        post=post,
    )
    assert result == {"status": "ok", "found": 2, "processed": 2, "failed": 0}
    assert len(posted) == 2
    assert len(FakeIMAP.instances[0].seen) == 2
    assert FakeIMAP.instances[0].logged_out is True


def test_poll_once_is_fail_closed_when_configuration_is_incomplete():
    result = poll_once(EmailPollConfig(enabled=True, host="", username="", password=""))
    assert result["status"] == "disabled"
    assert result["processed"] == 0
    assert result["reason"] == "imap_configuration_missing"

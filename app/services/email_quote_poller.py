"""IMAP/SSL worker that feeds real supplier mail into Chain XiaoYi.

The worker is deliberately transport-only: it does not persist commercial
data. It signs a normalized envelope for ``email-quote-inbound`` and marks a
message seen only after the application returns a 2xx response, so temporary
outages are recoverable without inventing or dropping quotes.
"""
from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.header import decode_header, make_header
from email.message import Message
from email.parser import BytesParser
import hashlib
import hmac
import imaplib
import json
import os
import re
from typing import Any, Callable

import requests


@dataclass(frozen=True)
class EmailPollConfig:
    enabled: bool = False
    host: str = ""
    port: int = 993
    username: str = ""
    password: str = ""
    folder: str = "INBOX"
    callback_url: str = ""
    callback_secret: str = ""
    batch_size: int = 20
    timeout: int = 20


def _flag(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def email_poll_config(source: Any = None) -> EmailPollConfig:
    """Read worker settings from Flask config when available, then env."""
    cfg = source if source is not None else {}
    def value(name: str, default: str = "") -> str:
        configured = cfg.get(name) if hasattr(cfg, "get") else None
        return str(configured if configured not in (None, "") else os.getenv(name, default) or default).strip()

    try:
        port = int(value("INBOUND_IMAP_PORT", "993"))
        batch_size = max(1, min(int(value("INBOUND_EMAIL_BATCH_SIZE", "20")), 100))
        timeout = max(5, min(int(value("INBOUND_EMAIL_TIMEOUT_SECONDS", "20")), 120))
    except ValueError:
        port, batch_size, timeout = 993, 20, 20
    callback_url = value(
        "INBOUND_EMAIL_CALLBACK_URL",
        "http://127.0.0.1:5050/api/chain-xiaoyi/email-quote-inbound",
    )
    return EmailPollConfig(
        enabled=_flag(value("INBOUND_EMAIL_ENABLED", "false")),
        host=value("INBOUND_IMAP_HOST"),
        port=port,
        username=value("INBOUND_IMAP_USERNAME"),
        password=value("INBOUND_IMAP_PASSWORD"),
        folder=value("INBOUND_IMAP_FOLDER", "INBOX") or "INBOX",
        callback_url=callback_url,
        callback_secret=value("RFQ_EMAIL_INBOUND_SECRET"),
        batch_size=batch_size,
        timeout=timeout,
    )


def _decode_header(value: str | None) -> str:
    try:
        return str(make_header(decode_header(value or ""))).strip()[:500]
    except (UnicodeDecodeError, ValueError):
        return str(value or "").strip()[:500]


def _plain_text(message: Message) -> str:
    parts = message.walk() if message.is_multipart() else [message]
    for part in parts:
        if part.get_content_disposition() == "attachment":
            continue
        if part.get_content_type() != "text/plain":
            continue
        try:
            value = part.get_content()
        except (LookupError, UnicodeDecodeError):
            payload = part.get_payload(decode=True) or b""
            value = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        text = re.sub(r"\r\n?", "\n", str(value or "")).strip()
        if text:
            return text[:20_000]
    return ""


def parse_inbound_email(raw: bytes) -> dict[str, str]:
    """Extract only sender, subject, plain text and a stable event ID."""
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise ValueError("email_payload_invalid")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    message_id = _decode_header(message.get("Message-ID"))
    event_id = message_id or hashlib.sha256(raw).hexdigest()
    sender = _decode_header(message.get("From"))[:320]
    subject = _decode_header(message.get("Subject"))
    text = _plain_text(message)
    if not sender or not text:
        raise ValueError("email_sender_or_plain_text_missing")
    return {"event_id": event_id[:160], "from_email": sender, "subject": subject, "text": text}


def build_callback_request(payload: dict[str, Any], secret: str) -> tuple[bytes, dict[str, str]]:
    if not str(secret or "").strip():
        raise ValueError("callback_secret_missing")
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(str(secret).encode("utf-8"), raw, hashlib.sha256).hexdigest()
    return raw, {
        "Content-Type": "application/json",
        "X-Lianyipei-Signature": f"sha256={signature}",
    }


def poll_once(
    config: EmailPollConfig,
    *,
    imap_factory: Callable[..., Any] = imaplib.IMAP4_SSL,
    post: Callable[..., Any] = requests.post,
) -> dict[str, Any]:
    """Poll at most ``batch_size`` unseen messages and forward safely."""
    required = (config.host, config.username, config.password, config.callback_url, config.callback_secret)
    if not config.enabled:
        return {"status": "disabled", "reason": "inbound_email_disabled", "processed": 0}
    if not all(required):
        return {"status": "disabled", "reason": "imap_configuration_missing", "processed": 0}

    client = None
    processed = failed = found = 0
    try:
        client = imap_factory(config.host, config.port, timeout=config.timeout)
        client.login(config.username, config.password)
        status, _ = client.select(config.folder, readonly=False)
        if status != "OK":
            raise RuntimeError("imap_select_failed")
        status, data = client.search(None, "UNSEEN")
        if status != "OK":
            raise RuntimeError("imap_search_failed")
        identifiers = (data[0] or b"").split() if data else []
        identifiers = identifiers[-config.batch_size :]
        found = len(identifiers)
        for message_id in identifiers:
            try:
                status, fetched = client.fetch(message_id, "(RFC822)")
                if status != "OK":
                    raise RuntimeError("imap_fetch_failed")
                raw = next((item[1] for item in fetched if isinstance(item, tuple) and isinstance(item[1], bytes)), None)
                if not raw:
                    raise ValueError("imap_message_empty")
                payload = parse_inbound_email(raw)
                callback_raw, headers = build_callback_request(payload, config.callback_secret)
                response = post(config.callback_url, data=callback_raw, headers=headers, timeout=config.timeout)
                if not 200 <= int(getattr(response, "status_code", 0)) < 300:
                    raise RuntimeError(f"callback_http_{getattr(response, 'status_code', 0)}")
                client.store(message_id, "+FLAGS", "(\\Seen)")
                processed += 1
            except Exception:
                failed += 1
        return {"status": "ok", "found": found, "processed": processed, "failed": failed}
    except Exception as exc:
        # Do not include host credentials or provider response bodies in the
        # result; the supervisor can retry while operators inspect logs.
        return {"status": "error", "reason": type(exc).__name__, "found": found, "processed": processed, "failed": failed}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            try:
                client.logout()
            except Exception:
                pass


def run_forever(config: EmailPollConfig, *, sleep_seconds: int = 30) -> None:
    import time
    while True:
        poll_once(config)
        time.sleep(max(5, int(sleep_seconds)))

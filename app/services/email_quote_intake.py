"""Authenticated inbound-email adapter for supplier quotations.

The mail gateway only needs to POST a small normalized JSON envelope.  This
module performs the security-sensitive mapping from an email address and
human-written message to one existing IntentQuote; it never creates a quote
from an unknown sender or invents missing commercial terms.
"""
from __future__ import annotations

import re
from typing import Any

from app.models import Enterprise, IntentQuote
from app.services.supplier_quote_intake import (
    SupplierQuoteParseError,
    parse_supplier_quote,
)


class EmailQuoteInboundError(ValueError):
    """Raised when an inbound email cannot be safely mapped to a quote."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = int(status_code)


_QUOTE_COMMAND = re.compile(r"(?:确认)?报价\s*#?\s*\d+", re.IGNORECASE)


def _clean_email(value: Any) -> str:
    # Header parsers may pass ``Name <address>``; accept only the address and
    # compare case-insensitively.  The address is never returned to callers.
    text = str(value or "").strip()
    match = re.search(r"<([^<>\s]+@[^<>\s]+)>", text)
    if match:
        text = match.group(1)
    if len(text) > 320 or text.count("@") != 1 or any(ch.isspace() for ch in text):
        raise EmailQuoteInboundError("from_email_invalid")
    local, domain = text.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise EmailQuoteInboundError("from_email_invalid")
    return text.casefold()


def _message_text(payload: dict[str, Any]) -> str:
    value = payload.get("text")
    if value in (None, ""):
        value = payload.get("text_plain")
    if value in (None, ""):
        value = payload.get("body")
    text = str(value or "").replace("\x00", "").strip()
    if not text:
        raise EmailQuoteInboundError("email_text_required")
    if len(text) > 20_000:
        raise EmailQuoteInboundError("email_text_too_large")
    return text


def _extract_command(text: str) -> str:
    """Ignore greetings/signatures and parse the first explicit quote line."""
    match = _QUOTE_COMMAND.search(text)
    if not match:
        raise EmailQuoteInboundError("quote_command_required")
    # Keep only the message starting at the command.  This avoids accidentally
    # parsing an older quoted reply above the supplier's current response.
    return text[match.start() :]


def _find_supplier(from_email: str) -> Enterprise:
    # ``extras`` is JSON on the current schema, so authorization is evaluated
    # in Python rather than relying on a database-specific JSON operator.
    matches = []
    for supplier in Enterprise.query.filter_by(role="enterprise").all():
        extras = supplier.extras if isinstance(supplier.extras, dict) else {}
        stored = str(extras.get("email") or "").strip().casefold()
        trust = extras.get("trust_profile") if isinstance(extras.get("trust_profile"), dict) else {}
        authorizations = extras.get("communication_authorizations") if isinstance(extras.get("communication_authorizations"), dict) else {}
        if (
            stored == from_email
            and trust.get("claim_status") == "claimed"
            and trust.get("contact_authorized") is True
            and authorizations.get("email") is True
        ):
            matches.append(supplier)
    if len(matches) > 1:
        raise EmailQuoteInboundError("sender_ambiguous", status_code=409)
    if matches:
        return matches[0]
    raise EmailQuoteInboundError("sender_not_authorized", status_code=403)


def normalize_email_quote(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an inbound envelope and return a provider-neutral quote event."""
    if not isinstance(payload, dict):
        raise EmailQuoteInboundError("callback_body_must_be_object")
    event_id = str(payload.get("event_id") or payload.get("provider_event_id") or "").strip()
    if not event_id or len(event_id) > 160:
        raise EmailQuoteInboundError("event_id_required")

    from_email = _clean_email(payload.get("from_email") or payload.get("from"))
    supplier = _find_supplier(from_email)
    text = _message_text(payload)
    command_text = _extract_command(text)
    try:
        parsed = parse_supplier_quote(command_text)
    except SupplierQuoteParseError as exc:
        raise EmailQuoteInboundError(str(exc)) from exc

    explicit_quote_id = payload.get("quote_id")
    if explicit_quote_id not in (None, ""):
        try:
            explicit_id = int(explicit_quote_id)
        except (TypeError, ValueError) as exc:
            raise EmailQuoteInboundError("quote_id_invalid") from exc
        if explicit_id != int(parsed["quote_id"]):
            raise EmailQuoteInboundError("quote_id_mismatch")

    quote = IntentQuote.query.get(int(parsed["quote_id"]))
    if quote is None:
        raise EmailQuoteInboundError("intent_quote_not_found", status_code=404)
    if int(quote.seller_id) != int(supplier.id):
        raise EmailQuoteInboundError("sender_not_quote_supplier", status_code=403)

    return {
        "event_id": event_id,
        "quote_id": int(quote.id),
        "supplier_id": int(supplier.id),
        "confirmed": bool(parsed["confirmed"]),
        "reply_price": parsed["reply_price"],
        "reply_details": parsed.get("reply_details") or {},
        "reply_notes": "通过签名邮件确认提交",
        "product_name": str(quote.product_name or "")[:100],
    }

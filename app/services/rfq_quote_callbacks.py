"""Apply authenticated supplier quote callbacks to Chain XiaoYi RFQs.

Delivery callbacks deliberately cannot change commercial data.  This module is
the separate, provider-neutral quote callback seam used by email/WeCom
adapters after they have authenticated the supplier and normalized a message.
Only a signed callback can move a pending quote to ``accepted``; prices and
commercial terms always come from the callback payload and are validated by
``IntentQuoteService``.
"""
from __future__ import annotations

from typing import Any

from app.applications.fulfillment.services.intent_quote_service import IntentQuoteService
from app.models import IntentQuote


SUPPORTED_QUOTE_PROVIDERS = {"email", "wechat", "work_wechat"}
_CHANNEL_ALIASES = {"work_wechat": "wechat"}


class QuoteCallbackError(ValueError):
    """A signed quote event cannot be applied safely."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = int(status_code)


def normalize_quote_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_QUOTE_PROVIDERS:
        raise QuoteCallbackError("unsupported_quote_provider", status_code=404)
    return value


def _bounded_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def apply_quote_event(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one already-authenticated, normalized supplier quote event.

    A callback without ``confirmed=true`` is intentionally a no-op preview.
    This lets an adapter surface an unconfirmed email/message without creating
    a commercial commitment.  The provider must send the same event again with
    explicit confirmation after its own verification step.
    """
    provider = normalize_quote_provider(provider)
    if not isinstance(payload, dict):
        raise QuoteCallbackError("callback_body_must_be_object")
    if not _bounded_text(payload.get("event_id") or payload.get("provider_event_id"), 160):
        raise QuoteCallbackError("event_id_required")
    raw_quote_id = payload.get("quote_id") or payload.get("intent_quote_id")
    try:
        quote_id = int(raw_quote_id)
    except (TypeError, ValueError):
        raise QuoteCallbackError("quote_id_required") from None
    quote = IntentQuote.query.get(quote_id)
    if quote is None:
        raise QuoteCallbackError("intent_quote_not_found", status_code=404)

    raw_supplier_id = payload.get("supplier_id")
    if raw_supplier_id is None:
        raise QuoteCallbackError("supplier_id_required")
    try:
        supplier_id = int(raw_supplier_id)
    except (TypeError, ValueError):
        raise QuoteCallbackError("supplier_id_invalid") from None
    if supplier_id != int(quote.seller_id):
        raise QuoteCallbackError("supplier_not_authorized", status_code=403)

    confirmed = payload.get("confirmed") is True
    if not confirmed:
        return {
            "quote_id": quote.id,
            "status": quote.status,
            "confirmed": False,
            "needs_confirmation": True,
            "provider": provider,
        }
    if quote.status != "pending":
        if quote.status == "accepted":
            return {
                "quote_id": quote.id,
                "status": quote.status,
                "confirmed": True,
                "idempotent": True,
                "provider": provider,
            }
        raise QuoteCallbackError(f"quote_status_not_pending:{quote.status}", status_code=409)

    raw_price = payload.get("reply_price", payload.get("price"))
    if raw_price in (None, ""):
        raise QuoteCallbackError("reply_price_required")
    details = payload.get("reply_details")
    if details is None:
        details = payload.get("details")
    if details is not None and not isinstance(details, dict):
        raise QuoteCallbackError("reply_details_must_be_object")
    accepted, error = IntentQuoteService().accept_intent_quote(
        quote_id=quote.id,
        seller_id=int(quote.seller_id),
        reply_price=raw_price,
        reply_notes=_bounded_text(payload.get("reply_notes") or payload.get("notes"), 2000) or None,
        reply_details=details or {},
        reply_channel=_CHANNEL_ALIASES.get(provider, provider),
    )
    if error or accepted is None:
        raise QuoteCallbackError(error or "quote_accept_failed", status_code=409)
    return {
        "quote_id": accepted.id,
        "status": accepted.status,
        "confirmed": True,
        "idempotent": False,
        "provider": provider,
        "reply_price": accepted.seller_reply_price,
        "reply_details": accepted.seller_reply_details or {},
    }

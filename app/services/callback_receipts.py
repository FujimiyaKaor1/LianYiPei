"""Durable third-party callback idempotency helpers."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta

from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError

from app import db
from app.models import ExternalCallbackReceipt


def callback_event_key(message: dict, raw: bytes) -> str:
    # Provider callbacks often call this field event_id while WeChat calls it
    # MsgId. Prefer the explicit provider identifier over hashing the raw JSON
    # so harmless key-order/whitespace changes on retries remain idempotent.
    msg_id = str(
        message.get("msg_id")
        or message.get("event_id")
        or message.get("provider_event_id")
        or ""
    ).strip()
    if msg_id:
        return f"msg:{msg_id}"[:160]
    stable = "|".join(str(message.get(key) or "") for key in ("from_user", "create_time", "msg_type", "event", "event_key"))
    material = stable.encode("utf-8") if stable.strip("|") else raw
    return "sha256:" + hashlib.sha256(material).hexdigest()


def claim_callback(provider: str, event_key: str) -> tuple[ExternalCallbackReceipt, bool]:
    existing = ExternalCallbackReceipt.query.filter_by(provider=provider, event_key=event_key).first()
    if existing:
        return existing, False
    receipt = ExternalCallbackReceipt(provider=provider[:40], event_key=event_key[:160], status="processing")
    db.session.add(receipt)
    try:
        db.session.commit()
        return receipt, True
    except IntegrityError:
        db.session.rollback()
        existing = ExternalCallbackReceipt.query.filter_by(provider=provider, event_key=event_key).one()
        return existing, False


def complete_callback(receipt: ExternalCallbackReceipt, response_body: str) -> None:
    receipt.status = "completed"
    receipt.response_body = str(response_body or "")[:64_000]
    receipt.completed_at = datetime.utcnow()
    db.session.commit()


def release_callback(receipt: ExternalCallbackReceipt) -> None:
    if receipt.status == "processing":
        db.session.delete(receipt)
        db.session.commit()


def cleanup_callback_receipts(
    *,
    completed_days: int = 30,
    processing_hours: int = 24,
    now: datetime | None = None,
) -> int:
    """Delete expired receipts and abandoned claims.

    Completed responses are retained long enough to cover provider retries.
    A processing claim older than a day is considered abandoned so the same
    signed callback can safely be retried instead of being blocked forever.
    """
    reference = now or datetime.utcnow()
    completed_cutoff = reference - timedelta(days=max(1, int(completed_days)))
    processing_cutoff = reference - timedelta(hours=max(1, int(processing_hours)))
    removed = ExternalCallbackReceipt.query.filter(
        or_(
            and_(
                ExternalCallbackReceipt.status == "completed",
                ExternalCallbackReceipt.completed_at.isnot(None),
                ExternalCallbackReceipt.completed_at < completed_cutoff,
            ),
            and_(
                ExternalCallbackReceipt.status == "processing",
                ExternalCallbackReceipt.created_at < processing_cutoff,
            ),
        )
    ).delete(synchronize_session=False)
    db.session.commit()
    return int(removed or 0)

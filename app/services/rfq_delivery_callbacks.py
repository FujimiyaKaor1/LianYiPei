"""Verified provider callbacks for RFQ delivery status.

Providers are allowed to report transport state, but they cannot mutate quote
content or create commercial commitments.  The callback only updates the
outbound audit record and emits an immutable Chain XiaoYi event.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app import db
from app.models_chain_xiaoyi import (
    ChainXiaoYiEvent,
    ChainXiaoYiOutboundRecord,
    ChainXiaoYiTask,
)


SUPPORTED_PROVIDERS = {"email", "wechat", "work_wechat"}
DELIVERY_STATUSES = {"queued", "sent", "delivered", "read", "failed"}
_CHANNEL_ALIASES = {"work_wechat": "wechat"}
_STATUS_RANK = {"pending": 0, "queued": 1, "sent": 2, "delivered": 3, "read": 4, "replied": 5, "rejected": 5, "timed_out": 6, "failed": -1}


class DeliveryCallbackError(ValueError):
    """A provider callback is invalid or cannot be applied safely."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = int(status_code)


def normalize_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_PROVIDERS:
        raise DeliveryCallbackError("unsupported_delivery_provider", status_code=404)
    return value


def _channel(provider: str) -> str:
    return _CHANNEL_ALIASES.get(provider, provider)


def _as_text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _find_outbound(provider: str, payload: dict[str, Any]) -> ChainXiaoYiOutboundRecord:
    raw_id = payload.get("outbound_id")
    if raw_id is not None and str(raw_id).strip():
        try:
            outbound = db.session.get(ChainXiaoYiOutboundRecord, int(raw_id))
        except (TypeError, ValueError):
            outbound = None
        if outbound:
            return outbound

    provider_message_id = _as_text(
        payload.get("provider_message_id") or payload.get("message_id"), 240
    )
    if provider_message_id:
        # JSON containment differs between SQLite/MySQL and older SQLAlchemy
        # versions.  The bounded scan is intentional: provider callbacks are
        # low-volume and this keeps the adapter portable across deployments.
        for outbound in ChainXiaoYiOutboundRecord.query.order_by(
            ChainXiaoYiOutboundRecord.id.desc()
        ).limit(5000):
            state = outbound.channel_status_json or {}
            channels = state.get("channels") if isinstance(state, dict) else {}
            if not isinstance(channels, dict):
                continue
            channel_state = channels.get(_channel(provider))
            if isinstance(channel_state, dict) and str(channel_state.get("message_id") or "") == provider_message_id:
                return outbound
    raise DeliveryCallbackError("outbound_record_not_found", status_code=404)


def _can_advance(current: str, requested: str) -> bool:
    current = str(current or "pending").lower()
    requested = str(requested or "").lower()
    if current in {"read", "replied", "rejected", "timed_out"}:
        return False
    if requested == "failed":
        return current not in {"failed", "replied"}
    if current == "failed":
        # A later retry may legitimately report queued/sent again.
        return requested in {"queued", "sent"}
    return _STATUS_RANK.get(requested, -1) > _STATUS_RANK.get(current, 0)


def apply_delivery_event(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one already-authenticated delivery event.

    The returned status is the effective persisted status.  A stale event is
    accepted as an idempotent no-op rather than reported as a provider error;
    this is important because providers can deliver callbacks out of order.
    """

    provider = normalize_provider(provider)
    if not isinstance(payload, dict):
        raise DeliveryCallbackError("callback_body_must_be_object")
    status = _as_text(payload.get("status"), 24).lower()
    if status not in DELIVERY_STATUSES:
        raise DeliveryCallbackError("unsupported_delivery_status")
    event_id = _as_text(
        payload.get("event_id") or payload.get("provider_event_id"), 160
    )
    if not event_id:
        raise DeliveryCallbackError("event_id_required")

    outbound = _find_outbound(provider, payload)
    channel = _channel(provider)
    state = dict(outbound.channel_status_json or {})
    channels = dict(state.get("channels") or {})
    channel_state = dict(channels.get(channel) or {})
    current = str(outbound.status or "pending").lower()
    effective = status if _can_advance(current, status) else current
    now = datetime.utcnow()

    if effective != current:
        outbound.status = effective
        if effective in {"delivered", "read"} and outbound.delivered_at is None:
            outbound.delivered_at = now
        if effective == "read":
            outbound.read_at = outbound.read_at or now
        if effective == "failed":
            outbound.error_message = _as_text(payload.get("error") or payload.get("reason"), 500) or "provider_delivery_failed"
        elif current == "failed":
            outbound.error_message = None

    channel_state.update(
        {
            "status": effective,
            "provider": provider,
            "event_id": event_id,
            "updated_at": now.isoformat(),
        }
    )
    provider_message_id = _as_text(
        payload.get("provider_message_id") or payload.get("message_id"), 240
    )
    if provider_message_id:
        channel_state["message_id"] = provider_message_id
    if payload.get("occurred_at"):
        channel_state["provider_occurred_at"] = _as_text(payload.get("occurred_at"), 80)
    channels[channel] = channel_state
    state["channels"] = channels
    state["last_delivery_event"] = {
        "provider": provider,
        "event_id": event_id,
        "status": effective,
        "received_at": now.isoformat(),
    }
    outbound.channel_status_json = state

    task = db.session.get(ChainXiaoYiTask, outbound.task_id)
    db.session.add(
        ChainXiaoYiEvent(
            session_id=task.session_id if task else None,
            event_type="rfq_delivery_status_updated",
            actor_id=None,
            payload={
                "task_id": outbound.task_id,
                "outbound_id": outbound.id,
                "supplier_id": outbound.supplier_id,
                "provider": provider,
                "status": effective,
                "requested_status": status,
                "event_id": event_id,
            },
        )
    )
    db.session.commit()
    return {
        "outbound_id": outbound.id,
        "status": effective,
        "requested_status": status,
        "provider": provider,
        "idempotent": effective != status,
    }

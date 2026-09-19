"""Provider-neutral, authenticated order/fulfillment event application."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from werkzeug.exceptions import NotFound

from app import db
from app.applications.fulfillment.services.order_service import OrderService


SUPPORTED_FULFILLMENT_PROVIDERS = {"erp", "payment", "econtract", "logistics", "quality", "tax"}
PROVIDER_EVENT_ALLOWLIST = {
    "erp": {
        "contract_signed", "contract_failed", "payment_succeeded", "payment_failed",
        "invoice_validated", "invoice_rejected", "shipment_dispatched", "shipment_delayed",
        "quality_passed", "quality_failed", "delivery_confirmed", "delivery_failed",
    },
    "payment": {"payment_succeeded", "payment_failed"},
    "econtract": {"contract_signed", "contract_failed"},
    "logistics": {"shipment_dispatched", "shipment_delayed", "delivery_confirmed", "delivery_failed"},
    "quality": {"quality_passed", "quality_failed"},
    "tax": {"invoice_validated", "invoice_rejected"},
}

_EXCEPTION_EVENTS = {
    "shipment_delayed",
    "delivery_failed",
    "payment_failed",
    "contract_failed",
    "quality_failed",
    "invoice_rejected",
}


class FulfillmentEventError(ValueError):
    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = int(status_code)


def normalize_fulfillment_provider(provider: str) -> str:
    value = str(provider or "").strip().lower()
    if value not in SUPPORTED_FULFILLMENT_PROVIDERS:
        raise FulfillmentEventError("unsupported_fulfillment_provider", status_code=404)
    return value


def _bounded(value: Any, limit: int = 200) -> str:
    return str(value or "").strip()[:limit]


def _sync_chain_xiaoyi_task(
    order: Any,
    *,
    provider: str,
    event_type: str,
    event_data: dict[str, Any],
    blocked_reason: str | None,
) -> None:
    """Write the provider fact into the originating Agent task.

    Orders are stored in the legacy SaaS collection, while Chain XiaoYi uses
    relational audit rows.  Keeping this bridge here means every signed
    callback is visible from the task audit API without granting the provider
    permission to perform a business action.  The helper is idempotent on the
    provider event id and also updates an existing task if a callback is
    retried after the order write already committed.
    """
    metadata = dict(getattr(order, "metadata", {}) or {})
    raw_task_id = metadata.get("chain_xiaoyi_task_id")
    if not str(raw_task_id or "").isdigit():
        return

    from app.models_chain_xiaoyi import ChainXiaoYiEvent, ChainXiaoYiSession, ChainXiaoYiTask

    task = db.session.get(ChainXiaoYiTask, int(raw_task_id))
    if not task:
        return
    session = db.session.get(ChainXiaoYiSession, task.session_id)
    # The order's enterprise is the buyer/owner.  Never let a provider
    # callback mutate a task belonging to another tenant.
    if not session or int(session.owner_id or 0) != int(getattr(order, "enterprise_id", 0) or 0):
        return

    event_id = str(event_data.get("event_id") or "")[:160]
    existing = None
    for row in ChainXiaoYiEvent.query.filter_by(session_id=session.id, event_type="fulfillment_event_received").all():
        payload = row.payload if isinstance(row.payload, dict) else {}
        if payload.get("task_id") == task.id and payload.get("event_id") == event_id and event_id:
            existing = row
            break

    status = "fulfillment_exception" if event_type in _EXCEPTION_EVENTS else None
    if event_type == "shipment_dispatched":
        status = "fulfillment_in_progress"
    elif event_type == "delivery_confirmed":
        status = "fulfillment_completed"

    fulfillment = dict((task.output_json or {}).get("fulfillment") or {})
    fulfillment.update(
        {
            "order_id": int(getattr(order, "id", 0) or 0),
            "provider": provider,
            "latest_event": event_type,
            "latest_event_id": event_id or None,
            "last_event_at": event_data.get("received_at"),
            "status": status or fulfillment.get("status") or "recorded",
        }
    )
    if event_type in _EXCEPTION_EVENTS:
        fulfillment["exception"] = {
            "event_type": event_type,
            "reason": _bounded(event_data.get("reason"), 500),
            "code": _bounded(event_data.get("code"), 100),
            "delay_days": event_data.get("delay_days"),
            "recoverable": True,
        }
    output = dict(task.output_json or {})
    output["fulfillment"] = fulfillment
    task.output_json = output

    if status and task.status in {"completed", "fulfillment_in_progress", "fulfillment_exception"}:
        task.status = status

    if not existing:
        db.session.add(
            ChainXiaoYiEvent(
                session_id=session.id,
                event_type="fulfillment_event_received",
                actor_id=None,
                payload={
                    "task_id": task.id,
                    "order_id": int(getattr(order, "id", 0) or 0),
                    "provider": provider,
                    "event_id": event_id or None,
                    "event_type": event_type,
                    "recoverable": event_type in _EXCEPTION_EVENTS,
                    "blocked_reason": blocked_reason,
                    "data": event_data,
                },
            )
        )

    # Batch material tasks fan out into child RFQ tasks.  Mirror the same
    # lifecycle marker on the parent so the buyer can monitor one purchase
    # task instead of opening every supplier-specific child task.
    parent_id = (task.input_json or {}).get("source_procurement_task_id")
    if str(parent_id or "").isdigit() and int(parent_id) != task.id:
        parent = db.session.get(ChainXiaoYiTask, int(parent_id))
        if parent and parent.session_id == session.id:
            parent_output = dict(parent.output_json or {})
            parent_fulfillment = dict(parent_output.get("fulfillment") or {})
            parent_fulfillment.update(
                {
                    "order_id": int(getattr(order, "id", 0) or 0),
                    "provider": provider,
                    "latest_event": event_type,
                    "latest_event_id": event_id or None,
                    "last_event_at": event_data.get("received_at"),
                    "status": status or parent_fulfillment.get("status") or "recorded",
                }
            )
            if event_type in _EXCEPTION_EVENTS:
                parent_fulfillment["exception"] = fulfillment["exception"]
            parent_output["fulfillment"] = parent_fulfillment
            parent.output_json = parent_output
            if status and parent.status in {"running", "completed", "fulfillment_in_progress", "fulfillment_exception"}:
                parent.status = status
            parent_event_exists = any(
                isinstance(row.payload, dict)
                and row.payload.get("task_id") == parent.id
                and row.payload.get("event_id") == event_id
                for row in ChainXiaoYiEvent.query.filter_by(session_id=session.id, event_type="fulfillment_event_received").all()
            )
            if not parent_event_exists:
                db.session.add(
                    ChainXiaoYiEvent(
                        session_id=session.id,
                        event_type="fulfillment_event_received",
                        actor_id=None,
                        payload={
                            "task_id": parent.id,
                            "child_task_id": task.id,
                            "order_id": int(getattr(order, "id", 0) or 0),
                            "provider": provider,
                            "event_id": event_id or None,
                            "event_type": event_type,
                            "recoverable": event_type in _EXCEPTION_EVENTS,
                            "blocked_reason": blocked_reason,
                            "data": event_data,
                        },
                    )
                )
    db.session.commit()


def apply_fulfillment_event(provider: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Apply one explicit external event without bypassing human gates."""
    provider = normalize_fulfillment_provider(provider)
    if not isinstance(payload, dict):
        raise FulfillmentEventError("callback_body_must_be_object")
    event_id = _bounded(payload.get("event_id") or payload.get("provider_event_id"), 160)
    if not event_id:
        raise FulfillmentEventError("event_id_required")
    try:
        order_id = int(payload.get("order_id"))
        enterprise_id = int(payload.get("enterprise_id"))
    except (TypeError, ValueError):
        raise FulfillmentEventError("order_id_and_enterprise_id_required") from None
    event_type = _bounded(payload.get("event_type"), 60).lower()
    rules: dict[str, dict[str, Any]] = {
        "contract_signed": {"metadata": {"external_contract_status": "signed"}, "result": "contract_recorded"},
        "contract_failed": {"metadata": {"external_contract_status": "failed"}, "result": "contract_failed"},
        "payment_succeeded": {"metadata": {"external_payment_status": "succeeded"}, "result": "payment_recorded"},
        "payment_failed": {"metadata": {"external_payment_status": "failed"}, "result": "payment_failed"},
        "invoice_validated": {"metadata": {"external_invoice_status": "validated"}, "result": "invoice_recorded"},
        "invoice_rejected": {"metadata": {"external_invoice_status": "rejected"}, "result": "invoice_rejected"},
        "shipment_dispatched": {"metadata": {"fulfillment_status": "shipped"}, "desired_status": "in_progress", "result": "in_progress"},
        "shipment_delayed": {"metadata": {"fulfillment_status": "delayed"}, "result": "shipment_delayed"},
        "quality_passed": {"metadata": {"quality_status": "passed"}, "result": "quality_recorded"},
        "quality_failed": {"metadata": {"quality_status": "failed"}, "result": "quality_failed"},
        "delivery_confirmed": {"metadata": {"fulfillment_status": "delivered"}, "desired_status": "completed", "result": "completed"},
        "delivery_failed": {"metadata": {"fulfillment_status": "failed"}, "result": "delivery_failed"},
    }
    rule = rules.get(event_type)
    if rule is None:
        raise FulfillmentEventError("unsupported_event_type")
    allowed_events = PROVIDER_EVENT_ALLOWLIST.get(provider)
    if allowed_events is not None and event_type not in allowed_events:
        raise FulfillmentEventError("provider_not_authorized_for_event", status_code=403)

    safe_data = {
        "event_id": event_id,
        "provider": provider,
        "received_at": datetime.utcnow().isoformat() + "Z",
    }
    for key in ("reference", "tracking_no", "invoice_no", "occurred_at", "reason", "code", "expected_delivery_at"):
        value = _bounded(payload.get(key), 200)
        if value:
            safe_data[key] = value
    if payload.get("delay_days") is not None:
        try:
            safe_data["delay_days"] = max(0, min(int(payload.get("delay_days")), 3650))
        except (TypeError, ValueError):
            pass
    try:
        order, idempotent, blocked_reason = OrderService.record_external_event(
            order_id,
            enterprise_id,
            event_type,
            safe_data,
            metadata_updates=rule["metadata"],
            desired_status=rule.get("desired_status"),
        )
    except NotFound as exc:
        raise FulfillmentEventError("order_not_found", status_code=404) from exc
    # The order write and the Agent audit live in the same local database, but
    # the order service commits internally.  Re-run the bridge on retries so a
    # transient audit failure can self-heal without creating a duplicate event.
    _sync_chain_xiaoyi_task(
        order,
        provider=provider,
        event_type=event_type,
        event_data=safe_data,
        blocked_reason=blocked_reason,
    )
    if idempotent:
        return {"order_id": order_id, "status": order.status, "idempotent": True}
    result = str(rule["result"])
    if blocked_reason:
        result = "event_recorded_pending_confirmation"
    return {
        "order_id": order_id,
        "status": result,
        "order_status": order.status,
        "blocked_reason": blocked_reason,
        "idempotent": False,
    }

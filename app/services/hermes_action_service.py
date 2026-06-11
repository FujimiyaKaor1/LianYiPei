"""
Hermes remote-operation service for ChainYiPei alerts.

This module intentionally keeps the first remote-control surface small:
Hermes can inspect alerts and prepare a few auditable actions, but every
state-changing action must be confirmed with a short-lived pending action id.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from typing import Any, Optional

from flask import current_app

from app import db
from app.models import Alert, Enterprise, HermesPendingAction
from app.services.operation_logger import log_operation

CONFIRMATION_PHRASE = "确认执行"


class HermesActionError(Exception):
    def __init__(self, code: str, message: str = "", status_code: int = 400):
        super().__init__(message or code)
        self.code = code
        self.message = message or code
        self.status_code = status_code


def _utc_now() -> datetime:
    return datetime.utcnow()


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if isinstance(dt, datetime) else None


def _clamp_limit(raw: Any, default: int = 20, maximum: int = 100) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(1, min(maximum, value))


def _as_int(value: Any, field: str, required: bool = True) -> Optional[int]:
    if value in (None, ""):
        if required:
            raise HermesActionError("invalid_parameter", f"{field} is required")
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise HermesActionError("invalid_parameter", f"{field} must be an integer")


def _enterprise_name(enterprise_id: Optional[int]) -> Optional[str]:
    if not enterprise_id:
        return None
    enterprise = Enterprise.query.get(enterprise_id)
    return enterprise.name if enterprise else None


def alert_to_dict(alert: Alert) -> dict[str, Any]:
    analysis = alert.analysis_data if isinstance(alert.analysis_data, dict) else {}
    history = alert.workflow_history if isinstance(alert.workflow_history, list) else []
    active_workflows = [
        entry
        for entry in history
        if isinstance(entry, dict) and entry.get("status") in {"pending", "processing"}
    ]

    return {
        "id": alert.id,
        "product_name": alert.product_name,
        "message": alert.message,
        "level": alert.level,
        "dimension": alert.dimension,
        "alert_type": alert.alert_type,
        "severity_score": alert.severity_score,
        "is_active": bool(alert.is_active),
        "suggestion": alert.suggestion,
        "created_at": _iso(alert.created_at),
        "risk_reason": analysis.get("risk_reason", ""),
        "impact_scope": analysis.get("impact_scope", ""),
        "ai_suggestions": analysis.get("ai_suggestions", []),
        "data_source_info": analysis.get("data_source_info", {}),
        "historical_trend": analysis.get("historical_trend", []),
        "active_workflows": active_workflows,
        "workflow_history": history,
        "dashboard_url": f"/dashboard/alert-center?alert_id={alert.id}",
    }


def list_alerts(
    *,
    level: Optional[str] = None,
    status: Optional[str] = None,
    limit: Any = 20,
) -> list[dict[str, Any]]:
    query = Alert.query
    if level:
        query = query.filter(Alert.level == level)
    if status == "active":
        query = query.filter(Alert.is_active == True)
    elif status in {"inactive", "closed"}:
        query = query.filter(Alert.is_active == False)

    rows = (
        query.order_by(Alert.created_at.desc())
        .limit(_clamp_limit(limit))
        .all()
    )
    return [alert_to_dict(alert) for alert in rows]


def get_alert(alert_id: int) -> Optional[dict[str, Any]]:
    alert = Alert.query.get(alert_id)
    return alert_to_dict(alert) if alert else None


def preview_action(
    *,
    action: str,
    alert_id: Any,
    requested_by: str = "",
    parameters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    clean_action = (action or "").strip().lower()
    if clean_action not in {"assign_alert", "close_alert", "mark_alert_read"}:
        raise HermesActionError("unsupported_action", f"Unsupported action: {action}")

    alert_pk = _as_int(alert_id, "alert_id")
    alert = Alert.query.get(alert_pk)
    if not alert:
        raise HermesActionError("alert_not_found", f"Alert {alert_pk} not found", 404)

    params = _normalize_action_params(clean_action, parameters or {})
    summary = _build_preview_summary(clean_action, alert, params)
    ttl = int(current_app.config.get("HERMES_ACTION_CONFIRM_TTL_SECONDS", 300))
    expires_at = _utc_now() + timedelta(seconds=ttl)
    pending_action_id = secrets.token_urlsafe(24)

    pending = HermesPendingAction(
        id=pending_action_id,
        action=clean_action,
        alert_id=alert_pk,
        requested_by=(requested_by or "hermes").strip()[:120],
        parameters=params,
        summary=summary,
        expires_at=expires_at,
    )
    db.session.add(pending)
    db.session.commit()

    return {
        "success": True,
        "action": clean_action,
        "alert_id": alert_pk,
        "summary": summary,
        "requires_confirmation": True,
        "confirmation_phrase": CONFIRMATION_PHRASE,
        "pending_action_id": pending_action_id,
        "expires_at": _iso(expires_at),
    }


def execute_action(*, pending_action_id: str, confirmation: str) -> dict[str, Any]:
    pending = HermesPendingAction.query.get((pending_action_id or "").strip())
    if not pending or pending.status != "pending":
        raise HermesActionError("pending_action_not_found", "Pending action not found", 404)

    if pending.expires_at <= _utc_now():
        pending.status = "expired"
        db.session.add(pending)
        db.session.commit()
        raise HermesActionError("pending_action_expired", "Pending action expired")

    if (confirmation or "").strip() != CONFIRMATION_PHRASE:
        raise HermesActionError(
            "confirmation_required",
            f"Please reply exactly: {CONFIRMATION_PHRASE}",
        )

    payload = pending.to_payload()
    try:
        result = _execute_pending(payload)
        pending.status = "executed"
        pending.executed_at = _utc_now()
        db.session.add(pending)
        db.session.commit()
        _log_hermes_action(payload, "success", "")
        return {"success": True, "result": result}
    except HermesActionError:
        db.session.rollback()
        raise
    except Exception as exc:
        db.session.rollback()
        _log_hermes_action(payload, "error", str(exc))
        raise HermesActionError("action_execute_failed", str(exc), 500)


def clear_pending_actions() -> None:
    """Test helper; harmless in production."""
    HermesPendingAction.query.delete()
    db.session.commit()


def _normalize_action_params(action: str, params: dict[str, Any]) -> dict[str, Any]:
    if action == "assign_alert":
        assigned_to = _as_int(params.get("assigned_to"), "assigned_to")
        assigned_by = _as_int(params.get("assigned_by"), "assigned_by")
        if Enterprise.query.get(assigned_to) is None:
            raise HermesActionError("invalid_parameter", "assigned_to enterprise not found")
        if Enterprise.query.get(assigned_by) is None:
            raise HermesActionError("invalid_parameter", "assigned_by enterprise not found")
        return {
            "assigned_to": assigned_to,
            "assigned_by": assigned_by,
            "deadline": (params.get("deadline") or "").strip() or None,
        }

    if action == "close_alert":
        operator_id = _as_int(params.get("operator_id"), "operator_id")
        reason = (params.get("reason") or "Hermes 确认关闭预警").strip()
        return {"operator_id": operator_id, "reason": reason[:500]}

    operator_id = _as_int(params.get("operator_id"), "operator_id", required=False)
    return {"operator_id": operator_id, "note": (params.get("note") or "").strip()[:500]}


def _build_preview_summary(action: str, alert: Alert, params: dict[str, Any]) -> str:
    if action == "assign_alert":
        assignee = _enterprise_name(params.get("assigned_to")) or params.get("assigned_to")
        assigner = _enterprise_name(params.get("assigned_by")) or params.get("assigned_by")
        return (
            f"将预警 #{alert.id}「{alert.product_name}」派发给 {assignee}，"
            f"派发人 {assigner}。"
        )
    if action == "close_alert":
        return f"将预警 #{alert.id}「{alert.product_name}」标记为已关闭，原因：{params.get('reason')}"
    return f"将预警 #{alert.id}「{alert.product_name}」标记为 Hermes 已读。"


def _execute_pending(pending: dict[str, Any]) -> dict[str, Any]:
    action = pending["action"]
    alert_id = pending["alert_id"]
    params = pending["parameters"]
    alert = Alert.query.get(alert_id)
    if not alert:
        raise HermesActionError("alert_not_found", f"Alert {alert_id} not found", 404)

    if action == "assign_alert":
        from app.services.alert_workflow_service import assign_workflow

        deadline = _parse_deadline(params.get("deadline"))
        workflow = assign_workflow(
            alert_id,
            params["assigned_to"],
            params["assigned_by"],
            deadline=deadline,
        )
        return {
            "action": action,
            "alert_id": alert_id,
            "workflow_id": workflow.id,
            "status": workflow.status,
        }

    if action == "close_alert":
        history = alert.workflow_history if isinstance(alert.workflow_history, list) else []
        history.append(
            {
                "assigned_to": params["operator_id"],
                "assigned_by": params["operator_id"],
                "assigned_at": _iso(_utc_now()),
                "status": "completed",
                "handling_notes": params["reason"],
                "evidence_urls": [],
                "completed_at": _iso(_utc_now()),
                "reviewed_by": params["operator_id"],
                "review_result": "approved",
                "review_notes": "Hermes 确认执行",
            }
        )
        alert.workflow_history = history
        alert.is_active = False
        db.session.add(alert)
        return {"action": action, "alert_id": alert_id, "is_active": False}

    alert.auto_pushed = True
    db.session.add(alert)
    return {"action": action, "alert_id": alert_id, "auto_pushed": True}


def _parse_deadline(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        raise HermesActionError("invalid_parameter", "deadline must be ISO datetime")


def _log_hermes_action(pending: dict[str, Any], result: str, error_message: str) -> None:
    params = pending.get("parameters") or {}
    user_id = params.get("assigned_by") or params.get("operator_id") or 0
    log_operation(
        user_id=int(user_id or 0),
        operation_type="hermes_action_execute",
        operation_target=pending.get("action", ""),
        target_id=pending.get("alert_id"),
        operation_detail=(
            f"requested_by={pending.get('requested_by')} "
            f"pending_action_id={pending.get('id')} summary={pending.get('summary')}"
        ),
        result=result,
        error_message=error_message,
    )

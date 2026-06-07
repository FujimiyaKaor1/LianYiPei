"""
信用分变更事件：存于 Enterprise.credit_score_events（JSON 列表），替代 credit_score_history 表。

每条为 dict: id, old_score, new_score, change_value, change_type, reason, created_at (ISO8601)。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from app.models import Enterprise


def _events_raw(ent: Enterprise) -> list:
    raw = getattr(ent, "credit_score_events", None)
    return list(raw) if isinstance(raw, list) else []


def append_credit_event(
    ent: Enterprise,
    old_score: float,
    new_score: float,
    change_value: float,
    change_type: str,
    reason: str,
) -> dict[str, Any]:
    events = _events_raw(ent)
    rec = {
        "id": str(uuid.uuid4()),
        "old_score": float(old_score),
        "new_score": float(new_score),
        "change_value": float(change_value),
        "change_type": change_type,
        "reason": reason or change_type,
        "created_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }
    events.append(rec)
    ent.credit_score_events = events
    return rec


def credit_events_newest_first(ent: Enterprise) -> list[dict[str, Any]]:
    events = _events_raw(ent)
    return sorted(
        events,
        key=lambda x: (x.get("created_at") or ""),
        reverse=True,
    )


def credit_events_oldest_first(ent: Enterprise) -> list[dict[str, Any]]:
    events = _events_raw(ent)
    return sorted(
        events,
        key=lambda x: (x.get("created_at") or ""),
    )


def count_credit_events(ent: Enterprise) -> int:
    return len(_events_raw(ent))


def find_credit_event(ent: Enterprise, event_id: str) -> Optional[dict[str, Any]]:
    for e in _events_raw(ent):
        if str(e.get("id")) == str(event_id):
            return e
    return None


def slice_credit_events(
    ent: Enterprise, limit: int = 10, offset: int = 0
) -> list[dict[str, Any]]:
    rows = credit_events_newest_first(ent)
    return rows[offset : offset + limit]


def event_to_api_dict(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": e.get("id"),
        "old_score": e.get("old_score"),
        "new_score": e.get("new_score"),
        "change_value": e.get("change_value"),
        "change_type": e.get("change_type"),
        "reason": e.get("reason"),
        "created_at": e.get("created_at"),
    }

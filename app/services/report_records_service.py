"""举报记录：存入被举报方 Enterprise.extras['reports_received'] 列表。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app import db
from app.models import Enterprise

logger = logging.getLogger("app.ops")


def _reports_received(ent: Enterprise) -> list:
    ex = ent.extras if isinstance(ent.extras, dict) else {}
    raw = ex.get("reports_received")
    return list(raw) if isinstance(raw, list) else []


def _set_reports(ent: Enterprise, rows: list) -> None:
    ex = dict(ent.extras) if isinstance(ent.extras, dict) else {}
    ex["reports_received"] = rows
    ent.extras = ex
    db.session.add(ent)


def _next_report_id() -> int:
    m = 0
    for ent in Enterprise.query.all():
        for r in _reports_received(ent):
            if isinstance(r, dict):
                m = max(m, int(r.get("id") or 0))
    return m + 1


def append_report(
    reporter_id: int,
    reported_id: int,
    report_type: str,
    description: str,
    target_type: Optional[str] = None,
    target_id: Optional[int] = None,
) -> Tuple[int, Enterprise]:
    reported = Enterprise.query.get(reported_id)
    if not reported:
        raise ValueError("被举报企业不存在")

    rid = _next_report_id()
    rows = _reports_received(reported)
    rows.append(
        {
            "id": rid,
            "reporter_id": reporter_id,
            "report_type": report_type,
            "description": description,
            "target_type": target_type,
            "target_id": target_id,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "handler_id": None,
            "handling_notes": None,
            "handled_at": None,
        }
    )
    _set_reports(reported, rows)
    return rid, reported


def list_reports(status: str = "pending", limit: int = 50) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for ent in Enterprise.query.all():
        for r in _reports_received(ent):
            if not isinstance(r, dict):
                continue
            if r.get("status") != status:
                continue
            rep = Enterprise.query.get(r.get("reporter_id"))
            out.append(
                {
                    "id": r.get("id"),
                    "reporter_id": r.get("reporter_id"),
                    "reporter_name": rep.name if rep else "",
                    "reported_id": ent.id,
                    "reported_name": ent.name,
                    "report_type": r.get("report_type"),
                    "description": r.get("description"),
                    "status": r.get("status"),
                    "created_at": r.get("created_at"),
                }
            )
    out.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return out[:limit]


def find_report(report_id: int) -> Optional[Tuple[Enterprise, dict, int]]:
    for ent in Enterprise.query.all():
        for i, r in enumerate(_reports_received(ent)):
            if isinstance(r, dict) and int(r.get("id") or 0) == int(report_id):
                return ent, r, i
    return None


def handle_report(
    report_id: int,
    handler_id: int,
    result: str,
    notes: str = "",
) -> bool:
    """result: verified_true / verified_false"""
    found = find_report(report_id)
    if not found:
        return False
    ent, r, idx = found
    r["status"] = result
    r["handler_id"] = handler_id
    r["handling_notes"] = notes
    r["handled_at"] = datetime.utcnow().isoformat() + "Z"
    rows = _reports_received(ent)
    rows[idx] = r
    _set_reports(ent, rows)
    logger.info(
        "report_handled id=%s result=%s handler_id=%s", report_id, result, handler_id
    )
    return True

"""
预警处置工作流（数据存入 Alert.workflow_history JSON 列表）。
workflow_id 编码：alert_id * 100000 + (在 history 中的 1-based 下标)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from app import db
from app.models import Alert, Enterprise, Message

logger = logging.getLogger(__name__)

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_REJECTED = "rejected"

VALID_TRANSITIONS = {
    STATUS_PENDING: [STATUS_PROCESSING],
    STATUS_PROCESSING: [STATUS_COMPLETED, STATUS_REJECTED],
    STATUS_COMPLETED: [],
    STATUS_REJECTED: [STATUS_PROCESSING],
}


def _encode_wid(alert_id: int, index_0: int) -> int:
    return alert_id * 100000 + index_0 + 1


def _decode_wid(workflow_id: int) -> tuple:
    alert_id = workflow_id // 100000
    idx = workflow_id % 100000 - 1
    return alert_id, idx


def _hist(a: Alert) -> List[Dict[str, Any]]:
    h = a.workflow_history
    return list(h) if isinstance(h, list) else []


def _save_hist(a: Alert, hist: List[Dict[str, Any]]) -> None:
    a.workflow_history = hist


def assign_workflow(
    alert_id: int,
    assigned_to: int,
    assigned_by: int,
    deadline: Optional[datetime] = None,
) -> SimpleNamespace:
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    for e in hist:
        if isinstance(e, dict) and e.get("status") in (STATUS_PENDING, STATUS_PROCESSING):
            raise ValueError(f"预警 {alert_id} 已有活跃工作流")

    entry = {
        "assigned_to": assigned_to,
        "assigned_by": assigned_by,
        "assigned_at": datetime.utcnow().isoformat(),
        "status": STATUS_PENDING,
        "handling_notes": None,
        "evidence_urls": [],
        "completed_at": None,
        "reviewed_by": None,
        "review_result": None,
        "review_notes": None,
    }
    hist.append(entry)
    _save_hist(alert, hist)
    db.session.add(alert)
    db.session.flush()

    wid = _encode_wid(alert_id, len(hist) - 1)
    _notify_assignee_simple(alert, assigned_to, wid)

    logger.info(
        "alert_workflow assign alert_id=%s workflow_id=%s -> %s",
        alert_id,
        wid,
        assigned_to,
    )
    return SimpleNamespace(id=wid, alert_id=alert_id, status=STATUS_PENDING)


def start_processing(workflow_id: int, operator_id: int) -> SimpleNamespace:
    alert_id, idx = _decode_wid(workflow_id)
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    if idx < 0 or idx >= len(hist):
        raise ValueError("工作流不存在")
    w = hist[idx]
    _check_transition(w, STATUS_PROCESSING)
    w["status"] = STATUS_PROCESSING
    _save_hist(alert, hist)
    db.session.commit()
    return SimpleNamespace(id=workflow_id, alert_id=alert_id, status=w["status"])


def submit_result(
    workflow_id: int,
    operator_id: int,
    handling_notes: str,
    evidence_urls: Optional[List[str]] = None,
) -> SimpleNamespace:
    alert_id, idx = _decode_wid(workflow_id)
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    w = hist[idx]
    if w.get("status") == STATUS_PENDING:
        w["status"] = STATUS_PROCESSING
    _check_transition(w, STATUS_COMPLETED)
    if not handling_notes or not str(handling_notes).strip():
        raise ValueError("处理说明不能为空")
    w["handling_notes"] = handling_notes.strip()
    w["evidence_urls"] = evidence_urls or []
    w["completed_at"] = datetime.utcnow().isoformat()
    w["status"] = STATUS_COMPLETED
    _save_hist(alert, hist)
    db.session.commit()
    return SimpleNamespace(id=workflow_id, alert_id=alert_id, status=STATUS_COMPLETED)


def review_workflow(
    workflow_id: int,
    reviewer_id: int,
    approved: bool,
    review_notes: str = "",
) -> SimpleNamespace:
    alert_id, idx = _decode_wid(workflow_id)
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    w = hist[idx]
    if w.get("status") != STATUS_COMPLETED:
        raise ValueError(f"工作流状态为 {w.get('status')}，只有 completed 状态才能审核")
    w["reviewed_by"] = reviewer_id
    w["review_notes"] = review_notes
    if approved:
        w["review_result"] = "approved"
        alert.is_active = False
    else:
        w["review_result"] = "rejected"
        w["status"] = STATUS_PROCESSING
        w["completed_at"] = None
    _save_hist(alert, hist)
    db.session.commit()
    return SimpleNamespace(
        id=workflow_id,
        alert_id=alert_id,
        status=w["status"],
        review_result=w.get("review_result"),
    )


def get_workflow_detail(workflow_id: int) -> Dict:
    alert_id, idx = _decode_wid(workflow_id)
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    if idx < 0 or idx >= len(hist):
        raise ValueError("工作流不存在")
    return _entry_to_dict(alert, hist[idx], workflow_id, include_alert=True)


def get_workflows_for_alert(alert_id: int) -> List[Dict]:
    alert = Alert.query.get_or_404(alert_id)
    hist = _hist(alert)
    out = []
    for i, e in enumerate(hist):
        wid = _encode_wid(alert_id, i)
        out.append(_entry_to_dict(alert, e, wid, include_alert=False))
    return out


def get_my_workflows(user_id: int, status: Optional[str] = None) -> List[Dict]:
    q = Alert.query.filter(Alert.workflow_history.isnot(None))
    res = []
    for a in q.all():
        hist = _hist(a)
        for i, e in enumerate(hist):
            if e.get("assigned_to") != user_id:
                continue
            if status and e.get("status") != status:
                continue
            wid = _encode_wid(a.id, i)
            res.append(_entry_to_dict(a, e, wid, include_alert=True))
    res.sort(key=lambda x: x.get("assigned_at") or "", reverse=True)
    return res


def get_workflow_stats() -> Dict:
    total = 0
    by_status: Dict[str, int] = {}
    for a in Alert.query.all():
        for e in _hist(a):
            total += 1
            st = e.get("status") or "unknown"
            by_status[st] = by_status.get(st, 0) + 1
    completed = by_status.get(STATUS_COMPLETED, 0)
    resolution_rate = round(completed / total * 100, 1) if total else 0.0
    return {
        "total": total,
        "by_status": by_status,
        "completed": completed,
        "resolution_rate": resolution_rate,
        "level_response_hours": {},
        "daily_trend": [],
        "overdue_count": 0,
    }


def _check_transition(entry: Dict, target_status: str) -> None:
    st = entry.get("status")
    allowed = VALID_TRANSITIONS.get(st, [])
    if target_status not in allowed:
        raise ValueError(
            f"不允许的状态转换: {st} → {target_status}，允许: {allowed}"
        )


def _notify_assignee_simple(alert: Alert, assigned_to: int, workflow_id: int) -> None:
    level_map = {"red": "红色预警（严重）", "yellow": "黄色预警（警告）", "blue": "蓝色预警（提示）"}
    level_label = level_map.get(alert.level, alert.level)
    msg = Message(
        recipient_id=assigned_to,
        message_type="alert",
        title=f"【预警处置任务】{alert.product_name}",
        content=(
            f"您收到一个{level_label}处置任务：{alert.message}\n请及时处理并填写处理记录。"
        ),
        link_url=f"/dashboard/alert-workflow/{workflow_id}",
        is_read=False,
        priority="high" if alert.level == "red" else "normal",
    )
    db.session.add(msg)


def _entry_to_dict(
    alert: Alert,
    e: Dict,
    workflow_id: int,
    include_alert: bool,
) -> Dict:
    aid_to = e.get("assigned_to")
    aid_by = e.get("assigned_by")
    rev_by = e.get("reviewed_by")
    assignee = Enterprise.query.get(aid_to) if aid_to else None
    assigner = Enterprise.query.get(aid_by) if aid_by else None
    reviewer = Enterprise.query.get(rev_by) if rev_by else None
    d = {
        "id": workflow_id,
        "alert_id": alert.id,
        "assigned_to": aid_to,
        "assigned_to_name": assignee.name if assignee else None,
        "assigned_by": aid_by,
        "assigned_by_name": assigner.name if assigner else None,
        "assigned_at": e.get("assigned_at"),
        "status": e.get("status"),
        "handling_notes": e.get("handling_notes"),
        "evidence_urls": e.get("evidence_urls") or [],
        "completed_at": e.get("completed_at"),
        "reviewed_by": rev_by,
        "reviewed_by_name": reviewer.name if reviewer else None,
        "review_result": e.get("review_result"),
        "review_notes": e.get("review_notes"),
    }
    if include_alert:
        d["alert"] = {
            "id": alert.id,
            "product_name": alert.product_name,
            "message": alert.message,
            "level": alert.level,
            "suggestion": alert.suggestion,
            "alert_type": getattr(alert, "alert_type", None),
        }
    return d

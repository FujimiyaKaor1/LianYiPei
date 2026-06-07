"""
质量标签服务（存储于 Enterprise.qualifications JSON 列表）
- 政府绿标 / 链主验厂 / 第三方评分
- 标签有效期管理与自动过期
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from app import db
from app.models import Enterprise, Message

LABEL_TYPE_NAMES = {
    "government_green": "政府绿标",
    "lead_inspection": "链主验厂",
    "third_party": "第三方评分",
}

KNOWN_LABEL_TYPES = frozenset(LABEL_TYPE_NAMES.keys())

DEFAULT_VALIDITY_DAYS = {
    "government_green": 365,
    "lead_inspection": 365,
    "third_party": 180,
}


def _qualifications(ent: Enterprise) -> list[dict]:
    q = ent.qualifications
    if not q:
        return []
    if not isinstance(q, list):
        return []
    return [x for x in q if isinstance(x, dict)]


def _set_qualifications(ent: Enterprise, rows: list[dict]) -> None:
    ent.qualifications = rows
    db.session.add(ent)


def _next_label_id(rows: list[dict]) -> int:
    ids = [int(x.get("id") or 0) for x in rows]
    return max(ids, default=0) + 1


def _parse_date(val: Any) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        try:
            return date.fromisoformat(val[:10])
        except ValueError:
            return None
    return None


def _is_active_label(row: dict, today: date) -> bool:
    if row.get("status") != "active":
        return False
    vu = _parse_date(row.get("valid_until"))
    if vu is None:
        return True
    return vu >= today


def _quality_rows(ent: Enterprise) -> list[dict]:
    return [r for r in _qualifications(ent) if r.get("label_type") in KNOWN_LABEL_TYPES]


def _label_to_dict(row: dict, enterprise_id: int) -> dict:
    issuer_name = ""
    iid = row.get("issuer_id")
    if iid:
        issuer = Enterprise.query.get(iid)
        issuer_name = issuer.name if issuer else ""
    lt = row.get("label_type") or ""
    vf, vu = row.get("valid_from"), row.get("valid_until")
    ca = row.get("created_at")
    return {
        "id": row.get("id"),
        "enterprise_id": enterprise_id,
        "label_type": lt,
        "label_type_name": LABEL_TYPE_NAMES.get(lt, lt),
        "label_name": row.get("label_name"),
        "issuer_id": iid,
        "issuer_name": issuer_name,
        "certificate_no": row.get("certificate_no"),
        "valid_from": vf[:10] if isinstance(vf, str) else (vf.isoformat() if hasattr(vf, "isoformat") else None),
        "valid_until": vu[:10] if isinstance(vu, str) else (vu.isoformat() if hasattr(vu, "isoformat") else None),
        "status": row.get("status"),
        "created_at": ca if isinstance(ca, str) else (ca.isoformat() if hasattr(ca, "isoformat") else None),
    }


def get_active_labels(enterprise_id: int) -> list:
    _auto_expire_labels(enterprise_id)
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return []
    today = date.today()
    out = []
    for row in _quality_rows(ent):
        if _is_active_label(row, today):
            out.append(_label_to_dict(row, enterprise_id))
    out.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return out


def get_all_labels(enterprise_id: int) -> list:
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return []
    rows = _quality_rows(ent)
    rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return [_label_to_dict(r, enterprise_id) for r in rows]


def get_labels_by_type(enterprise_id: int, label_type: str) -> list:
    _auto_expire_labels(enterprise_id)
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return []
    today = date.today()
    out = []
    for row in _quality_rows(ent):
        if row.get("label_type") == label_type and _is_active_label(row, today):
            out.append(_label_to_dict(row, enterprise_id))
    return out


def grant_government_green_label(
    enterprise_id: int,
    issuer_id: int,
    label_name: str = "政府绿色认证",
    certificate_no: str = "",
    valid_days: int = 365,
) -> dict:
    issuer = Enterprise.query.get(issuer_id)
    if not issuer or issuer.role not in ("admin", "government"):
        return {"success": False, "message": "只有政府用户可以颁发绿标"}

    enterprise = Enterprise.query.get(enterprise_id)
    if not enterprise:
        return {"success": False, "message": "企业不存在"}

    today = date.today()
    rows = _qualifications(enterprise)
    lid = _next_label_id(rows)
    valid_until = today + timedelta(days=valid_days)
    new_row = {
        "id": lid,
        "label_type": "government_green",
        "label_name": label_name,
        "issuer_id": issuer_id,
        "certificate_no": certificate_no or None,
        "valid_from": today.isoformat(),
        "valid_until": valid_until.isoformat(),
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
    }
    rows.append(new_row)
    _set_qualifications(enterprise, rows)

    _send_label_message(
        enterprise_id=enterprise_id,
        title="获得政府绿标认证",
        content=f'恭喜！您的企业已获得政府绿标认证"{label_name}"，有效期至 {valid_until}。',
    )
    db.session.commit()
    return {"success": True, "label_id": lid}


def grant_lead_inspection_label(
    enterprise_id: int,
    issuer_id: int,
    label_name: str = "链主验厂通过",
    certificate_no: str = "",
    valid_days: int = 365,
    inspection_notes: str = "",
) -> dict:
    issuer = Enterprise.query.get(issuer_id)
    if not issuer or not issuer.is_lead_enterprise:
        return {"success": False, "message": "只有链主企业可以颁发验厂标签"}

    enterprise = Enterprise.query.get(enterprise_id)
    if not enterprise:
        return {"success": False, "message": "企业不存在"}

    today = date.today()
    rows = _qualifications(enterprise)
    lid = _next_label_id(rows)
    vn = today + timedelta(days=valid_days)
    disp_name = label_name or f"{issuer.name}验厂通过"
    new_row = {
        "id": lid,
        "label_type": "lead_inspection",
        "label_name": disp_name,
        "issuer_id": issuer_id,
        "certificate_no": certificate_no or None,
        "valid_from": today.isoformat(),
        "valid_until": vn.isoformat(),
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "inspection_notes": inspection_notes,
    }
    rows.append(new_row)
    _set_qualifications(enterprise, rows)

    _send_label_message(
        enterprise_id=enterprise_id,
        title="通过链主验厂",
        content=f'恭喜！您已通过"{issuer.name}"的验厂审核，验厂标签有效期至 {vn}。{inspection_notes}',
    )
    db.session.commit()
    return {"success": True, "label_id": lid}


def apply_reinspection(enterprise_id: int, issuer_id: int, reason: str = "") -> dict:
    issuer = Enterprise.query.get(issuer_id)
    enterprise = Enterprise.query.get(enterprise_id)
    if not issuer or not enterprise:
        return {"success": False, "message": "企业不存在"}

    _send_label_message(
        enterprise_id=issuer_id,
        title="收到重新验厂申请",
        content=f'企业"{enterprise.name}"申请重新验厂。原因：{reason or "未说明"}',
        link_url=f"/quality-labels/inspection/{enterprise_id}",
    )
    db.session.commit()
    return {"success": True, "message": "重新验厂申请已提交"}


def sync_third_party_rating(
    enterprise_id: int,
    rating_source: str = "企查查",
    rating_value: str = "",
    rating_detail: str = "",
    valid_days: int = 180,
) -> dict:
    enterprise = Enterprise.query.get(enterprise_id)
    if not enterprise:
        return {"success": False, "message": "企业不存在"}

    rows = _qualifications(enterprise)
    prefix = f"{rating_source}"
    for row in rows:
        if row.get("label_type") != "third_party":
            continue
        if row.get("status") != "active":
            continue
        ln = row.get("label_name") or ""
        if ln.startswith(prefix):
            row["status"] = "revoked"

    today = date.today()
    lid = _next_label_id(rows)
    vn = today + timedelta(days=valid_days)
    new_row = {
        "id": lid,
        "label_type": "third_party",
        "label_name": f"{rating_source}信用评分",
        "issuer_id": None,
        "certificate_no": rating_value,
        "valid_from": today.isoformat(),
        "valid_until": vn.isoformat(),
        "status": "active",
        "created_at": datetime.utcnow().isoformat(),
        "rating_detail": rating_detail,
    }
    rows.append(new_row)
    _set_qualifications(enterprise, rows)
    db.session.commit()
    return {"success": True, "label_id": lid, "rating": rating_value}


def fetch_third_party_rating(enterprise_name: str, source: str = "企查查") -> dict:
    import hashlib

    h = int(hashlib.md5(enterprise_name.encode()).hexdigest()[:4], 16)
    ratings = ["AAA", "AA+", "AA", "AA-", "A+", "A", "BBB"]
    rating = ratings[h % len(ratings)]
    return {
        "success": True,
        "source": source,
        "enterprise_name": enterprise_name,
        "rating": rating,
        "detail": f"{source}综合信用评级：{rating}",
    }


def revoke_label(label_id: int, operator_id: int, reason: str = "") -> dict:
    ent = None
    target = None
    for e in Enterprise.query.all():
        for row in _quality_rows(e):
            if int(row.get("id") or 0) == int(label_id):
                ent = e
                target = row
                break
        if target:
            break

    if not target or not ent:
        return {"success": False, "message": "标签不存在"}

    operator = Enterprise.query.get(operator_id)
    if not operator:
        return {"success": False, "message": "操作者不存在"}

    lt = target.get("label_type")
    if lt == "government_green" and operator.role not in ("admin", "government"):
        return {"success": False, "message": "无权撤销政府绿标"}
    if lt == "lead_inspection" and not operator.is_lead_enterprise:
        return {"success": False, "message": "无权撤销验厂标签"}

    target["status"] = "revoked"
    _set_qualifications(ent, _qualifications(ent))
    _send_label_message(
        enterprise_id=ent.id,
        title="质量标签已撤销",
        content=f'您的"{target.get("label_name")}"标签已被撤销。原因：{reason or "未说明"}',
        priority="high",
    )
    db.session.commit()
    return {"success": True}


def _auto_expire_labels(enterprise_id: int):
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return
    today = date.today()
    rows = _qualifications(ent)
    changed = False
    for row in rows:
        if row.get("label_type") not in KNOWN_LABEL_TYPES:
            continue
        if row.get("status") != "active":
            continue
        vu = _parse_date(row.get("valid_until"))
        if vu is not None and vu < today:
            row["status"] = "expired"
            changed = True
            _send_label_message(
                enterprise_id=enterprise_id,
                title="质量标签已过期",
                content=f'您的"{row.get("label_name")}"标签已于 {vu} 过期，请及时更新。',
                priority="normal",
            )
    if changed:
        _set_qualifications(ent, rows)
        db.session.commit()


def expire_all_overdue_labels() -> int:
    today = date.today()
    count = 0
    for ent in Enterprise.query.all():
        rows = _qualifications(ent)
        changed = False
        for row in rows:
            if row.get("label_type") not in KNOWN_LABEL_TYPES:
                continue
            if row.get("status") != "active":
                continue
            vu = _parse_date(row.get("valid_until"))
            if vu is not None and vu < today:
                row["status"] = "expired"
                changed = True
                count += 1
                _send_label_message(
                    enterprise_id=ent.id,
                    title="质量标签已过期",
                    content=f'您的"{row.get("label_name")}"标签已于 {vu} 过期，请及时更新。',
                )
        if changed:
            _set_qualifications(ent, rows)
    if count:
        db.session.commit()
    return count


def get_enterprise_label_types(enterprise_id: int) -> list[str]:
    _auto_expire_labels(enterprise_id)
    ent = Enterprise.query.get(enterprise_id)
    if not ent:
        return []
    today = date.today()
    types: set[str] = set()
    for row in _quality_rows(ent):
        if _is_active_label(row, today):
            lt = row.get("label_type")
            if lt:
                types.add(lt)
    return list(types)


def filter_enterprises_by_labels(
    enterprise_ids: list[int],
    label_types: list[str],
    require_all: bool = False,
) -> list[int]:
    if not label_types or not enterprise_ids:
        return enterprise_ids

    today = date.today()
    need = set(label_types)
    out: list[int] = []

    for eid in enterprise_ids:
        ent = Enterprise.query.get(eid)
        if not ent:
            continue
        active_types = set()
        for row in _quality_rows(ent):
            if row.get("label_type") in need and _is_active_label(row, today):
                active_types.add(row["label_type"])
        if require_all:
            if need <= active_types:
                out.append(eid)
        else:
            if active_types & need:
                out.append(eid)
    return out


def get_label_boost_score(enterprise_id: int) -> float:
    label_types = get_enterprise_label_types(enterprise_id)
    boost = 0.0
    if "government_green" in label_types:
        boost += 10.0
    if "lead_inspection" in label_types:
        boost += 8.0
    if "third_party" in label_types:
        boost += 5.0
    return boost


def _send_label_message(
    enterprise_id: int,
    title: str,
    content: str,
    link_url: str = "/quality-labels/manage",
    priority: str = "normal",
):
    msg = Message(
        recipient_id=enterprise_id,
        message_type="system",
        title=title,
        content=content,
        link_url=link_url,
        priority=priority,
    )
    db.session.add(msg)

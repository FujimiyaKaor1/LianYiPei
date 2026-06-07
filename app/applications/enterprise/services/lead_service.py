"""
链主企业管理服务（入驻申请、供应商展示控制 → Enterprise.extras JSON）
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

from app import db
from app.models import Enterprise

logger = logging.getLogger("app.ops")

# extras 键与 models.py 注释一致
KEY_LEAD_ONBOARDING = "lead_onboarding"
KEY_SUPPLIER_DISPLAY = "supplier_display"


def _extras_dict(ent: Enterprise) -> dict:
    e = ent.extras
    return dict(e) if isinstance(e, dict) else {}


def _save_extras(ent: Enterprise, data: dict) -> None:
    ent.extras = data
    db.session.add(ent)


def _onboarding_list(ent: Enterprise) -> list:
    ex = _extras_dict(ent)
    raw = ex.get(KEY_LEAD_ONBOARDING)
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _set_onboarding_list(ent: Enterprise, rows: list) -> None:
    ex = _extras_dict(ent)
    ex[KEY_LEAD_ONBOARDING] = rows
    _save_extras(ent, ex)


def _supplier_display_list(ent: Enterprise) -> list:
    ex = _extras_dict(ent)
    raw = ex.get(KEY_SUPPLIER_DISPLAY)
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


def _set_supplier_display_list(ent: Enterprise, rows: list) -> None:
    ex = _extras_dict(ent)
    ex[KEY_SUPPLIER_DISPLAY] = rows
    _save_extras(ent, ex)


def _next_id_from_rows(rows: list, key: str = "id") -> int:
    ids = [int(r.get(key) or 0) for r in rows]
    return max(ids, default=0) + 1


def _max_onboarding_id_globally() -> int:
    m = 0
    for ent in Enterprise.query.all():
        for app in _onboarding_list(ent):
            m = max(m, int(app.get("id") or 0))
    return m


class LeadEnterpriseService:
    """链主企业管理服务"""

    @staticmethod
    def get_pending_onboarding_application(enterprise_id: int) -> Optional[Dict]:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return None
        for app in _onboarding_list(ent):
            if app.get("status") == "pending":
                return app
        return None

    @staticmethod
    def submit_onboarding_application(enterprise_id: int, application_data: Dict) -> Dict:
        try:
            enterprise = Enterprise.query.get(enterprise_id)
            if not enterprise:
                return {"success": False, "message": "企业不存在"}

            if enterprise.is_lead_enterprise:
                return {"success": False, "message": "该企业已经是链主企业"}

            apps = _onboarding_list(enterprise)
            if any(a.get("status") == "pending" for a in apps):
                return {"success": False, "message": "已有待审核的申请，请等待审核结果"}

            new_id = _max_onboarding_id_globally() + 1
            app = {
                "id": new_id,
                "enterprise_id": enterprise_id,
                "qualification_docs": application_data.get("qualification_docs", ""),
                "supplier_management_system": application_data.get(
                    "supplier_management_system", ""
                ),
                "supplier_count": application_data.get("supplier_count", 0),
                "annual_procurement": application_data.get("annual_procurement", 0),
                "description": application_data.get("description", ""),
                "status": "pending",
                "submitted_at": datetime.now().isoformat(),
                "reviewed_by": None,
                "reviewed_at": None,
                "review_notes": "",
            }
            apps.append(app)
            _set_onboarding_list(enterprise, apps)
            db.session.commit()

            return {
                "success": True,
                "message": "申请已提交，等待管理员审核",
                "application_id": new_id,
            }

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"提交申请失败: {str(e)}"}

    @staticmethod
    def review_onboarding_application(
        application_id: int,
        reviewer_id: int,
        approved: bool,
        review_notes: str = "",
    ) -> Dict:
        try:
            application = None
            enterprise = None
            for ent in Enterprise.query.all():
                for app in _onboarding_list(ent):
                    if int(app.get("id") or 0) == int(application_id):
                        application = app
                        enterprise = ent
                        break
                if application:
                    break

            if not application:
                return {"success": False, "message": "申请不存在"}

            if application.get("status") != "pending":
                return {
                    "success": False,
                    "message": f'申请已{application.get("status")}，无法重复审核',
                }

            application["status"] = "approved" if approved else "rejected"
            application["reviewed_by"] = reviewer_id
            application["reviewed_at"] = datetime.now().isoformat()
            application["review_notes"] = review_notes

            if enterprise:
                _set_onboarding_list(enterprise, _onboarding_list(enterprise))

            if approved and enterprise:
                enterprise.is_lead_enterprise = True
                logger.info(
                    "lead_enterprise_approval enterprise_id=%s reviewer_id=%s result=success",
                    enterprise.id,
                    reviewer_id,
                )

            db.session.commit()

            return {
                "success": True,
                "message": "审核完成" if approved else "申请已拒绝",
            }

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"审核失败: {str(e)}"}

    @staticmethod
    def get_onboarding_applications(status: Optional[str] = None) -> List[Dict]:
        result: List[Dict] = []
        for ent in Enterprise.query.all():
            eid = ent.id
            for app in _onboarding_list(ent):
                if status and app.get("status") != status:
                    continue
                en = Enterprise.query.get(eid)
                result.append(
                    {
                        "id": app.get("id"),
                        "enterprise_id": eid,
                        "enterprise_name": en.name if en else "未知",
                        "supplier_count": app.get("supplier_count"),
                        "annual_procurement": app.get("annual_procurement"),
                        "description": app.get("description"),
                        "status": app.get("status"),
                        "submitted_at": _fmt_ts(app.get("submitted_at")),
                        "reviewed_at": _fmt_ts(app.get("reviewed_at")),
                        "review_notes": app.get("review_notes") or "",
                    }
                )

        result.sort(key=lambda x: str(x.get("submitted_at") or ""), reverse=True)
        return result

    @staticmethod
    def import_supplier_list(lead_enterprise_id: int, supplier_ids: List[int]) -> Dict:
        try:
            lead_enterprise = Enterprise.query.get(lead_enterprise_id)
            if not lead_enterprise or not lead_enterprise.is_lead_enterprise:
                return {"success": False, "message": "只有链主企业可以导入供应商名单"}

            imported_count = 0
            controls = _supplier_display_list(lead_enterprise)
            existing_pairs = {(c.get("lead_enterprise_id"), c.get("supplier_id")) for c in controls}

            for supplier_id in supplier_ids:
                supplier = Enterprise.query.get(supplier_id)
                if supplier and supplier.id != lead_enterprise_id:
                    key = (lead_enterprise_id, supplier_id)
                    if key not in existing_pairs:
                        new_id = _next_id_from_rows(controls)
                        controls.append(
                            {
                                "id": new_id,
                                "lead_enterprise_id": lead_enterprise_id,
                                "supplier_id": supplier_id,
                                "display_mode": "public",
                                "authorized": False,
                                "created_at": datetime.now().isoformat(),
                                "updated_at": None,
                                "authorized_at": None,
                            }
                        )
                        existing_pairs.add(key)
                        imported_count += 1

            _set_supplier_display_list(lead_enterprise, controls)
            db.session.commit()

            return {
                "success": True,
                "message": f"成功导入{imported_count}家供应商",
                "imported_count": imported_count,
            }

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"导入失败: {str(e)}"}

    @staticmethod
    def calculate_contribution(lead_enterprise_id: int) -> Dict:
        try:
            from app.services.quality_label_service import _qualifications

            inspection_count = 0
            for ent in Enterprise.query.all():
                for row in _qualifications(ent):
                    if row.get("label_type") != "lead_inspection":
                        continue
                    if row.get("status") != "active":
                        continue
                    if int(row.get("issuer_id") or 0) != lead_enterprise_id:
                        continue
                    inspection_count += 1

            lead = Enterprise.query.get(lead_enterprise_id)
            managed_supplier_count = 0
            if lead:
                managed_supplier_count = len(
                    [
                        c
                        for c in _supplier_display_list(lead)
                        if c.get("lead_enterprise_id") == lead_enterprise_id
                    ]
                )

            total_transaction_amount = inspection_count * 1000000.0

            return {
                "total_transaction_amount": total_transaction_amount,
                "inspection_count": inspection_count,
                "managed_supplier_count": managed_supplier_count,
            }

        except Exception:
            return {
                "total_transaction_amount": 0.0,
                "inspection_count": 0,
                "managed_supplier_count": 0,
            }

    @staticmethod
    def configure_supplier_display(
        lead_enterprise_id: int, supplier_id: int, display_mode: str
    ) -> Dict:
        try:
            lead_enterprise = Enterprise.query.get(lead_enterprise_id)
            if not lead_enterprise or not lead_enterprise.is_lead_enterprise:
                return {"success": False, "message": "只有链主企业可以配置展示控制"}

            if display_mode not in ("public", "lead_only", "hidden"):
                return {"success": False, "message": "无效的展示模式"}

            supplier = Enterprise.query.get(supplier_id)
            if not supplier:
                return {"success": False, "message": "供应商不存在"}

            controls = _supplier_display_list(lead_enterprise)
            control = None
            for c in controls:
                if c.get("lead_enterprise_id") == lead_enterprise_id and c.get(
                    "supplier_id"
                ) == supplier_id:
                    control = c
                    break

            if not control:
                new_id = _next_id_from_rows(controls)
                control = {
                    "id": new_id,
                    "lead_enterprise_id": lead_enterprise_id,
                    "supplier_id": supplier_id,
                    "display_mode": display_mode,
                    "authorized": False,
                    "created_at": datetime.now().isoformat(),
                    "updated_at": None,
                    "authorized_at": None,
                }
                controls.append(control)
            else:
                if not control.get("authorized") and display_mode != "public":
                    return {"success": False, "message": "供应商未授权，无法应用展示控制"}
                old_mode = control.get("display_mode")
                control["display_mode"] = display_mode
                control["updated_at"] = datetime.now().isoformat()
                logger.info(
                    "display_control_change lead_id=%s supplier_id=%s %s->%s",
                    lead_enterprise_id,
                    supplier_id,
                    old_mode,
                    display_mode,
                )

            _set_supplier_display_list(lead_enterprise, controls)
            db.session.commit()

            return {"success": True, "message": "展示控制配置成功"}

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"配置失败: {str(e)}"}

    @staticmethod
    def authorize_display_control(
        supplier_id: int, lead_enterprise_id: int, authorized: bool
    ) -> Dict:
        try:
            lead = Enterprise.query.get(lead_enterprise_id)
            if not lead:
                return {"success": False, "message": "链主企业不存在"}

            controls = _supplier_display_list(lead)
            control = None
            for c in controls:
                if c.get("lead_enterprise_id") == lead_enterprise_id and c.get(
                    "supplier_id"
                ) == supplier_id:
                    control = c
                    break

            if not control:
                return {"success": False, "message": "展示控制记录不存在"}

            control["authorized"] = authorized
            control["authorized_at"] = (
                datetime.now().isoformat() if authorized else None
            )
            control["updated_at"] = datetime.now().isoformat()
            if not authorized:
                control["display_mode"] = "public"

            logger.info(
                "display_control_authorization supplier_id=%s lead_id=%s authorized=%s",
                supplier_id,
                lead_enterprise_id,
                authorized,
            )

            _set_supplier_display_list(lead, controls)
            db.session.commit()

            return {
                "success": True,
                "message": "授权成功" if authorized else "授权已撤销",
            }

        except Exception as e:
            db.session.rollback()
            return {"success": False, "message": f"操作失败: {str(e)}"}

    @staticmethod
    def get_supplier_display_controls(lead_enterprise_id: int) -> List[Dict]:
        lead = Enterprise.query.get(lead_enterprise_id)
        if not lead:
            return []

        result: List[Dict] = []
        for control in _supplier_display_list(lead):
            if control.get("lead_enterprise_id") != lead_enterprise_id:
                continue
            supplier = Enterprise.query.get(control.get("supplier_id"))
            if supplier:
                result.append(
                    {
                        "id": control.get("id"),
                        "supplier_id": supplier.id,
                        "supplier_name": supplier.name,
                        "display_mode": control.get("display_mode"),
                        "authorized": control.get("authorized", False),
                        "authorized_at": _fmt_ts(control.get("authorized_at")),
                        "created_at": _fmt_ts(control.get("created_at")),
                        "updated_at": _fmt_ts(control.get("updated_at")),
                    }
                )
        return result

    @staticmethod
    def check_supplier_visibility(supplier_id: int, viewer_id: int) -> bool:
        for lead in Enterprise.query.all():
            for control in _supplier_display_list(lead):
                if control.get("supplier_id") != supplier_id:
                    continue
                if not control.get("authorized"):
                    continue
                mode = control.get("display_mode")
                if mode == "hidden":
                    return viewer_id == supplier_id
                if mode == "lead_only":
                    lid = control.get("lead_enterprise_id")
                    if viewer_id != supplier_id and viewer_id != lid:
                        return False
        return True


def _fmt_ts(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val[:19].replace("T", " ") if "T" in val else val
    if hasattr(val, "strftime"):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return str(val)

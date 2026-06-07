"""
数据授权：读写 Enterprise.data_auth JSON（dict[data_type -> 授权记录]）。
"""
from datetime import datetime
from typing import Dict, List, Optional

from app import db
from app.models import Enterprise
from app.services import credit_engine
from app.services.external_data_service import power_api_service, tax_api_service


class DataAuthorizationService:
    def __init__(self):
        pass

    def _auth_map(self, ent: Enterprise) -> Dict:
        m = ent.data_auth
        return dict(m) if isinstance(m, dict) else {}

    def _save_map(self, ent: Enterprise, m: Dict) -> None:
        ent.data_auth = m

    def authorize_data(self, enterprise_id: int, data_type: str) -> Dict:
        valid_types = ["power_consumption", "invoice_data"]
        if data_type not in valid_types:
            return {
                "success": False,
                "message": f'无效的数据类型。支持的类型: {", ".join(valid_types)}',
            }
        enterprise = Enterprise.query.get(enterprise_id)
        if not enterprise:
            return {"success": False, "message": "企业不存在"}

        m = self._auth_map(enterprise)
        existing = m.get(data_type)
        if existing and existing.get("authorized"):
            return {"success": False, "message": "该数据类型已授权"}

        if existing and not existing.get("authorized"):
            existing["authorized"] = True
            existing["authorized_at"] = datetime.utcnow().isoformat()
            existing["revoked_at"] = None
            existing["sync_status"] = "pending"
            existing["error_message"] = None
            m[data_type] = existing
            self._save_map(enterprise, m)
            db.session.commit()
            return {
                "success": True,
                "message": "数据授权已恢复",
                "authorization_id": existing.get("id"),
                "credit_bonus": 0,
            }

        new_id = max((v.get("id") or 0) for v in m.values() if isinstance(v, dict)) + 1 if m else 1
        m[data_type] = {
            "id": new_id,
            "authorized": True,
            "authorized_at": datetime.utcnow().isoformat(),
            "sync_status": "pending",
        }
        self._save_map(enterprise, m)
        old_score = enterprise.credit_score
        credit_engine.update_credit_score(
            enterprise_id=enterprise_id,
            change_type="data_authorization",
            change_value=10.0,
            reason=f"授权{self._get_data_type_name(data_type)}数据",
        )
        db.session.commit()
        self._sync_data(enterprise_id, data_type)
        return {
            "success": True,
            "message": "数据授权成功",
            "authorization_id": new_id,
            "credit_bonus": 10.0,
            "old_score": old_score,
            "new_score": enterprise.credit_score,
        }

    def revoke_authorization(self, authorization_id: int, enterprise_id: int) -> Dict:
        enterprise = Enterprise.query.get(enterprise_id)
        if not enterprise:
            return {"success": False, "message": "企业不存在"}
        m = self._auth_map(enterprise)
        found = None
        for dt, rec in m.items():
            if isinstance(rec, dict) and rec.get("id") == authorization_id:
                found = dt
                break
        if not found:
            return {"success": False, "message": "授权记录不存在"}
        rec = m[found]
        if not rec.get("authorized"):
            return {"success": False, "message": "该授权已撤销"}
        rec["authorized"] = False
        rec["revoked_at"] = datetime.utcnow().isoformat()
        m[found] = rec
        self._save_map(enterprise, m)
        db.session.commit()
        return {
            "success": True,
            "message": "授权已撤销，历史数据已保留，不扣除已获得的信用分",
        }

    def get_authorizations(self, enterprise_id: int) -> List[Dict]:
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return []
        m = self._auth_map(ent)
        result = []
        for data_type, auth in m.items():
            if not isinstance(auth, dict):
                continue
            result.append(
                {
                    "id": auth.get("id"),
                    "data_type": data_type,
                    "data_type_name": self._get_data_type_name(data_type),
                    "authorized": auth.get("authorized"),
                    "authorized_at": auth.get("authorized_at"),
                    "revoked_at": auth.get("revoked_at"),
                    "last_sync_at": auth.get("last_sync_at"),
                    "sync_status": auth.get("sync_status"),
                    "sync_status_name": self._get_sync_status_name(auth.get("sync_status")),
                    "error_message": auth.get("error_message"),
                }
            )
        return result

    def sync_all_authorized_data(self) -> Dict:
        success_count = 0
        failed_count = 0
        total = 0
        for ent in Enterprise.query.all():
            m = self._auth_map(ent)
            for data_type, rec in m.items():
                if not isinstance(rec, dict) or not rec.get("authorized"):
                    continue
                total += 1
                r = self._sync_data(ent.id, data_type)
                if r.get("success"):
                    success_count += 1
                else:
                    failed_count += 1
        return {"total": total, "success": success_count, "failed": failed_count}

    def _sync_data(self, enterprise_id: int, data_type: str, retry_count: int = 0) -> Dict:
        max_retries = 3
        ent = Enterprise.query.get(enterprise_id)
        if not ent:
            return {"success": False, "error": "企业不存在"}
        m = self._auth_map(ent)
        rec = m.get(data_type)
        if not isinstance(rec, dict):
            return {"success": False, "error": "无授权记录"}

        try:
            if data_type == "power_consumption":
                data = self._fetch_power_consumption_data(enterprise_id)
            elif data_type == "invoice_data":
                data = self._fetch_invoice_data(enterprise_id)
            else:
                raise ValueError(f"未知的数据类型: {data_type}")
            rec["last_sync_at"] = datetime.utcnow().isoformat()
            rec["sync_status"] = "success"
            rec["error_message"] = None
            m[data_type] = rec
            self._save_map(ent, m)
            db.session.commit()
            return {"success": True, "data": data}
        except Exception as e:
            error_msg = str(e)
            if retry_count < max_retries:
                return self._sync_data(enterprise_id, data_type, retry_count + 1)
            rec["sync_status"] = "failed"
            rec["error_message"] = f"同步失败（重试{max_retries}次）: {error_msg}"
            m[data_type] = rec
            self._save_map(ent, m)
            db.session.commit()
            return {"success": False, "error": error_msg}

    def _fetch_power_consumption_data(self, enterprise_id: int) -> Dict:
        return power_api_service.fetch_power_consumption(enterprise_id)

    def _fetch_invoice_data(self, enterprise_id: int) -> Dict:
        return tax_api_service.fetch_invoice_data(enterprise_id)

    def _get_data_type_name(self, data_type: str) -> str:
        names = {"power_consumption": "用电量数据", "invoice_data": "开票数据"}
        return names.get(data_type, data_type)

    def _get_sync_status_name(self, sync_status: Optional[str]) -> str:
        if not sync_status:
            return "未同步"
        names = {"success": "同步成功", "failed": "同步失败", "pending": "等待同步"}
        return names.get(sync_status, sync_status)

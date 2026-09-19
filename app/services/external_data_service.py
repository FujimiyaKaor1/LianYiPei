"""
外部数据接口服务（配置来自 config.EXTERNAL_INTERFACES + 进程内内存状态；工商缓存为内存 TTL）。
"""
from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

import requests
from flask import current_app

from app import db
from app.models import Alert, Enterprise

logger = logging.getLogger(__name__)

# query_key -> (expires_at, result_data)
_industrial_memory_cache: Dict[str, Tuple[datetime, List[Dict]]] = {}
_interface_runtime_state: Optional[Dict[str, Dict[str, Any]]] = None


class ExternalDataUnavailable(RuntimeError):
    """A configured real source is unavailable; callers must not invent facts."""


def _evidence(source: str, source_url: str = "") -> Dict[str, Any]:
    now = datetime.utcnow().isoformat() + "Z"
    return {
        "source": source,
        "source_url": source_url,
        "collected_at": now,
        "updated_at": now,
        "is_mock": False,
        "confidence": 1.0,
        "authorization": "configured_external_interface",
    }


def _state() -> Dict[str, Dict[str, Any]]:
    global _interface_runtime_state
    if _interface_runtime_state is None:
        from config import EXTERNAL_INTERFACES

        _interface_runtime_state = copy.deepcopy(EXTERNAL_INTERFACES)
    return _interface_runtime_state


def _cfg_ns(interface_type: str) -> Optional[SimpleNamespace]:
    raw = _state().get(interface_type)
    if not raw:
        return None
    return SimpleNamespace(**raw)


def _dict_for_api(cfg: SimpleNamespace) -> Dict[str, Any]:
    return {k: v for k, v in vars(cfg).items()}


# ============================================================
# 基础 HTTP 客户端
# ============================================================


class ExternalAPIClient:
    """外部 API 客户端；config 为 SimpleNamespace（与旧 ORM 字段一致）。"""

    def __init__(self, config: SimpleNamespace):
        self.config = config
        self._validate_base_url()
        self._oauth_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    def _validate_base_url(self) -> None:
        """Reject malformed or unsafe credential destinations.

        Configured registry/tax/power providers are trusted only after their
        origin is validated. Production requires HTTPS; URL userinfo,
        queries and fragments are rejected so secrets cannot be redirected or
        accidentally exposed to an unapproved endpoint.
        """
        raw = str(getattr(self.config, "base_url", "") or "").strip()
        parsed = urlsplit(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ExternalDataUnavailable("外部数据接口 URL 配置无效")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ExternalDataUnavailable("外部数据接口 URL 不得包含凭据或查询参数")
        try:
            environment = str(current_app.config.get("APP_ENV") or os.getenv("APP_ENV") or "development").lower()
        except RuntimeError:
            environment = str(os.getenv("APP_ENV") or "development").lower()
        if environment == "production" and parsed.scheme != "https":
            raise ExternalDataUnavailable("生产环境外部数据接口 URL 必须使用 HTTPS")

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.config.auth_type == "api_key" and getattr(self.config, "api_key", None):
            headers["X-API-Key"] = self.config.api_key
        elif self.config.auth_type == "oauth2":
            token = self._get_oauth_token()
            if token:
                headers["Authorization"] = f"Bearer {token}"
        return headers

    def _get_oauth_token(self) -> Optional[str]:
        if (
            self._oauth_token
            and self._token_expires_at
            and datetime.utcnow() < self._token_expires_at
        ):
            return self._oauth_token

        if not self.config.client_id or not self.config.client_secret:
            logger.warning(f"[{self.config.interface_type}] OAuth2缺少client_id或client_secret")
            return None

        token_url = f"{self.config.base_url}/oauth/token"
        try:
            resp = requests.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                },
                timeout=self.config.timeout_seconds,
            )
            resp.raise_for_status()
            data = resp.json()
            self._oauth_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)
            self._token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 60)
            return self._oauth_token
        except Exception as e:
            logger.error(f"[{self.config.interface_type}] OAuth2获取令牌失败: {e}")
            return None

    def get(self, path: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, data: Optional[Dict] = None) -> Dict:
        return self._request("POST", path, json_data=data)

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
    ) -> Dict:
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self._get_headers(),
                    params=params,
                    json=json_data,
                    timeout=self.config.timeout_seconds,
                )
                resp.raise_for_status()
                return resp.json()
            except requests.Timeout:
                last_error = f"请求超时（{self.config.timeout_seconds}s）"
                logger.warning(f"[{self.config.interface_type}] 第{attempt+1}次请求超时: {url}")
            except requests.HTTPError as e:
                last_error = f"HTTP错误: {e.response.status_code}"
                logger.warning(
                    f"[{self.config.interface_type}] HTTP错误 {e.response.status_code}: {url}"
                )
                if e.response.status_code < 500:
                    break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[{self.config.interface_type}] 第{attempt+1}次请求失败: {e}")

            if attempt < self.config.max_retries - 1:
                time.sleep(2**attempt)

        raise RuntimeError(f"接口调用失败（重试{self.config.max_retries}次）: {last_error}")


# ============================================================
# 电力 / 税务 / 工商
# ============================================================


class PowerAPIService:
    INTERFACE_TYPE = "power_api"

    def get_config(self) -> Optional[SimpleNamespace]:
        return _cfg_ns(self.INTERFACE_TYPE)

    def fetch_power_consumption(self, enterprise_id: int) -> Dict:
        config = self.get_config()
        if not config or not config.is_enabled:
            raise ExternalDataUnavailable("电力数据接口未配置，禁止使用模拟用电数据")

        enterprise = Enterprise.query.get(enterprise_id)
        if not enterprise:
            raise ValueError(f"企业不存在: {enterprise_id}")

        client = ExternalAPIClient(config)
        raw = client.get(
            "/consumption/monthly",
            params={"enterprise_name": enterprise.name, "months": 12},
        )

        mapping = getattr(config, "field_mapping", None)
        result = self._map_power_data(raw, mapping, enterprise_id)
        result.update(_evidence(self.INTERFACE_TYPE, config.base_url))
        return result

    def _map_power_data(
        self, raw: Dict, mapping: Optional[Dict], enterprise_id: int
    ) -> Dict:
        if not mapping:
            return {
                "enterprise_id": enterprise_id,
                "data_type": "power_consumption",
                "period": "last_12_months",
                "data": raw.get("monthly_data", []),
                "total_consumption": raw.get("total", 0),
            }
        data_key = mapping.get("data_list", "monthly_data")
        total_key = mapping.get("total", "total")
        return {
            "enterprise_id": enterprise_id,
            "data_type": "power_consumption",
            "period": "last_12_months",
            "data": raw.get(data_key, []),
            "total_consumption": raw.get(total_key, 0),
        }

class TaxAPIService:
    INTERFACE_TYPE = "tax_api"

    def get_config(self) -> Optional[SimpleNamespace]:
        return _cfg_ns(self.INTERFACE_TYPE)

    def fetch_invoice_data(self, enterprise_id: int) -> Dict:
        config = self.get_config()
        if not config or not config.is_enabled:
            raise ExternalDataUnavailable("税务数据接口未配置，禁止使用模拟开票数据")

        enterprise = Enterprise.query.get(enterprise_id)
        if not enterprise:
            raise ValueError(f"企业不存在: {enterprise_id}")

        client = ExternalAPIClient(config)
        raw = client.get(
            "/invoice/monthly",
            params={"enterprise_name": enterprise.name, "months": 12},
        )

        mapping = getattr(config, "field_mapping", None)
        result = self._map_invoice_data(raw, mapping, enterprise_id)
        result.update(_evidence(self.INTERFACE_TYPE, config.base_url))
        return result

    def _map_invoice_data(
        self, raw: Dict, mapping: Optional[Dict], enterprise_id: int
    ) -> Dict:
        if not mapping:
            return {
                "enterprise_id": enterprise_id,
                "data_type": "invoice_data",
                "period": "last_12_months",
                "data": raw.get("monthly_data", []),
                "total_amount": raw.get("total_amount", 0),
                "total_invoices": raw.get("total_count", 0),
            }
        data_key = mapping.get("data_list", "monthly_data")
        amount_key = mapping.get("total_amount", "total_amount")
        count_key = mapping.get("total_count", "total_count")
        return {
            "enterprise_id": enterprise_id,
            "data_type": "invoice_data",
            "period": "last_12_months",
            "data": raw.get(data_key, []),
            "total_amount": raw.get(amount_key, 0),
            "total_invoices": raw.get(count_key, 0),
        }

class IndustrialCommerceService:
    INTERFACE_TYPE = "industrial_commerce_api"
    CACHE_TTL_HOURS = 24

    def get_config(self) -> Optional[SimpleNamespace]:
        return _cfg_ns(self.INTERFACE_TYPE)

    def query_enterprises(
        self, keyword: str, filters: Optional[Dict] = None
    ) -> List[Dict]:
        config = self.get_config()
        if not config or not config.is_enabled or not getattr(config, "base_url", ""):
            raise ExternalDataUnavailable("工商数据接口未配置，禁止生成模拟候选企业")

        cache_key = self._build_cache_key(keyword, filters)

        hit = _industrial_memory_cache.get(cache_key)
        if hit:
            expires_at, data = hit
            if datetime.utcnow() < expires_at:
                logger.debug(f"[工商API] 命中内存缓存: {cache_key}")
                return data

        try:
            client = ExternalAPIClient(config)
            params = {"keyword": keyword, "page_size": 20}
            if filters:
                params.update(filters)
            raw = client.get("/enterprise/search", params=params)
            mapping = getattr(config, "field_mapping", None)
            result = self._map_enterprise_data(raw, mapping, config.base_url)
        except ExternalDataUnavailable:
            raise
        except Exception as e:
            logger.error(f"[工商API] 查询失败: {e}")
            raise ExternalDataUnavailable("工商数据接口查询失败，未返回候选企业") from e

        expires = datetime.utcnow() + timedelta(hours=self.CACHE_TTL_HOURS)
        _industrial_memory_cache[cache_key] = (expires, result)
        return result

    def _build_cache_key(self, keyword: str, filters: Optional[Dict]) -> str:
        raw = f"{keyword}:{json.dumps(filters or {}, sort_keys=True)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _map_enterprise_data(
        self, raw: Dict, mapping: Optional[Dict], source_url: str = ""
    ) -> List[Dict]:
        if not mapping:
            items = raw.get("data", raw.get("list", []))
        else:
            items = raw.get(mapping.get("data_list", "data"), [])

        result = []
        for item in items:
            mapped = {
                    "name": item.get("name", ""),
                    "location": item.get("address", item.get("location", "")),
                    "business_scope": item.get("business_scope", ""),
                    "registered_capital": item.get("registered_capital", ""),
                    "patent_count": item.get("patent_count", 0),
                    "credit_rating": item.get("credit_rating", ""),
                    # Public registry results are candidate facts only. Private
                    # contacts require a separate enterprise claim/authorization.
                    "contact": "",
                    "contact_authorized": False,
            }
            mapped.update(_evidence(self.INTERFACE_TYPE, source_url))
            result.append(mapped)
        return result

    def check_enterprise_status(self, enterprise_name: str) -> Dict:
        """
        查询企业工商状态（存续/注销/吊销等）
        
        Args:
            enterprise_name: 企业名称
            
        Returns:
            Dict包含:
                - name: 企业名称
                - status: 存续/注销/吊销/清算
                - is_active: 是否正常经营
                - check_date: 检查时间
                - is_mock: 是否为模拟数据
        """
        config = self.get_config()
        if not config or not config.is_enabled or not getattr(config, "base_url", ""):
            raise ExternalDataUnavailable("工商状态接口未配置，禁止随机生成企业经营状态")
        
        try:
            client = ExternalAPIClient(config)
            # 调用企业状态查询接口
            params = {"name": enterprise_name}
            raw = client.get("/enterprise/status", params=params)
            
            # 映射结果
            mapping = getattr(config, "field_mapping", None)
            return self._map_enterprise_status(raw, mapping, enterprise_name)
            
        except Exception as e:
            logger.error(f"[工商API] 企业状态查询失败: {e}")
            raise ExternalDataUnavailable("工商状态查询失败，企业状态保持不变") from e

    def _map_enterprise_status(self, raw: Dict, mapping: Optional[Dict], enterprise_name: str) -> Dict:
        """映射企业状态数据"""
        status_key = "status" if not mapping else mapping.get("status", "status")
        status_field = raw.get(status_key)
        if status_field in (None, ""):
            raise ExternalDataUnavailable("工商状态接口响应缺少状态字段")
        
        # 状态映射：有些API返回英文或数字
        status_map = {
            "存续": "存续",
            "在业": "存续",
            "active": "存续",
            "1": "存续",
            "注销": "注销",
            "注销备案": "注销",
            "cancelled": "注销",
            "2": "注销",
            "吊销": "吊销",
            "revoked": "吊销",
            "3": "吊销",
            "清算": "清算",
            "clearing": "清算",
            "4": "清算",
        }
        
        mapped_status = status_map.get(str(status_field))
        if mapped_status is None:
            raise ExternalDataUnavailable("工商状态接口返回了未知状态")
        is_active = mapped_status == "存续"
        
        result = {
            "name": enterprise_name,
            "status": mapped_status,
            "is_active": is_active,
            "check_date": datetime.utcnow().isoformat(),
            "is_mock": False,
            "raw_data": raw,
        }
        config = self.get_config()
        result.update(_evidence(self.INTERFACE_TYPE, getattr(config, "base_url", "")))
        return result


def _config_to_dict(cfg: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(cfg)
    lat = out.get("last_check_at")
    if hasattr(lat, "isoformat"):
        out["last_check_at"] = lat.isoformat()
    return out


class ExternalInterfaceManager:
    def ensure_default_configs(self) -> None:
        _state()

    def get_all_configs(self) -> List[Dict]:
        self.ensure_default_configs()
        return [_config_to_dict(v) for v in _state().values()]

    def get_config(self, interface_type: str) -> Optional[Dict]:
        cfg = _state().get(interface_type)
        return _config_to_dict(cfg) if cfg else None

    def update_config(self, interface_type: str, data: Dict) -> Dict:
        st = _state()
        if interface_type not in st:
            return {"success": False, "message": "接口配置不存在"}

        allowed = [
            "base_url",
            "auth_type",
            "api_key",
            "client_id",
            "client_secret",
            "timeout_seconds",
            "max_retries",
            "field_mapping",
            "is_enabled",
        ]
        for field in allowed:
            if field in data:
                st[interface_type][field] = data[field]
        return {"success": True, "message": "配置已更新"}

    def check_interface_availability(self, interface_type: str) -> Dict:
        st = _state()
        cfg_dict = st.get(interface_type)
        if not cfg_dict:
            return {"success": False, "status": "error", "message": "接口配置不存在"}

        cfg_ns = SimpleNamespace(**cfg_dict)
        if not cfg_ns.base_url:
            cfg_dict["last_check_status"] = "unknown"
            cfg_dict["last_check_at"] = datetime.utcnow()
            cfg_dict["last_check_error"] = "未配置接口地址"
            return {"success": False, "status": "unknown", "message": "未配置接口地址"}

        try:
            client = ExternalAPIClient(cfg_ns)
            health_path = "/health"
            resp = requests.get(
                f"{cfg_ns.base_url.rstrip('/')}{health_path}",
                headers=client._get_headers(),
                timeout=cfg_ns.timeout_seconds,
            )
            is_ok = resp.status_code < 400
            status = "ok" if is_ok else "error"
            error_msg = None if is_ok else f"HTTP {resp.status_code}"
        except requests.Timeout:
            status = "error"
            error_msg = f"连接超时（{cfg_ns.timeout_seconds}s）"
        except Exception as e:
            status = "error"
            error_msg = str(e)

        cfg_dict["last_check_status"] = status
        cfg_dict["last_check_at"] = datetime.utcnow()
        cfg_dict["last_check_error"] = error_msg

        if status == "error":
            self._trigger_interface_alert(cfg_dict, error_msg)

        return {
            "success": status == "ok",
            "status": status,
            "message": error_msg or "接口正常",
            "checked_at": cfg_dict["last_check_at"].isoformat(),
        }

    def check_all_interfaces(self) -> List[Dict]:
        results = []
        for interface_type, row in _state().items():
            if not row.get("is_enabled"):
                continue
            r = self.check_interface_availability(interface_type)
            r["interface_type"] = interface_type
            r["interface_name"] = row.get("interface_name", interface_type)
            results.append(r)
        return results

    def _trigger_interface_alert(self, cfg_dict: Dict, error: Optional[str]) -> None:
        try:
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            name = cfg_dict.get("interface_name", "")
            existing = Alert.query.filter(
                Alert.alert_type == "interface_unavailable",
                Alert.product_name == name,
                Alert.created_at >= one_hour_ago,
            ).first()
            if existing:
                return

            alert = Alert(
                product_name=name,
                message=f"外部接口不可用: {name}。错误: {error}",
                level="yellow",
                dimension="system",
                alert_type="interface_unavailable",
                severity_score=0.6,
            )
            db.session.add(alert)
            db.session.commit()
            logger.warning(f"[接口监控] 已创建接口不可用预警: {name}")
        except Exception as e:
            db.session.rollback()
            logger.error(f"[接口监控] 创建预警失败: {e}")


power_api_service = PowerAPIService()
tax_api_service = TaxAPIService()
industrial_commerce_service = IndustrialCommerceService()
interface_manager = ExternalInterfaceManager()

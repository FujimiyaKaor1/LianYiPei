"""
高德地图 Web 服务 + geopy 地理计算。

- 后端 REST 使用环境变量 AMAP_SERVICE_KEY（未设置时回退 AMAP_KEY）。
- 前端密钥由 Flask 通过 AMAP_JS_KEY / AMAP_SECURITY_JS_CODE 注入模板，不在此模块硬编码。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

import requests
from geopy.distance import geodesic

logger = logging.getLogger(__name__)

DEFAULT_LNG = 116.397428
DEFAULT_LAT = 39.90923

GEOCODE_URL = "https://restapi.amap.com/v3/geocode/geo"
DISTANCE_URL = "https://restapi.amap.com/v3/distance"

# 地理编码连通性探测用固定地址（高德示例常用地址，无敏感信息）
_TEST_GEOCODE_ADDRESS = "北京市东城区天安门广场"


class MapService:
    """
    高德 Web 服务封装：在实例上持有 service_key，便于测试与依赖注入。
    """

    def __init__(self, service_key: Optional[str] = None) -> None:
        raw = service_key if service_key is not None else os.environ.get("AMAP_SERVICE_KEY")
        fallback = os.environ.get("AMAP_KEY")
        self.service_key = (raw or fallback or "").strip()

    def test_connection(self) -> Dict[str, Any]:
        """
        调用地理编码接口做一次轻量请求，验证 Web 服务 Key 是否可用。
        不记录、不返回密钥明文。
        """
        if not self.service_key:
            logger.warning("MapService.test_connection: AMAP_SERVICE_KEY (or AMAP_KEY) missing")
            return {"ok": False, "error": "missing_service_key", "hint": "配置 AMAP_SERVICE_KEY 或兼容项 AMAP_KEY"}

        params = {"key": self.service_key, "address": _TEST_GEOCODE_ADDRESS}
        try:
            resp = requests.get(GEOCODE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            logger.exception("MapService.test_connection: HTTP error")
            return {"ok": False, "error": "http_error", "detail": str(e)}
        except ValueError as e:
            return {"ok": False, "error": "invalid_json", "detail": str(e)}

        status = str(data.get("status", ""))
        info = data.get("info")
        if status == "1" and data.get("geocodes"):
            return {
                "ok": True,
                "status": status,
                "info": info,
                "sample_count": len(data.get("geocodes") or []),
            }
        return {
            "ok": False,
            "status": status,
            "info": info,
            "error": "geocode_rejected",
        }

    def geocode(self, address: str, city: Optional[str] = None) -> Tuple[float, float]:
        """地理编码，返回 (lng, lat)。"""
        return _geocode_with_key(self.service_key, address, city)


# 进程内默认实例（也可在测试中替换）
_default_service: Optional[MapService] = None


def get_map_service() -> MapService:
    global _default_service
    if _default_service is None:
        _default_service = MapService()
    return _default_service


def _geocode_with_key(key: str, address: str, city: Optional[str] = None) -> Tuple[float, float]:
    addr = (address or "").strip()
    if not addr:
        logger.warning("geocode: empty address, use default")
        return DEFAULT_LNG, DEFAULT_LAT

    if not key:
        logger.warning("geocode: service key missing, use default")
        return DEFAULT_LNG, DEFAULT_LAT

    params: Dict[str, Any] = {"key": key, "address": addr}
    if city:
        params["city"] = city

    try:
        resp = requests.get(GEOCODE_URL, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.exception("geocode: request failed: %s", e)
        return DEFAULT_LNG, DEFAULT_LAT

    if str(data.get("status")) != "1" or not data.get("geocodes"):
        logger.warning("geocode: error info=%s", data.get("info"))
        return DEFAULT_LNG, DEFAULT_LAT

    loc = data["geocodes"][0].get("location") or ""
    parts = loc.split(",")
    if len(parts) != 2:
        return DEFAULT_LNG, DEFAULT_LAT
    try:
        lng, lat = float(parts[0]), float(parts[1])
        return lng, lat
    except (TypeError, ValueError):
        return DEFAULT_LNG, DEFAULT_LAT


def get_coords(address: str, city: Optional[str] = None) -> Tuple[float, float]:
    """模块级便捷方法：使用默认 MapService 的 Web Key。"""
    return get_map_service().geocode(address, city)


def calculate_distance(
    coord1: Dict[str, float],
    coord2: Dict[str, float],
    mode: str = "straight",
) -> Dict[str, Any]:
    try:
        lng1, lat1 = float(coord1["longitude"]), float(coord1["latitude"])
        lng2, lat2 = float(coord2["longitude"]), float(coord2["latitude"])
    except (KeyError, TypeError, ValueError) as e:
        raise ValueError("坐标格式应为 {longitude, latitude} 数字") from e

    key = get_map_service().service_key

    if mode == "driving":
        d = _amap_driving_distance_meters(key, lng1, lat1, lng2, lat2)
        if d is not None:
            return {"meters": round(d, 2), "mode": "driving", "source": "amap"}
        logger.warning("calculate_distance: driving API failed, fallback geodesic")

    dist_m = geodesic((lat1, lng1), (lat2, lng2)).meters
    return {"meters": round(dist_m, 2), "mode": "straight", "source": "geopy"}


def _amap_driving_distance_meters(
    key: str,
    lng1: float,
    lat1: float,
    lng2: float,
    lat2: float,
) -> Optional[float]:
    if not key:
        return None
    origins = f"{lng1},{lat1}"
    destination = f"{lng2},{lat2}"
    try:
        resp = requests.get(
            DISTANCE_URL,
            params={
                "key": key,
                "origins": origins,
                "destination": destination,
                "type": "1",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.exception("amap distance: %s", e)
        return None

    if str(data.get("status")) != "1":
        return None
    results = data.get("results")
    if not results:
        return None
    try:
        return float(results[0].get("distance", 0))
    except (TypeError, ValueError):
        return None


def resolve_enterprise_coords(
    address: Optional[str],
    longitude: Optional[float],
    latitude: Optional[float],
    province: Optional[str] = None,
) -> Tuple[float, float, str]:
    if longitude is not None and latitude is not None:
        try:
            return float(longitude), float(latitude), "database"
        except (TypeError, ValueError):
            pass

    city_hint = (province or "").strip() or None
    if address and address.strip():
        lng, lat = get_coords(address.strip(), city=city_hint)
        if (lng, lat) != (DEFAULT_LNG, DEFAULT_LAT):
            return lng, lat, "geocode"
        if city_hint:
            lng, lat = get_coords(address.strip(), city=None)
            if (lng, lat) != (DEFAULT_LNG, DEFAULT_LAT):
                return lng, lat, "geocode"
        return lng, lat, "default"

    return DEFAULT_LNG, DEFAULT_LAT, "default"

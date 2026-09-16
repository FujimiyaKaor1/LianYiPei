#!/usr/bin/env python3
"""Make Tianxia Gongchang imports usable by the platform UI.

The source search result contains useful company facts but not the platform's
operational fields.  This script fills those fields deterministically and
creates display products, while marking generated values in ``extras``.
It only touches enterprises whose ``extras.source`` is Tianxia Gongchang.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app import create_app, db
from app.models import Enterprise, Product

DEFAULT_CSV = ROOT / "data/external/tianxiagongchang/tianxiagongchang_companies_platform.csv"
DEFAULT_RAW = ROOT / "data/external/tianxiagongchang/tianxiagongchang_raw_pages.json"
IMAGE_PATH = "/static/frontend/logo.png"

INDUSTRY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("电子", "PCB", "电路板", "芯片", "通信", "连接器"), "C39"),
    (("汽车", "摩托车", "车载", "车辆"), "C36"),
    (("医用", "医疗", "器械", "康复"), "C35"),
    (("纺织", "服装", "毛衫", "面料", "无纺"), "C17"),
    (("化工", "涂料", "胶粘", "新材料"), "C26"),
    (("家具", "木材", "家居"), "C21"),
    (("五金", "金属", "模具", "钣金", "冲压", "铝", "钢材"), "C33"),
    (("机械", "机床", "自动化", "机器人", "泵", "阀", "轴承"), "C34"),
    (("塑料", "橡胶", "注塑", "吸塑", "硅胶"), "C29"),
)

PRODUCT_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("电子", "PCB", "电路板", "芯片"), ("电子组件", "PCB电路板", "电子产品组装", "连接器组件")),
    (("汽车", "车载", "车辆"), ("汽车零部件", "汽车电子组件", "精密汽车配件", "车用结构件")),
    (("五金", "金属", "模具", "冲压"), ("精密五金件", "金属冲压件", "五金模具", "金属零部件")),
    (("机械", "机床", "自动化", "机器人"), ("自动化设备", "机械零部件", "工业设备组件", "工装夹具")),
    (("塑料", "橡胶", "注塑", "吸塑"), ("注塑件", "塑料制品", "橡胶密封件", "塑胶外壳")),
    (("纺织", "服装", "面料", "毛衫"), ("功能性面料", "服装加工", "针织产品", "纺织辅料")),
)

REGION_COORDS = {
    "北京": (116.4074, 39.9042), "上海": (121.4737, 31.2304), "天津": (117.2000, 39.1333),
    "重庆": (106.5516, 29.5630), "广东": (113.2665, 23.1322), "江苏": (118.7632, 32.0617),
    "浙江": (120.1536, 30.2655), "山东": (117.1201, 36.6512), "福建": (119.2965, 26.0745),
    "四川": (104.0665, 30.5723), "湖北": (114.3055, 30.5928), "湖南": (112.9388, 28.2282),
    "河南": (113.6254, 34.7466), "河北": (114.5149, 38.0428), "安徽": (117.2272, 31.8206),
    "江西": (115.8582, 28.6829), "陕西": (108.9398, 34.3416), "辽宁": (123.4315, 41.8057),
    "吉林": (125.3235, 43.8171), "黑龙江": (126.6424, 45.7560), "广西": (108.3669, 22.8170),
    "云南": (102.8329, 24.8801), "贵州": (106.6302, 26.6477), "山西": (112.5489, 37.8706),
    "甘肃": (103.8343, 36.0611), "海南": (110.3312, 20.0311), "内蒙古": (111.7656, 40.8175),
    "新疆": (87.6168, 43.8256), "西藏": (91.1409, 29.6456), "宁夏": (106.2309, 38.4872),
    "青海": (101.7782, 36.6171), "香港": (114.1694, 22.3193), "澳门": (113.5439, 22.1987),
}


def _stable_int(key: Any, low: int, high: int) -> int:
    digest = hashlib.sha256(str(key).encode("utf-8")).digest()
    return low + int.from_bytes(digest[:8], "big") % (high - low + 1)


def _text(value: Any) -> str:
    return str(value or "").strip()


def classify_industry_code(industries: str, scope: str) -> str:
    text = f"{industries},{scope}".upper()
    for keywords, code in INDUSTRY_RULES:
        if any(keyword.upper() in text for keyword in keywords):
            return code
    return "C34"


def build_demo_metrics(source_id: Any, keywords: str) -> dict[str, Any]:
    seed = f"{source_id}:{keywords}"
    capacity = _stable_int(seed + ":capacity", 30, 95)
    max_capacity = capacity + _stable_int(seed + ":max", 20, 100)
    return {
        "capacity": capacity,
        "max_capacity": max_capacity,
        "current_orders": _stable_int(seed + ":orders", 0, max(0, int(max_capacity * 0.7))),
        "credit_score": round(_stable_int(seed + ":credit", 70, 96) + 0.1 * (capacity % 10), 1),
        "data_freshness_score": float(_stable_int(seed + ":fresh", 82, 100)),
        "patent_count": _stable_int(seed + ":patents", 0, 12),
        "rd_investment": round(_stable_int(seed + ":rd", 10, 180) / 10, 1),
    }


def build_product_names(keywords: str, industry_code: str, source_id: Any) -> list[str]:
    text = keywords or ""
    pool = next((names for words, names in PRODUCT_RULES if any(w.upper() in text.upper() for w in words)), None)
    if pool is None:
        pool = ("工业零部件", "定制加工服务", "制造业配套产品", "工装夹具")
    count = _stable_int(f"{source_id}:{industry_code}:products", 2, min(4, len(pool)))
    start = _stable_int(f"{source_id}:product-start", 0, len(pool) - 1)
    return [pool[(start + offset) % len(pool)] for offset in range(count)]


def build_demo_coordinates(province: str, city: str, source_id: Any) -> tuple[float, float]:
    """Return stable display coordinates near the province/city center."""
    region = next((name for name in REGION_COORDS if name in (province or "") or name in (city or "")), "北京")
    base_lng, base_lat = REGION_COORDS[region]
    lng_offset = (_stable_int(f"{source_id}:lng", -40, 40) / 1000) if source_id else 0.0
    lat_offset = (_stable_int(f"{source_id}:lat", -30, 30) / 1000) if source_id else 0.0
    return round(base_lng + lng_offset, 6), round(base_lat + lat_offset, 6)


def merge_source_extras(existing: dict[str, Any] | None, raw: dict[str, Any]) -> dict[str, Any]:
    extras = dict(existing or {})
    extras["source_flags"] = {
        "is_foreign_trade": raw.get("isForeignTrade") in (1, 2, True, "1", "2"),
        "is_specialized": bool(raw.get("isSpecialized")),
        "is_single_champion": bool(raw.get("isSingleChampion")),
        "is_high_tech": bool(raw.get("isHighTech")),
        "is_env_label": bool(raw.get("isEnvLabel")),
        "exported": bool(raw.get("exported")),
    }
    extras["platform_enrichment"] = "tianxiagongchang_functional_v1"
    extras["data_quality"] = "demo_enriched"
    extras["synthetic_fields"] = sorted(
        set(extras.get("synthetic_fields", []))
        | {
            "capacity", "max_capacity", "current_orders", "credit_score",
            "data_freshness_score", "patent_count", "rd_investment", "products",
        }
    )
    return extras


def load_csv_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {row.get("source_company_id", ""): row for row in csv.DictReader(handle) if row.get("source_company_id")}


def load_raw_rows(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    pages = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, dict[str, Any]] = {}
    for page in pages:
        for row in (page.get("payload") or {}).get("resultList", []):
            if isinstance(row, dict) and row.get("id") is not None:
                result[str(row["id"])] = row
    return result


def enrich(csv_path: Path, raw_path: Path, dry_run: bool = False) -> tuple[int, int]:
    csv_rows = load_csv_rows(csv_path)
    raw_rows = load_raw_rows(raw_path)
    updated = 0
    products_created = 0

    enterprises = Enterprise.query.all()
    for enterprise in enterprises:
        extras = enterprise.extras if isinstance(enterprise.extras, dict) else {}
        source_id = _text(extras.get("source_company_id"))
        if extras.get("source") != "tianxiagongchang.com" or source_id not in csv_rows:
            continue

        row = csv_rows[source_id]
        raw = raw_rows.get(source_id, {})
        industries = _text(row.get("raw_industries"))
        scope = _text(row.get("business_scope"))
        industry_code = _text(enterprise.industry_code) or classify_industry_code(industries, scope)
        metrics = build_demo_metrics(source_id, row.get("tech_keywords", ""))
        longitude, latitude = build_demo_coordinates(row.get("province", ""), row.get("city", ""), source_id)

        enterprise.address = enterprise.address or _text(row.get("city")) or _text(row.get("province")) or "待补充"
        enterprise.business_scope = enterprise.business_scope or scope or "制造业配套服务"
        enterprise.industry_code = industry_code
        enterprise.tech_keywords = enterprise.tech_keywords or _text(row.get("tech_keywords")) or industries
        enterprise.phone = None if enterprise.phone in {"00000000000", "待补充"} else enterprise.phone
        enterprise.company_images = enterprise.company_images or [IMAGE_PATH]
        enterprise.longitude = enterprise.longitude or longitude
        enterprise.latitude = enterprise.latitude or latitude
        enterprise.qualifications = enterprise.qualifications if enterprise.qualifications is not None else []
        enterprise.patents = enterprise.patents if enterprise.patents is not None else []
        enterprise.green_certification = enterprise.green_certification or {"level": "待评级", "source": "platform_demo"}
        enterprise.clean_energy_usage = enterprise.clean_energy_usage or round(_stable_int(source_id + ":energy", 5, 35) / 100, 2)
        enterprise.carbon_emission_level = enterprise.carbon_emission_level or "B"
        enterprise.environment_protection_patents = enterprise.environment_protection_patents or 0
        enterprise.green_supplier_rank = enterprise.green_supplier_rank or "待评级"
        for field, value in metrics.items():
            if getattr(enterprise, field, None) in (None, 0, 0.0):
                setattr(enterprise, field, value)
        enterprise.is_lead_enterprise = bool(raw.get("isSpecialized") or raw.get("isSingleChampion") or raw.get("isHighTech"))
        enterprise.is_dormant = False
        enterprise.current_mode = enterprise.current_mode or "seller"
        enterprise.extras = merge_source_extras(extras, raw)
        updated += 1

        existing_names = {p.name for p in Product.query.filter_by(enterprise_id=enterprise.id).all()}
        names = build_product_names(",".join(filter(None, [row.get("tech_keywords", ""), scope, industries])), industry_code, source_id)
        for name in names:
            if name in existing_names:
                continue
            db.session.add(Product(
                name=name,
                description=f"{name}，根据企业公开经营范围生成的平台展示产品，支持定制与批量采购，待企业确认。",
                category=industry_code,
                industry_code=industry_code,
                enterprise_id=enterprise.id,
                import_risk={"data_quality": "demo_enriched", "source": "tianxiagongchang.com"},
            ))
            products_created += 1

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return updated, products_created


def main() -> int:
    parser = argparse.ArgumentParser(description="补全天下工厂企业字段并生成平台展示产品")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    app = create_app()
    with app.app_context():
        try:
            updated, products = enrich(args.csv, args.raw, args.dry_run)
        except Exception:
            db.session.rollback()
            logging.exception("Enrichment failed")
            return 1
    logging.info("完成：更新企业 %s 家，新增产品 %s 条，dry_run=%s", updated, products, args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

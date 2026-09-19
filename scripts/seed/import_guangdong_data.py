"""
广东企业 CSV 导入 MySQL `enterprises` 表（与 app.models.Enterprise 一致）。

读取公开 CSV，制造业关键词过滤，只导入来源中实际存在的字段。
企业默认是“未认领、不可触达”的候选目录，不生成联系人、电话、地址、资本或信用分。

用法（项目根目录）：
    python scripts/seed/import_guangdong_data.py
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from os import environ

import pandas as pd
from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from app import create_app, db
from app.models import Enterprise, Product

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = _ROOT / "data" / "real_enterprises_test.csv"
BATCH_SIZE = 1000

# 与 CSV 列对应：支持英文列名与广东公开数据常见中文表头
_COL_NAME = ("enterprise_name", "企业名称", "公司名称")
_COL_PROVINCE = ("province", "所在省份", "省份")
_COL_CITY = ("city", "地区", "城市", "地市")
_COL_INDUSTRY = ("industry", "经营范围", "业务范围")
_COL_SOURCE_URL = ("source_url", "source", "来源链接", "来源网址", "数据来源")
_COL_PRODUCTS = ("product", "products", "产品", "主营产品", "产品能力", "制造能力", "product_name")

# 制造业关键词：企业名称或经营范围任含其一即导入
MFG_KEYWORDS = ("制造", "工业", "装备", "机械", "电子", "精密")

# 广东主要城市中心坐标 (lng, lat)
GUANGDONG_CITY_COORDS: dict[str, tuple[float, float]] = {
    "广州": (113.264385, 23.129163),
    "深圳": (114.057868, 22.543099),
    "东莞": (113.751799, 23.020536),
    "佛山": (113.121416, 23.021548),
    "珠海": (113.576726, 22.270715),
    "中山": (113.392782, 22.517645),
    "惠州": (114.415587, 23.112381),
}


def _clear_enterprises_fresh_start() -> None:
    for stmt in (
        "SET FOREIGN_KEY_CHECKS=0",
        "TRUNCATE TABLE demands",
        "TRUNCATE TABLE products",
        "TRUNCATE TABLE transactions",
        "TRUNCATE TABLE match_feedbacks",
        "TRUNCATE TABLE enterprise_patents",
        "TRUNCATE TABLE enterprises",
        "SET FOREIGN_KEY_CHECKS=1",
    ):
        db.session.execute(text(stmt))
    db.session.commit()
    logger.info("已 TRUNCATE enterprises 及关联表。")


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    stripped = [str(c).strip() for c in columns]
    lower_map = {s.lower(): s for s in stripped if s}
    for cand in candidates:
        c = cand.strip()
        if not c:
            continue
        if c in stripped:
            return c
        cl = c.lower()
        if cl in lower_map:
            return lower_map[cl]
    return None


def _normalize_city_key(city: str) -> str:
    s = (city or "").strip()
    if s.endswith("市"):
        s = s[:-1]
    return s


def _lng_lat_for_city(city: str) -> tuple[float | None, float | None]:
    key = _normalize_city_key(city)
    if key in GUANGDONG_CITY_COORDS:
        lng, lat = GUANGDONG_CITY_COORDS[key]
        return lng, lat
    if city.strip() in GUANGDONG_CITY_COORDS:
        lng, lat = GUANGDONG_CITY_COORDS[city.strip()]
        return lng, lat
    return None, None


def _cell(row: dict, key: str | None) -> str:
    if not key:
        return ""
    v = row.get(key, "")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _is_manufacturing(name: str, industry: str) -> bool:
    text_blob = f"{name}{industry}"
    return any(kw in text_blob for kw in MFG_KEYWORDS)


def _truncate(s: str, max_len: int) -> str:
    s = (s or "").strip()
    if len(s) <= max_len:
        return s
    return s[:max_len]


def import_guangdong_data(csv_path: Path, replace_all: bool = False) -> tuple[int, int, int]:
    """
    返回 (成功插入条数, 跳过非制造条数, 跳过无效/重复条数)。
    """
    if replace_all:
        _clear_enterprises_fresh_start()

    df = pd.read_csv(csv_path, encoding="utf-8-sig", on_bad_lines="skip")
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns.tolist()

    col_name = _pick_column(cols, _COL_NAME)
    col_province = _pick_column(cols, _COL_PROVINCE)
    col_city = _pick_column(cols, _COL_CITY)
    col_industry = _pick_column(cols, _COL_INDUSTRY)
    col_source_url = _pick_column(cols, _COL_SOURCE_URL)
    col_products = _pick_column(cols, _COL_PRODUCTS)

    if not col_name:
        raise ValueError(f"未找到企业名称列，当前表头: {cols}")

    logger.info(
        "列映射: enterprise_name=%s province=%s city=%s industry=%s",
        col_name,
        col_province,
        col_city,
        col_industry,
    )

    inserted = 0
    skipped_non_mfg = 0
    skipped_bad = 0
    seen_names: set[str] = {name for (name,) in db.session.query(Enterprise.name).all() if name}
    batch: list[dict] = []
    batch_product_specs: list[tuple[str, list[str]]] = []

    def flush() -> None:
        nonlocal inserted, batch, batch_product_specs
        if not batch:
            return
        db.session.bulk_insert_mappings(Enterprise, batch)
        db.session.commit()
        for enterprise_name, product_names in batch_product_specs:
            enterprise = Enterprise.query.filter_by(name=enterprise_name).first()
            if not enterprise:
                continue
            existing = {str(item.name).strip().lower() for item in Product.query.filter_by(enterprise_id=enterprise.id).all() if item.name}
            for product_name in product_names:
                if product_name.lower() in existing:
                    continue
                db.session.add(Product(enterprise_id=enterprise.id, name=product_name))
                existing.add(product_name.lower())
        db.session.commit()
        inserted += len(batch)
        logger.info("已批量提交 %s 条，累计 %s", len(batch), inserted)
        batch.clear()
        batch_product_specs.clear()

    for _, row in df.iterrows():
        r = row.to_dict()
        name = _cell(r, col_name)
        if not name:
            skipped_bad += 1
            continue

        name = _truncate(name, 100)
        if name in seen_names:
            skipped_bad += 1
            continue

        province = _cell(r, col_province) or None
        city_val = _cell(r, col_city) or None
        industry = _cell(r, col_industry)
        source_url = _cell(r, col_source_url) or None
        product_names = [
            _truncate(value, 200)
            for value in re.split(r"[,，、;/；|]+", _cell(r, col_products))
            if value.strip()
        ][:20]

        if not _is_manufacturing(name, industry):
            skipped_non_mfg += 1
            continue

        seen_names.add(name)

        lng, lat = _lng_lat_for_city(city_val or "")

        collected_at = datetime.utcnow()
        evidence_base = {
            "source_type": "public_directory",
            "source": csv_path.name,
            "source_url": source_url,
            "collected_at": collected_at.isoformat(),
            "updated_at": collected_at.isoformat(),
            "is_mock": False,
            "confidence": 0.6,
            "authorization": "public_directory_only",
        }
        data_evidence = {
            field: {**evidence_base, "value_present": bool(value)}
            for field, value in {
                "name": name,
                "province": province,
                "city": city_val,
                "business_scope": industry,
                "products": product_names,
            }.items()
        }
        mapping = {
            "name": name,
            "province": _truncate(province, 20) if province else None,
            "city": _truncate(city_val, 200) if city_val else None,
            "business_scope": industry if industry else None,
            "longitude": lng,
            "latitude": lat,
            "address": None,
            "contact": None,
            "phone": None,
            "registered_capital": None,
            # Enterprise.credit_score has a legacy ORM default of 70. Use a
            # neutral zero sentinel and explicitly mark it unverified so the
            # matcher never treats a generated default as a sourced fact.
            "credit_score": 0,
            "password_hash": None,
            "role": "enterprise",
            "is_admin": False,
            "capacity": 0,
            "current_orders": 0,
            "verification_status": "pending",
            "is_verified": False,
            "last_data_update": collected_at,
            "extras": {
                "trust_profile": {
                    "claim_status": "unclaimed",
                    "contact_authorized": False,
                    "sources": [{**evidence_base, "name": csv_path.name}],
                },
                "directory_record": True,
                "data_evidence": data_evidence,
                "unverified_fields": ["address", "contact", "phone", "registered_capital", "credit_score", "capacity"],
            },
            "created_at": collected_at,
        }
        batch.append(mapping)
        if product_names:
            batch_product_specs.append((name, product_names))

        if len(batch) >= BATCH_SIZE:
            flush()

    flush()
    return inserted, skipped_non_mfg, skipped_bad


def main() -> int:
    parser = argparse.ArgumentParser(description="导入广东企业 CSV 到 MySQL")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_CSV,
        help=f"CSV 路径（默认 {DEFAULT_CSV}）",
    )
    parser.add_argument("--replace-all", action="store_true", help="危险：清空企业及关联业务表后重建；默认只做增量导入")
    args = parser.parse_args()

    if not args.input.is_file():
        logger.error("找不到 CSV: %s", args.input.resolve())
        return 1
    if not environ.get("DATABASE_URL"):
        logger.error("DATABASE_URL 未设置")
        return 1

    app = create_app()
    with app.app_context():
        try:
            n, skip_mfg, skip_bad = import_guangdong_data(args.input, replace_all=args.replace_all)
        except Exception:
            db.session.rollback()
            logger.exception("导入失败")
            return 1

    logger.info(
        "完成：插入 %s 条；非制造业跳过 %s 条；空名/重复跳过 %s 条。",
        n,
        skip_mfg,
        skip_bad,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

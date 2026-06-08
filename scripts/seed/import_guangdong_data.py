"""
广东企业 CSV 导入 MySQL `enterprises` 表（与 app.models.Enterprise 一致）。

读取 data/real_enterprises_test.csv（UTF-8 BOM），制造业关键词过滤，Faker 补全联系人与资本等字段，
按城市补全经纬度，bulk_insert_mappings 每 1000 条提交。

用法（项目根目录）：
    python scripts/import_guangdong_data.py
"""
from __future__ import annotations

import argparse
import logging
import random
import sys
from datetime import datetime
from pathlib import Path
from os import environ

import pandas as pd
from faker import Faker
from sqlalchemy import text
from werkzeug.security import generate_password_hash

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from app import create_app, db
from app.models import Enterprise

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = _ROOT / "data" / "real_enterprises_test.csv"
DEFAULT_PASSWORD = "admin"
BATCH_SIZE = 1000

# 与 CSV 列对应：支持英文列名与广东公开数据常见中文表头
_COL_NAME = ("enterprise_name", "企业名称", "公司名称")
_COL_PROVINCE = ("province", "所在省份", "省份")
_COL_CITY = ("city", "地区", "城市", "地市")
_COL_INDUSTRY = ("industry", "经营范围", "业务范围")

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


def import_guangdong_data(csv_path: Path, default_password: str) -> tuple[int, int, int]:
    """
    返回 (成功插入条数, 跳过非制造条数, 跳过无效/重复条数)。
    """
    _clear_enterprises_fresh_start()

    df = pd.read_csv(csv_path, encoding="utf-8-sig", on_bad_lines="skip")
    df.columns = [str(c).strip() for c in df.columns]
    cols = df.columns.tolist()

    col_name = _pick_column(cols, _COL_NAME)
    col_province = _pick_column(cols, _COL_PROVINCE)
    col_city = _pick_column(cols, _COL_CITY)
    col_industry = _pick_column(cols, _COL_INDUSTRY)

    if not col_name:
        raise ValueError(f"未找到企业名称列，当前表头: {cols}")

    logger.info(
        "列映射: enterprise_name=%s province=%s city=%s industry=%s",
        col_name,
        col_province,
        col_city,
        col_industry,
    )

    fake = Faker("zh_CN")
    rng = random.Random()
    pw_hash = generate_password_hash(default_password)

    inserted = 0
    skipped_non_mfg = 0
    skipped_bad = 0
    seen_names: set[str] = set()
    batch: list[dict] = []

    def flush() -> None:
        nonlocal inserted, batch
        if not batch:
            return
        db.session.bulk_insert_mappings(Enterprise, batch)
        db.session.commit()
        inserted += len(batch)
        logger.info("已批量提交 %s 条，累计 %s", len(batch), inserted)
        batch.clear()

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

        if not _is_manufacturing(name, industry):
            skipped_non_mfg += 1
            continue

        seen_names.add(name)

        lng, lat = _lng_lat_for_city(city_val or "")

        street = fake.street_address()
        base = (city_val or "") + street
        address = _truncate(base, 200)

        mapping = {
            "name": name,
            "province": _truncate(province, 20) if province else None,
            "city": _truncate(city_val, 200) if city_val else None,
            "business_scope": industry if industry else None,
            "longitude": lng,
            "latitude": lat,
            "address": address if address else None,
            "contact": _truncate(fake.name(), 50),
            "phone": _truncate(fake.phone_number(), 20),
            "registered_capital": round(rng.uniform(500, 8000), 2),
            "credit_score": round(rng.uniform(80, 95), 2),
            "password_hash": pw_hash,
            "role": "enterprise",
            "is_admin": False,
            "capacity": 50,
            "current_orders": 0,
            "created_at": datetime.utcnow(),
        }
        batch.append(mapping)

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
    parser.add_argument("-p", "--password", default=DEFAULT_PASSWORD, help="默认登录密码哈希用")
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
            n, skip_mfg, skip_bad = import_guangdong_data(args.input, args.password)
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

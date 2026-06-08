"""
从 CSV 批量导入企业到 MySQL `enterprises` 表。

默认读取项目根目录下的 unique_enterprises.csv（列：enterprise_name, province, city, industry）。

用法（在项目根目录执行）：
    python scripts/import_enterprises_mysql.py
    python scripts/import_enterprises_mysql.py -i my.csv

依赖：已配置 .env 中的 DATABASE_URL；python-dotenv、pandas 已列入 requirements。
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from os import environ

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from sqlalchemy.exc import IntegrityError

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from app import create_app, db
from app.models import Enterprise

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = _ROOT / "unique_enterprises.csv"
DEFAULT_CSV_ALT = _ROOT / "data" / "unique_enterprises.csv"
DEFAULT_PASSWORD = "123456"
NAME_MAX_LEN = 100
BATCH_SIZE = 1000
PROGRESS_EVERY = 100


def _read_csv_dataframe(path: Path) -> pd.DataFrame:
    """读取 CSV，尝试多种编码。"""
    encodings = ("utf-8-sig", "utf-8", "gb18030", "gbk")
    last_err: Exception | None = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            logger.warning("编码 %s 失败，尝试下一种…", enc)
    raise last_err or OSError("无法解码 CSV")


def _cell(row: dict, key: str) -> str:
    """从字典行安全取字符串（兼容 NaN、numpy 标量等）。"""
    v = row.get(key, "")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _truncate_name(name: str) -> str:
    if len(name) <= NAME_MAX_LEN:
        return name
    logger.warning("企业名称过长，已截断至 %s 字符: %r…", NAME_MAX_LEN, name[:40])
    return name[:NAME_MAX_LEN]


def import_data(csv_path: Path, default_password: str) -> tuple[int, int, int]:
    """
    使用 Pandas 读取 CSV，安全遍历字典列表并批量写入数据库。
    返回 (新增数量, 跳过已存在, 跳过无效行)。
    """
    df = _read_csv_dataframe(csv_path)
    if df.columns is None or len(df.columns) == 0:
        raise ValueError("CSV 无表头")

    df.columns = pd.Index([str(c).strip() for c in df.columns])
    df = df.fillna("")
    records = df.to_dict("records")

    added = 0
    skipped_exists = 0
    skipped_bad = 0
    total = len(records)

    batch: list[Enterprise] = []

    def commit_batch() -> None:
        """每 100 条强制 commit一次，遇到错误跳过并继续"""
        nonlocal added, skipped_exists, batch
        if not batch:
            return
        for ent in batch:
            try:
                db.session.add(ent)
                db.session.commit()
                added += 1
                if added % 100 == 0:
                    logger.info("当前已成功入库 %s 条", added)
            except Exception as e:
                db.session.rollback()
                skipped_exists += 1
                logger.debug("跳过重复/错误记录: %s", str(e)[:80])
        batch.clear()

    for idx, row in enumerate(records, start=1):
        if idx % PROGRESS_EVERY == 0 or idx == total:
            logger.info("进度: %s / %s", idx, total)

        name = _cell(row, "enterprise_name")
        if not name:
            skipped_bad += 1
            continue

        name = _truncate_name(name)
        province_s = _cell(row, "province")
        province = province_s if province_s else None
        city_val = _cell(row, "city")
        industry = _cell(row, "industry")

        if Enterprise.query.filter_by(name=name).first():
            skipped_exists += 1
            continue

        ent = Enterprise(
            name=name,
            address=city_val if city_val else None,
            city=city_val if city_val else None,
            province=province,
            business_scope=industry if industry else None,
            contact="导入",
            phone="00000000000",
            role="enterprise",
        )
        ent.set_password(default_password)
        batch.append(ent)

        if len(batch) >= 100:
            commit_batch()

    # 尾部剩余记录
    commit_batch()
    logger.info("导入完成，最终成功入库 %s 条", added)

    return added, skipped_exists, skipped_bad


def main() -> int:
    parser = argparse.ArgumentParser(description="从 CSV 导入企业到 MySQL")
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        default=DEFAULT_CSV,
        help=f"CSV 路径（默认: {DEFAULT_CSV}）",
    )
    parser.add_argument(
        "-p",
        "--password",
        default=DEFAULT_PASSWORD,
        help=f"新企业默认登录密码（默认: {DEFAULT_PASSWORD}）",
    )
    args = parser.parse_args()

    if not args.input.is_file() and DEFAULT_CSV_ALT.is_file():
        logger.info("使用备用路径: %s", DEFAULT_CSV_ALT)
        args.input = DEFAULT_CSV_ALT
    if not args.input.is_file():
        logger.error(
            "找不到 CSV 文件。请将 unique_enterprises.csv 放在项目根目录或 data/ 下: %s 或 %s",
            DEFAULT_CSV.resolve(),
            DEFAULT_CSV_ALT.resolve(),
        )
        return 1

    db_url = environ.get("DATABASE_URL")
    if not db_url:
        logger.error(
            "环境变量 DATABASE_URL 未设置。请检查项目根目录 .env 是否包含 "
            "DATABASE_URL=mysql+pymysql://... 并已通过 load_dotenv 加载。"
        )
        return 1

    app = create_app()
    with app.app_context():
        try:
            added, skip_dup, skip_bad = import_data(args.input, args.password)
        except Exception:
            db.session.rollback()
            logger.exception("导入失败，已回滚")
            return 1

    logger.info(
        "完成：新增 %s 条，已存在跳过 %s 条，空名称跳过 %s 条。",
        added,
        skip_dup,
        skip_bad,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

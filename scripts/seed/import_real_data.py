"""
广东真实数据 CSV → MySQL `enterprises`（清空后重建导入）。

- 启动时按外键顺序 TRUNCATE 子表与 enterprises，重置自增 ID。
- 分块读取 GB18030 CSV（encoding_errors 替换非法字节；坏行跳过）。
- 列名以中文常量为主（企业名称、注册地址、经营范围及省/市），与首块调试输出对照。

用法（在项目根目录）：
    python scripts/import_real_data.py
    python scripts/import_real_data.py -i my.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from os import environ
from typing import Any

import pandas as pd
from sqlalchemy import text

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv

load_dotenv(_ROOT / ".env")

from app import create_app, db
from app.models import Enterprise

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = _ROOT / "unique_enterprises.csv"
DEFAULT_CSV_ALT = _ROOT / "data" / "unique_enterprises.csv"
DEFAULT_PASSWORD = "admin"
NAME_MAX_LEN = 100
PROGRESS_EVERY = 100
CHUNK_SIZE = 8000

# 与广东公开数据表头一致的主列名（优先匹配；首块 📢 打印可核对）
COL_NAME = "企业名称"
COL_ADDRESS = "注册地址"
COL_SCOPE = "经营范围"
COL_PROVINCE = "省份"
COL_CITY = "城市"

# 备选列名（实际 CSV 表头变体）
_CAND_NAME = (
    COL_NAME,
    "公司名称",
    "商事主体名称",
    "名称",
    "name",
    "企业名",
)
_CAND_ADDRESS = (COL_ADDRESS, "address", "住所", "经营场所")
_CAND_LEGAL = ("法人代表", "legal_person", "法定代表人", "法人")
_CAND_SCOPE = (COL_SCOPE, "business_scope", "业务范围", "行业")
_CAND_PROVINCE = (COL_PROVINCE, "所在省份", "省", "province", "行政区划省")
_CAND_CITY = (COL_CITY, "地区", "市", "city", "地市", "县")


def _clear_enterprises_fresh_start() -> None:
    """清空引用 enterprises 的子表后 TRUNCATE enterprises，重置自增 ID。"""
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
    logger.info("已清空 enterprises 及依赖表，可全新导入。")


def _pick_column(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    """在已 strip 的列名中，按候选列表顺序取第一个存在的列（英文不区分大小写）。"""
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


def _cell(row: dict[str, Any], key: str | None) -> str:
    if not key:
        return ""
    v = row.get(key, "")
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def _truncate_name(name: str) -> str:
    if len(name) <= NAME_MAX_LEN:
        return name
    logger.warning("企业名称过长，已截断至 %s 字符: %r…", NAME_MAX_LEN, name[:40])
    return name[:NAME_MAX_LEN]


def import_real_data(csv_path: Path, default_password: str) -> tuple[int, int, int]:
    """
    读取 CSV（GB18030；坏行跳过）并写入 enterprises。
    字段映射：name←企业名称等、address←注册地址、business_scope←经营范围；省/市见列映射日志。
    返回 (新增数量, 跳过已存在, 跳过无效行)。
    """
    _clear_enterprises_fresh_start()

    reader = pd.read_csv(
        csv_path,
        encoding="gb18030",
        encoding_errors="replace",
        on_bad_lines="skip",
        chunksize=CHUNK_SIZE,
    )

    added = 0
    skipped_exists = 0
    skipped_bad = 0
    row_global = 0

    name_col: str | None = None
    address_col: str | None = None
    legal_col: str | None = None
    scope_col: str | None = None
    province_col: str | None = None
    city_col: str | None = None
    mapping_logged = False
    first_chunk = True

    batch: list[Enterprise] = []

    def commit_batch() -> None:
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

    for chunk in reader:
        if first_chunk:
            print(f"📢 调试信息 - 发现的原始列名有: {chunk.columns.tolist()}")
            first_chunk = False

        chunk.columns = [str(c).strip() for c in chunk.columns]

        if not mapping_logged:
            cols = chunk.columns.tolist()
            name_col = _pick_column(cols, _CAND_NAME)
            address_col = _pick_column(cols, _CAND_ADDRESS)
            legal_col = _pick_column(cols, _CAND_LEGAL)
            scope_col = _pick_column(cols, _CAND_SCOPE)
            province_col = _pick_column(cols, _CAND_PROVINCE)
            city_col = _pick_column(cols, _CAND_CITY)
            logger.info(
                "列映射: name=%s address=%s legal->contact=%s scope=%s province=%s city=%s",
                name_col,
                address_col,
                legal_col,
                scope_col,
                province_col,
                city_col,
            )
            if not name_col:
                logger.error(
                    "未匹配到名称列（候选 %s），请根据 DEBUG 输出调整脚本中的候选列名。",
                    _CAND_NAME,
                )
            mapping_logged = True

        if chunk.columns is None or len(chunk.columns) == 0:
            raise ValueError("CSV 无表头")

        chunk = chunk.fillna("")
        records = chunk.to_dict("records")

        for row in records:
            row_global += 1
            if row_global % PROGRESS_EVERY == 0:
                logger.info("进度: 已处理行约 %s", row_global)

            name = _cell(row, name_col)
            if not name:
                skipped_bad += 1
                continue

            name = _truncate_name(name)
            addr = _cell(row, address_col)
            legal = _cell(row, legal_col)
            scope = _cell(row, scope_col)
            province_s = _cell(row, province_col)
            province = province_s if province_s else None
            city_val = _cell(row, city_col)
            # 注册地址优先；缺失时再用城市作地址回退（与计划一致）
            addr_final = (addr or "").strip()
            if not addr_final and city_val:
                addr_final = city_val.strip()

            if Enterprise.query.filter_by(name=name).first():
                skipped_exists += 1
                continue

            contact_val = legal if legal else "导入"

            ent = Enterprise(
                name=name,
                address=addr_final or None,
                city=city_val if city_val else None,
                province=province,
                business_scope=scope if scope else None,
                contact=contact_val[:50] if contact_val else "导入",
                phone="00000000000",
                role="enterprise",
            )
            ent.set_password(default_password)
            batch.append(ent)

            if len(batch) >= 100:
                commit_batch()

    commit_batch()
    logger.info("导入完成，最终成功入库 %s 条", added)

    return added, skipped_exists, skipped_bad


def main() -> int:
    parser = argparse.ArgumentParser(
        description="广东真实数据：GB18030 CSV 导入 enterprises（先清空子表与企业表）"
    )
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
            "找不到 CSV 文件: %s 或 %s",
            DEFAULT_CSV.resolve(),
            DEFAULT_CSV_ALT.resolve(),
        )
        return 1

    if not environ.get("DATABASE_URL"):
        logger.error("环境变量 DATABASE_URL 未设置，请检查 .env。")
        return 1

    app = create_app()
    with app.app_context():
        try:
            added, skip_dup, skip_bad = import_real_data(args.input, args.password)
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

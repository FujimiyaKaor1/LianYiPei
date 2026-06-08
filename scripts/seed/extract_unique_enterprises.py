"""
从「上市公司上下游、客户数据匹配」类 CSV / XLSX 中提取去重企业名录。

默认筛选：年份 >= MIN_YEAR；未指定 TARGET_INDUSTRY 时，行业名称须命中 target_keywords 中任一制造业相关子串。
从「中文全称、上游供应商、下游客户」三列收集企业名并去重。

用法（在项目根目录）:
  python scripts/extract_unique_enterprises.py
  python scripts/extract_unique_enterprises.py -i "path/to/file.csv"

依赖: pandas, openpyxl（读 .xlsx 时需要）
"""
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent

# 默认输入：优先「导出 CSV」文件名；若不存在则使用同目录下同名 .xlsx
DEFAULT_CSV_NAME = "上市公司上下游、客户数据匹配（2001-2024年）.xlsx - Sheet1.csv"
DEFAULT_XLSX_NAME = "上市公司上下游、客户数据匹配（2001-2024年）.xlsx"

COL_INDUSTRY = "行业名称"
COL_YEAR = "年份"
COL_FULL_NAME = "中文全称"
COL_UPSTREAM = "上游供应商"
COL_DOWNSTREAM = "下游客户"
COL_PROVINCE = "省份"
COL_CITY = "城市"

TARGET_INDUSTRY = None  # None 表示不按单一行业精确匹配，此时用 target_keywords 筛选行业名称子串
MIN_YEAR = 2018
OUTPUT_COLS = ["enterprise_name", "province", "city", "industry"]

# 行业名称需包含以下任一子串（制造业向）；仅当 TARGET_INDUSTRY 为 None 时参与筛选
target_keywords = [
    "制造",
    "工业",
    "装备",
    "材料",
    "机械",
    "加工",
    "五金",
    "塑胶",
    "机电",
    "模具",
    "电子",
    "半导体",
    "新能源",
    "电气",
    "精密",
]


def _normalize_str(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "-", "—", "--"):
        return None
    return s


def _split_company_field(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r"[,，;；、\n\r\t]+", raw)
    out = []
    for p in parts:
        n = _normalize_str(p)
        if n:
            out.append(n)
    return out


def _find_default_input(root: Path) -> Path | None:
    csv_path = root / DEFAULT_CSV_NAME
    if csv_path.is_file():
        return csv_path
    xlsx_path = root / DEFAULT_XLSX_NAME
    if xlsx_path.is_file():
        return xlsx_path
    # 根目录仅有一个匹配年份的 xlsx 时作为兜底
    for p in sorted(root.glob("*.xlsx")):
        if "2001" in p.name and "2024" in p.name:
            return p
    xlsx_list = list(root.glob("*.xlsx"))
    if len(xlsx_list) == 1:
        return xlsx_list[0]
    return None


def _read_csv(path: Path) -> pd.DataFrame:
    encodings = ("utf-8-sig", "utf-8", "gb18030", "gbk")
    last_err = None
    for enc in encodings:
        try:
            df = pd.read_csv(path, encoding=enc, dtype=str, keep_default_na=False)
            df.columns = df.columns.str.strip()
            return df
        except UnicodeDecodeError as e:
            last_err = e
            logger.warning("编码 %s 失败，尝试下一种…", enc)
    raise last_err or RuntimeError("无法解码 CSV 文件")


def _read_excel(path: Path) -> pd.DataFrame:
    try:
        df = pd.read_excel(path, sheet_name="Sheet1", dtype=str, engine="openpyxl")
    except Exception:
        df = pd.read_excel(path, sheet_name=0, dtype=str, engine="openpyxl")
    df.columns = df.columns.str.strip()
    return df


def _read_table(path: Path) -> pd.DataFrame:
    suf = path.suffix.lower()
    if suf == ".csv":
        return _read_csv(path)
    if suf in (".xlsx", ".xls"):
        return _read_excel(path)
    raise ValueError(f"不支持的文件类型: {path}")


def _ensure_columns(df: pd.DataFrame, required: list[str]) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"缺少列: {missing}。实际列名: {list(df.columns)}")


def _to_int_year(series: pd.Series) -> pd.Series:
    def one(v):
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return pd.NA
        try:
            return int(float(str(v).strip()))
        except (ValueError, TypeError):
            return pd.NA

    return series.map(one)


def build_unique_enterprises(df: pd.DataFrame) -> pd.DataFrame:
    _ensure_columns(
        df,
        [
            COL_INDUSTRY,
            COL_YEAR,
            COL_FULL_NAME,
            COL_UPSTREAM,
            COL_DOWNSTREAM,
        ],
    )

    if COL_PROVINCE not in df.columns:
        df[COL_PROVINCE] = ""
    if COL_CITY not in df.columns:
        df[COL_CITY] = ""

    df = df.copy()
    df["_year_int"] = _to_int_year(df[COL_YEAR])

    mask_year = df["_year_int"] >= MIN_YEAR
    if TARGET_INDUSTRY:
        mask_industry = df[COL_INDUSTRY].astype(str).str.strip() == TARGET_INDUSTRY
        filtered = df.loc[mask_industry & mask_year].copy()
    else:
        ind_raw = df[COL_INDUSTRY].astype(str)
        mask_kw = ind_raw.apply(lambda s: any(kw in s for kw in target_keywords))
        filtered = df.loc[mask_year & mask_kw].copy()
    if filtered.empty:
        logger.warning(
            "筛选后无数据：年份>=%s%s。请检查列值与类型。",
            MIN_YEAR,
            "，且行业名称需命中 target_keywords" if not TARGET_INDUSTRY else "",
        )

    geo_from_fullname: dict[str, dict[str, str | None]] = {}

    def record_geo_for_fullname_row(row):
        name = _normalize_str(row.get(COL_FULL_NAME))
        if not name:
            return
        prov = _normalize_str(row.get(COL_PROVINCE))
        city = _normalize_str(row.get(COL_CITY))
        if name not in geo_from_fullname:
            geo_from_fullname[name] = {"province": prov, "city": city}
            return
        cur = geo_from_fullname[name]
        if not cur.get("province") and prov:
            cur["province"] = prov
        if not cur.get("city") and city:
            cur["city"] = city

    for _, row in filtered.iterrows():
        try:
            record_geo_for_fullname_row(row)
        except Exception as e:
            logger.debug("跳过一行地域写入: %s", e)

    all_names: set[str] = set()

    for _, row in filtered.iterrows():
        try:
            fn = _normalize_str(row.get(COL_FULL_NAME))
            if fn:
                all_names.add(fn)
            up = _normalize_str(row.get(COL_UPSTREAM))
            for n in _split_company_field(up):
                all_names.add(n)
            down = _normalize_str(row.get(COL_DOWNSTREAM))
            for n in _split_company_field(down):
                all_names.add(n)
        except Exception as e:
            logger.warning("解析行时出错（已跳过该行部分字段）: %s", e)

    rows = []
    for name in sorted(all_names):
        geo = geo_from_fullname.get(name, {"province": None, "city": None})
        rows.append(
            {
                "enterprise_name": name,
                "province": geo.get("province") or "",
                "city": geo.get("city") or "",
                "industry": TARGET_INDUSTRY,
            }
        )

    return pd.DataFrame(rows, columns=OUTPUT_COLS)


def main() -> int:
    parser = argparse.ArgumentParser(description="提取去重企业名录 CSV")
    parser.add_argument(
        "--input",
        "-i",
        type=Path,
        default=None,
        help="输入 CSV 或 XLSX 路径（默认自动查找项目根目录下数据文件）",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=_ROOT / "unique_enterprises.csv",
        help="输出 CSV 路径（默认项目根目录 unique_enterprises.csv）",
    )
    args = parser.parse_args()

    path = args.input
    if path is None:
        path = _find_default_input(_ROOT)
    else:
        path = path if path.is_absolute() else (_ROOT / path)

    if path is None or not path.is_file():
        logger.error(
            "找不到数据文件。请将「%s」或「%s」放在项目根目录: %s",
            DEFAULT_CSV_NAME,
            DEFAULT_XLSX_NAME,
            _ROOT,
        )
        return 1

    logger.info("读取: %s", path.resolve())

    try:
        df = _read_table(path)
    except Exception as e:
        logger.exception("读取失败: %s", e)
        return 1

    try:
        out = build_unique_enterprises(df)
    except ValueError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:
        logger.exception("处理失败: %s", e)
        return 1

    out_path = args.output if args.output.is_absolute() else (_ROOT / args.output)
    try:
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
    except OSError as e:
        logger.exception("写入失败: %s", e)
        return 1

    logger.info(
        "已写入 %s，共 %s 家去重企业。",
        out_path.resolve(),
        len(out),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

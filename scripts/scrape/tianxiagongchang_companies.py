#!/usr/bin/env python3
"""
Scrape authorized company search result data from tianxiagongchang.com.

The script follows the site's normal browser challenge flow, reads Nuxt SSR
payloads from public search pages, and writes both raw records and a platform
import CSV for LianYiPei.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

BASE_URL = "https://www.tianxiagongchang.com"
DEFAULT_KEYWORDS = [
    "五金加工",
    "注塑模具",
    "汽车零部件",
    "电子元器件",
    "包装印刷",
    "纺织服装",
    "PCB电路板",
    "医疗器械",
]
EXTENDED_KEYWORDS = [
    "数控机床",
    "精密加工",
    "机械加工",
    "钣金加工",
    "冲压件",
    "注塑件",
    "压铸件",
    "铸造件",
    "锻造件",
    "模具制造",
    "塑胶模具",
    "精密模具",
    "五金模具",
    "汽车模具",
    "电子连接器",
    "连接线",
    "线束",
    "电路板",
    "线路板",
    "PCBA",
    "SMT贴片",
    "电子组装",
    "传感器",
    "电机",
    "减速机",
    "轴承",
    "齿轮",
    "液压件",
    "气动元件",
    "阀门",
    "泵",
    "风机",
    "压缩机",
    "变压器",
    "电源适配器",
    "锂电池",
    "电池PACK",
    "储能设备",
    "光伏组件",
    "逆变器",
    "LED灯具",
    "照明器具",
    "工业机器人",
    "自动化设备",
    "输送设备",
    "包装机械",
    "印刷机械",
    "食品机械",
    "医疗设备",
    "实验仪器",
    "仪器仪表",
    "检测设备",
    "环保设备",
    "水处理设备",
    "空压机",
    "叉车配件",
    "汽车配件",
    "汽车电子",
    "新能源车配件",
    "摩托车配件",
    "自行车配件",
    "无人机配件",
    "家电配件",
    "小家电",
    "厨房电器",
    "智能家居",
    "安防设备",
    "摄像头",
    "通信设备",
    "光通信",
    "光纤跳线",
    "电线电缆",
    "电缆组件",
    "开关电源",
    "配电柜",
    "控制柜",
    "机箱机柜",
    "金属制品",
    "不锈钢制品",
    "铝合金制品",
    "铝型材",
    "钢结构",
    "紧固件",
    "螺丝",
    "弹簧",
    "刀具",
    "量具",
    "密封件",
    "橡胶制品",
    "硅胶制品",
    "塑料制品",
    "吸塑包装",
    "纸箱包装",
    "彩盒包装",
    "标签印刷",
    "不干胶",
    "服装加工",
    "针织服装",
    "毛衫",
    "鞋材",
    "箱包",
    "皮具",
    "家具",
    "办公家具",
    "板式家具",
    "灯饰",
    "陶瓷",
    "卫浴",
    "门窗",
    "玻璃制品",
    "化工原料",
    "涂料",
    "胶粘剂",
    "新材料",
    "复合材料",
    "碳纤维",
    "无纺布",
    "医用耗材",
    "口罩",
    "注射器",
    "康复器械",
    "牙科器械",
    "宠物用品",
    "玩具",
    "文具",
    "体育用品",
    "工艺品",
    "智能手表",
    "蓝牙耳机",
    "充电器",
    "数据线",
    "散热器",
    "热交换器",
    "工业清洗",
    "表面处理",
    "喷涂加工",
    "电镀加工",
    "阳极氧化",
    "激光切割",
    "焊接加工",
    "CNC加工",
    "3D打印",
    "PCB打样",
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/126.0 Safari/537.36 authorized-data-collection/1.0"
)

OUTPUT_COLUMNS = [
    "name",
    "address",
    "province",
    "city",
    "district",
    "business_scope",
    "contact",
    "phone",
    "registered_capital",
    "registered_capital_raw",
    "business_status",
    "industry_code",
    "tech_keywords",
    "credit_score",
    "role",
    "is_verified",
    "verification_status",
    "source",
    "source_company_id",
    "source_url",
    "source_query",
    "uscc",
    "establishment_date",
    "website",
    "phones_count",
    "crucial_count",
    "tags",
    "raw_industries",
    "scraped_at",
]


def _leading_zero_bits(hex_digest: str) -> int:
    zeros = 0
    for char in hex_digest:
        nibble = int(char, 16)
        if nibble == 0:
            zeros += 4
            continue
        if nibble < 2:
            zeros += 3
        elif nibble < 4:
            zeros += 2
        elif nibble < 8:
            zeros += 1
        break
    return zeros


def _solve_pow(token: str, difficulty: int) -> str:
    if difficulty <= 0:
        return "0"
    cap = 1 << 26
    for nonce in range(cap):
        digest = hashlib.sha256(f"{token}:{nonce}".encode("utf-8")).hexdigest()
        if _leading_zero_bits(digest) >= difficulty:
            return str(nonce)
    return str(cap)


class TianxiaSession:
    def __init__(self, delay: float, browser_state: Path | None = None) -> None:
        self.delay = delay
        self.last_request = 0.0
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "zh-CN,zh;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        if browser_state:
            self._load_browser_state(browser_state)

    def get(self, url: str) -> str:
        self._throttle()
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        if "正在验证您的访问" in response.text:
            self._pass_challenge(response.text)
            self._throttle()
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
        return response.text

    def _throttle(self) -> None:
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()

    def _pass_challenge(self, html: str) -> None:
        token_match = re.search(r"var token = '([^']+)'", html)
        difficulty_match = re.search(r"var difficulty = (\d+)", html)
        if not token_match or not difficulty_match:
            raise RuntimeError("Challenge page did not include token/difficulty")

        token = token_match.group(1)
        difficulty = int(difficulty_match.group(1))
        start = time.time()
        solution = _solve_pow(token, difficulty)
        duration_ms = int((time.time() - start) * 1000)
        response = self.session.post(
            f"{BASE_URL}/api/challenge/verify",
            json={"token": token, "solution": solution, "duration": duration_ms},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200:
            raise RuntimeError(f"Challenge failed: {payload}")

    def _load_browser_state(self, path: Path) -> None:
        state = json.loads(path.read_text(encoding="utf-8"))
        for part in str(state.get("cookie") or "").split(";"):
            if "=" not in part:
                continue
            name, value = part.strip().split("=", 1)
            if name:
                self.session.cookies.set(name, value, domain=".tianxiagongchang.com", path="/")
        token = (state.get("localStorage") or {}).get("isis_token")
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"


def _resolve_nuxt_value(payload: list[Any], value: Any, stack: frozenset[int] = frozenset()) -> Any:
    if isinstance(value, int) and 0 <= value < len(payload):
        target = payload[value]
        if not isinstance(target, (dict, list)):
            return target
        if value in stack:
            return None
        return _resolve_nuxt_value(payload, target, stack | {value})

    if isinstance(value, list):
        if value and isinstance(value[0], str) and value[0] in {
            "Reactive",
            "ShallowReactive",
            "Ref",
            "EmptyRef",
            "Set",
        }:
            marker = value[0]
            if marker == "EmptyRef":
                return None
            if marker == "Set":
                return []
            return _resolve_nuxt_value(payload, value[1], stack)
        return [_resolve_nuxt_value(payload, item, stack) for item in value]

    if isinstance(value, dict):
        return {key: _resolve_nuxt_value(payload, item, stack) for key, item in value.items()}

    return value


def extract_search_payload(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script type="application/json"[^>]*id="__NUXT_DATA__">(.*?)</script>',
        html,
        flags=re.S,
    )
    if not match:
        raise ValueError("No __NUXT_DATA__ payload found")

    payload = json.loads(unescape(match.group(1)))
    root = _resolve_nuxt_value(payload, 0)
    company_search = root.get("data", {}).get("company-search", {})
    if company_search.get("code") not in (0, 200):
        return company_search
    return company_search.get("data", {})


def _number_from_capital(raw: str) -> float | None:
    if not raw:
        return None
    match = re.search(r"([\d.]+)", raw.replace(",", ""))
    if not match:
        return None
    value = float(match.group(1))
    if "亿" in raw:
        value *= 10000
    if "美元" in raw:
        value *= 7.1
    return round(value, 2)


def _tag_values(tags: Any) -> list[str]:
    values: list[str] = []
    if not isinstance(tags, list):
        return values
    for tag in tags:
        if isinstance(tag, dict):
            value = tag.get("value")
            content = tag.get("content")
            if value:
                values.append(str(value))
            if content:
                values.append(str(content))
        elif tag:
            values.append(str(tag))
    return values


def _clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = "".join(
        char
        for char in text
        if unicodedata.category(char) not in {"Cf", "Cc", "Cs"}
        or char in {"\n", "\t"}
    )
    return re.sub(r"\s+", " ", text).strip()


def normalise_company(raw: dict[str, Any], query: str, scraped_at: str) -> dict[str, Any]:
    industries = raw.get("industry") if isinstance(raw.get("industry"), list) else []
    industries = [_clean_text(item) for item in industries if _clean_text(item)]
    services = _clean_text(raw.get("tkaiccServices"))
    detail_url = _clean_text(raw.get("detailURL"))
    source_url = f"{BASE_URL}{detail_url}" if detail_url.startswith("/") else detail_url
    tags = [_clean_text(item) for item in _tag_values(raw.get("tags")) if _clean_text(item)]

    return {
        "name": _clean_text(raw.get("companyName")),
        "address": _clean_text(raw.get("address")),
        "province": _clean_text(raw.get("province")),
        "city": _clean_text(raw.get("city")),
        "district": _clean_text(raw.get("county")),
        "business_scope": services,
        "contact": (_clean_text(raw.get("legalPerson")) or "导入")[:50],
        "phone": "00000000000",
        "registered_capital": _number_from_capital(_clean_text(raw.get("registeredCapital"))),
        "registered_capital_raw": _clean_text(raw.get("registeredCapital")),
        "business_status": _clean_text(raw.get("businessStatus")),
        "industry_code": "",
        "tech_keywords": ",".join(industries[:8]),
        "credit_score": 80.0,
        "role": "enterprise",
        "is_verified": "true" if raw.get("businessStatus") == "存续" else "false",
        "verification_status": "approved" if raw.get("businessStatus") == "存续" else "pending",
        "source": "tianxiagongchang.com",
        "source_company_id": raw.get("id"),
        "source_url": source_url,
        "source_query": query,
        "uscc": _clean_text(raw.get("unicode")),
        "establishment_date": _clean_text(raw.get("establishmentDate")),
        "website": _clean_text(raw.get("website")),
        "phones_count": raw.get("phonesCount"),
        "crucial_count": raw.get("crucialCount"),
        "tags": ",".join(tags),
        "raw_industries": ",".join(industries),
        "scraped_at": scraped_at,
    }


def build_search_url(keyword: str) -> str:
    return f"{BASE_URL}/search?{urlencode({'q': keyword})}"


def scrape_keywords(
    keywords: list[str],
    delay: float,
    browser_state: Path | None,
    target_records: int | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    client = TianxiaSession(delay=delay, browser_state=browser_state)
    companies_by_id: dict[str, dict[str, Any]] = {}
    raw_pages: list[dict[str, Any]] = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for keyword in keywords:
        url = build_search_url(keyword)
        logging.info("Fetching %s", url)
        html = client.get(url)
        payload = extract_search_payload(html)
        if payload.get("code") and payload.get("code") not in (0, 200):
            logging.warning("Keyword %s returned non-success payload: %s", keyword, payload)
            raw_pages.append({"keyword": keyword, "url": url, "payload": payload})
            continue

        result_list = payload.get("resultList", [])
        raw_pages.append({"keyword": keyword, "url": url, "payload": payload})
        logging.info(
            "Keyword %s yielded %s visible records (reported total=%s)",
            keyword,
            len(result_list),
            payload.get("resultNum"),
        )
        for raw in result_list:
            if not isinstance(raw, dict):
                continue
            normalised = normalise_company(raw, keyword, scraped_at)
            key = str(normalised.get("source_company_id") or normalised.get("name"))
            if not normalised["name"]:
                continue
            companies_by_id.setdefault(key, normalised)
        if target_records and len(companies_by_id) >= target_records:
            logging.info("Reached target_records=%s", target_records)
            break

    return list(companies_by_id.values()), raw_pages


def write_outputs(companies: list[dict[str, Any]], raw_pages: list[dict[str, Any]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    platform_csv = output_dir / "tianxiagongchang_companies_platform.csv"
    raw_json = output_dir / "tianxiagongchang_raw_pages.json"
    summary_json = output_dir / "tianxiagongchang_summary.json"

    with platform_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for company in companies:
            writer.writerow(company)

    raw_json.write_text(json.dumps(raw_pages, ensure_ascii=False, indent=2), encoding="utf-8")
    summary_json.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": BASE_URL,
                "records": len(companies),
                "queries": [page["keyword"] for page in raw_pages],
                "platform_csv": str(platform_csv),
                "raw_json": str(raw_json),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scrape Tianxia Gongchang company search data")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=DEFAULT_KEYWORDS,
        help="Search keywords. Defaults to homepage manufacturing examples.",
    )
    parser.add_argument(
        "--keyword-file",
        type=Path,
        help="Optional UTF-8 text file with one search keyword per line.",
    )
    parser.add_argument(
        "--extended-keywords",
        action="store_true",
        help="Use the built-in extended manufacturing keyword set.",
    )
    parser.add_argument(
        "--browser-state",
        type=Path,
        help="JSON exported from the logged-in browser page with cookie/localStorage.",
    )
    parser.add_argument(
        "--target-records",
        type=int,
        help="Stop after this many unique company records have been collected.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/external/tianxiagongchang"),
        help="Directory for CSV/JSON outputs.",
    )
    parser.add_argument("--delay", type=float, default=1.2, help="Delay between requests in seconds.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    keywords = list(args.keywords or [])
    if args.extended_keywords:
        keywords = DEFAULT_KEYWORDS + EXTENDED_KEYWORDS
    if args.keyword_file:
        file_keywords = [
            line.strip()
            for line in args.keyword_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        keywords = file_keywords
    keywords = list(dict.fromkeys(keywords))

    companies, raw_pages = scrape_keywords(
        keywords,
        args.delay,
        args.browser_state,
        args.target_records,
    )
    if args.target_records:
        companies = companies[: args.target_records]
    write_outputs(companies, raw_pages, args.output_dir)
    logging.info("Wrote %s unique companies to %s", len(companies), args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

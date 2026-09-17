"""RSS white-list ingestion for the public industry-news portal."""
from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urlencode, urldefrag, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
import requests

from app import db
from app.models import Enterprise, IndustryNewsArticle, IndustryNewsSource, IndustryNewsSyncRun, Product

MAX_FEED_BYTES = 2 * 1024 * 1024
ALLOWED_CATEGORIES = ("政策法规", "产业趋势", "供应链", "技术创新", "企业动态", "出海与贸易")
RELEVANCE_THRESHOLD = 60
CHAIN_TERMS = {
    "原材料": ("原材料", "材料", "钢材", "铝材", "化工", "矿产"),
    "核心零部件": ("芯片", "晶圆", "零部件", "元器件", "电池", "传感器", "模组"),
    "设备": ("设备", "机床", "工业机器人", "自动化", "生产线"),
    "制造加工": ("制造", "工厂", "产线", "生产", "加工", "产能", "扩建"),
    "物流仓储": ("物流", "仓储", "运输", "供应链"),
    "下游应用": ("汽车", "新能源", "家电", "电子产品", "医疗器械"),
    "出口贸易": ("出口", "外贸", "跨境", "关税", "贸易"),
}
MANUFACTURING_TERMS = ("制造", "工业", "工厂", "供应链", "产能", "生产", "加工", "设备", "芯片", "材料", "零部件", "汽车", "新能源", "出口", "产线")
EXCLUDED_TERMS = ("明星", "综艺", "演唱会", "球赛", "电影", "电视剧", "游戏娱乐")
AUTHORITATIVE_SOURCES = ("政府", "工信", "协会", "证券", "公告", "新华社", "人民日报", "财经")
CATEGORY_QUERY_TERMS = {
    "政策法规": "制造业 政策 法规 工信部",
    "产业趋势": "制造业 产业趋势 产能 技术",
    "供应链": "制造业 供应链 原材料 物流",
    "技术创新": "制造业 技术创新 工业自动化 芯片",
    "企业动态": "制造企业 扩产 投资 订单 上市公司",
    "出海与贸易": "制造业 出口 外贸 关税 跨境",
}
CATEGORY_RELEVANCE_TERMS = {
    "政策法规": ("政策", "法规", "工信部", "规划", "补贴", "标准"),
    "产业趋势": ("趋势", "产能", "投资", "产业"),
    "供应链": ("供应链", "原材料", "交付", "物流", "库存"),
    "技术创新": ("技术", "研发", "创新", "自动化", "工艺"),
    "企业动态": ("企业", "公司", "集团", "扩产", "订单", "融资"),
    "出海与贸易": ("出口", "外贸", "跨境", "关税", "贸易"),
}


def newsapi_query_for_category(category: str | None) -> str:
    return CATEGORY_QUERY_TERMS.get(category or "", "制造业 供应链 工业 工厂")


def _news_text(item: dict) -> str:
    return _clean(f"{item.get('title') or ''} {item.get('description') or item.get('summary') or ''}", 4000)


def build_news_record(item: dict, category_hint: str | None = None) -> dict:
    """Normalize a NewsAPI item and associate it with public enterprise data."""
    title = _clean(str(item.get("title") or ""), 500)
    summary = _clean(str(item.get("description") or item.get("summary") or ""), 2000)
    url = urldefrag(str(item.get("url") or "").strip())[0]
    text = f"{title} {summary}".lower()
    matched_chain = [stage for stage, terms in CHAIN_TERMS.items() if any(term.lower() in text for term in terms)]
    manufacturing_hits = sum(term.lower() in text for term in MANUFACTURING_TERMS)
    score = min(100, (35 if matched_chain else 0) + min(20, manufacturing_hits * 5))
    source_name = str((item.get("source") or {}).get("name") or "NewsAPI 来源")[:120]
    if any(term in source_name for term in AUTHORITATIVE_SOURCES):
        score += 10
    if category_hint in CATEGORY_RELEVANCE_TERMS and any(term.lower() in text for term in CATEGORY_RELEVANCE_TERMS[category_hint]):
        score += 20
    if any(term in text for term in EXCLUDED_TERMS) and not matched_chain:
        score = max(0, score - 50)
    related_enterprise_ids = []
    related_product_ids = []
    for enterprise in Enterprise.query.filter(Enterprise.role == "enterprise").all():
        enterprise_terms = [enterprise.name, enterprise.tech_keywords or "", enterprise.business_scope or ""]
        if any(term and term.lower() in text for term in enterprise_terms):
            related_enterprise_ids.append(enterprise.id)
            products = Product.query.filter(Product.enterprise_id == enterprise.id).all()
            related_product_ids.extend(product.id for product in products if product.name and product.name.lower() in text)
    if related_enterprise_ids:
        score = min(100, score + 30)
    if matched_chain and any(term in text for term in ("企业", "公司", "集团", "工厂")):
        score = min(100, score + 5)
    digest = hashlib.sha256((url + "\n" + title + "\n" + summary).encode()).hexdigest()
    return {
        "title": title, "summary": summary, "source_url": url, "canonical_url": url,
        "source_name": source_name, "published_at": _parse_date(str(item.get("publishedAt") or item.get("published") or "")),
        "provider_article_id": str(item.get("url") or digest)[:255], "content_hash": digest,
        "category": category_hint if category_hint in ALLOWED_CATEGORIES else ("企业动态" if related_enterprise_ids else ("出海与贸易" if "出口贸易" in matched_chain else "产业趋势")),
        "content_excerpt": summary,
        "cover_image_url": str(item.get("urlToImage") or "")[:1000] if str(item.get("urlToImage") or "").startswith("https://") else None,
        "industry_tags": matched_chain + (["制造业"] if manufacturing_hits else []),
        "chain_stage": matched_chain[0] if matched_chain else None,
        "related_enterprise_ids": list(dict.fromkeys(related_enterprise_ids)),
        "related_product_ids": list(dict.fromkeys(related_product_ids)),
        "relevance_score": min(100, score), "relevance_status": "approved" if score >= RELEVANCE_THRESHOLD else "rejected",
        "is_published": score >= RELEVANCE_THRESHOLD, "is_demo": False,
    }


def persist_newsapi_articles(items: list[dict], category_hint: str | None = None) -> list[IndustryNewsArticle]:
    """Persist provider results before they are exposed, making detail URLs stable."""
    saved = []
    for item in items:
        record = build_news_record(item, category_hint=category_hint)
        if not record["source_url"] or not record["title"]:
            continue
        article = IndustryNewsArticle.query.filter(
            (IndustryNewsArticle.canonical_url == record["canonical_url"]) |
            (IndustryNewsArticle.content_hash == record["content_hash"])
        ).first()
        if article is None:
            article = IndustryNewsArticle(slug=_slug(record["title"], record["content_hash"]), **record)
            db.session.add(article)
        else:
            for key, value in record.items():
                if hasattr(article, key) and key not in {"is_published"}:
                    setattr(article, key, value)
        saved.append(article)
    db.session.commit()
    return saved


def fetch_newsapi(keyword: str = "制造业 OR manufacturing", page: int = 1, page_size: int = 12) -> dict:
    """Read-only NewsAPI adapter; credentials stay server-side."""
    api_key = (os.getenv("NEWSAPI_API_KEY") or "").strip()
    if not api_key:
        return {"articles": [], "totalResults": 0, "configured": False}
    query = urlencode({"q": keyword[:100], "language": "zh", "sortBy": "publishedAt", "page": page, "pageSize": page_size, "apiKey": api_key})
    response = requests.get("https://newsapi.org/v2/everything?" + query, headers={"User-Agent": "ChainYiPei-News/1.0"}, timeout=8)
    response.raise_for_status()
    if len(response.content) > MAX_FEED_BYTES:
        raise ValueError("NewsAPI 响应超过大小限制")
    data = response.json()
    if data.get("status") != "ok":
        raise ValueError("NewsAPI 暂时不可用")
    return data | {"configured": True}


def validate_feed_url(value: str) -> str:
    parsed = urlparse((value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("RSS 来源必须是 HTTPS 地址")
    host = parsed.hostname.rstrip(".").lower()
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = {item[4][0] for item in infos}
    except OSError as exc:
        raise ValueError("RSS 来源域名无法解析") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError("RSS 来源地址不可访问内网资源")
    return parsed._replace(fragment="").geturl()


def _clean(value: str | None, limit: int = 2000) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _text(element: ET.Element | None, names: tuple[str, ...]) -> str:
    if element is None:
        return ""
    for child in element.iter():
        if child.tag.rsplit("}", 1)[-1].lower() in names:
            return _clean("".join(child.itertext()))
    return ""


def parse_feed(payload: bytes, source: IndustryNewsSource) -> list[dict]:
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("RSS 响应超过大小限制")
    root = ET.fromstring(payload)
    entries = []
    for item in root.iter():
        if item.tag.rsplit("}", 1)[-1].lower() not in ("item", "entry"):
            continue
        title = _text(item, ("title",))
        link = _text(item, ("link",))
        if not link:
            for child in item:
                if child.tag.rsplit("}", 1)[-1].lower() == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        link = urldefrag(link.strip())[0]
        summary = _text(item, ("description", "summary", "content", "encoded"))
        published = _text(item, ("pubdate", "published", "updated"))
        if title and link.startswith("https://"):
            category = (source.allowed_categories or ["产业趋势"])[0]
            category = category if category in ALLOWED_CATEGORIES else "产业趋势"
            entries.append({"title": title, "summary": summary, "source_url": link, "published": published, "category": category})
    return entries


def _slug(title: str, digest: str) -> str:
    ascii_title = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (ascii_title[:150] or "industry-news") + "-" + digest[:10]


def _parse_date(value: str) -> datetime:
    # Keeping an absent/unfamiliar date as None makes source freshness explicit.
    from email.utils import parsedate_to_datetime
    try:
        parsed = parsedate_to_datetime(value)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        return datetime.utcnow()


def sync_source(source: IndustryNewsSource, opener=urlopen) -> IndustryNewsSyncRun:
    run = IndustryNewsSyncRun(source_id=source.id, status="running")
    db.session.add(run)
    try:
        url = validate_feed_url(source.feed_url)
        response = opener(Request(url, headers={"User-Agent": "ChainYiPei-News/1.0"}), timeout=8)
        payload = response.read(MAX_FEED_BYTES + 1)
        records = parse_feed(payload, source)
        run.fetched_count = len(records)
        for record in records:
            digest = hashlib.sha256((record["source_url"] + "\n" + record["title"] + "\n" + record["summary"]).encode()).hexdigest()
            existing = IndustryNewsArticle.query.filter(
                (IndustryNewsArticle.canonical_url == record["source_url"]) | (IndustryNewsArticle.content_hash == digest)
            ).first()
            if existing:
                run.duplicate_count = (run.duplicate_count or 0) + 1
                continue
            article = IndustryNewsArticle(
                slug=_slug(record["title"], digest), title=record["title"], summary=record["summary"],
                content_excerpt=record["summary"], category=record["category"], tags=[],
                source_name=source.name, source_url=record["source_url"], canonical_url=record["source_url"],
                published_at=_parse_date(record["published"]), content_hash=digest,
                is_published=bool(source.auto_publish), is_demo=False,
            )
            db.session.add(article)
            run.created_count = (run.created_count or 0) + 1
        source.last_synced_at = datetime.utcnow(); source.last_sync_status = "success"; source.last_error = None
        run.status = "success"
    except Exception as exc:
        source.last_sync_status = "failed"; source.last_error = str(exc)[:500]; run.status = "failed"; run.error_message = str(exc)[:500]
    finally:
        run.finished_at = datetime.utcnow()
        db.session.commit()
    return run

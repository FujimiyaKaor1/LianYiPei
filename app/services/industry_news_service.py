"""RSS white-list ingestion for the public industry-news portal."""
from __future__ import annotations

import hashlib
import html
import ipaddress
import re
import socket
from datetime import datetime, timezone
from urllib.parse import urldefrag, urlparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from app import db
from app.models import IndustryNewsArticle, IndustryNewsSource, IndustryNewsSyncRun

MAX_FEED_BYTES = 2 * 1024 * 1024
ALLOWED_CATEGORIES = ("政策法规", "产业趋势", "供应链", "技术创新", "企业动态", "出海与贸易")


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

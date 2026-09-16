from datetime import datetime

from app import db
from app.models import IndustryNewsArticle, IndustryNewsSource
from app.services.industry_news_service import parse_feed, validate_feed_url


def test_public_news_hides_unpublished_and_paginates(client, _db):
    for index in range(205):
        db.session.add(IndustryNewsArticle(
            slug=f"news-{index}", title=f"制造业资讯 {index}", summary="摘要",
            category="产业趋势", source_name="测试来源", source_url=f"https://example.com/{index}",
            canonical_url=f"https://example.com/{index}", content_hash=f"{index:064d}",
            published_at=datetime(2026, 1, 1), is_published=index != 204,
        ))
    db.session.commit()
    response = client.get("/api/public/industry-news?page=2&per_page=20")
    data = response.get_json()
    assert response.status_code == 200
    assert data["total"] == 204
    assert len(data["items"]) == 20
    assert all("feed_url" not in item for item in data["items"])


def test_feed_parser_and_security(monkeypatch):
    source = IndustryNewsSource(name="官方来源", feed_url="https://example.com/feed", allowed_categories=["政策法规"])
    payload = '''<rss><channel><item><title><![CDATA[政策 <script>alert(1)</script>]]></title><link>https://example.com/a#x</link><description><![CDATA[摘要 <b>内容</b>]]></description></item></channel></rss>'''.encode()
    items = parse_feed(payload, source)
    assert items[0]["title"] == "政策"
    assert items[0]["summary"] == "摘要 内容"
    assert items[0]["category"] == "政策法规"
    monkeypatch.setattr("app.services.industry_news_service.socket.getaddrinfo", lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))])
    try:
        validate_feed_url("https://localhost/feed")
    except ValueError as exc:
        assert "内网" in str(exc)
    else:
        raise AssertionError("内网 RSS 地址必须被拒绝")


def test_news_source_management_requires_admin(client, _db):
    assert client.get("/admin/api/news/sources").status_code == 302

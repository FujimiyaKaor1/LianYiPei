from datetime import datetime

from app import db
from app.models import Enterprise, IndustryNewsArticle, IndustryNewsSource
from app.services.industry_news_service import (
    build_news_record,
    newsapi_query_for_category,
    parse_feed,
    validate_feed_url,
)


def test_public_news_hides_unpublished_and_paginates(client, _db):
    for index in range(205):
        db.session.add(IndustryNewsArticle(
            slug=f"news-{index}", title=f"制造业资讯 {index}", summary="摘要",
            category="产业趋势", source_name="测试来源", source_url=f"https://example.com/{index}",
            canonical_url=f"https://example.com/{index}", content_hash=f"{index:064d}",
            published_at=datetime(2026, 1, 1), is_published=index != 204, relevance_score=80,
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


def test_newsapi_record_is_persistable_and_related_to_enterprise(_db):
    enterprise = Enterprise(name="成都芯片制造有限公司", role="enterprise", tech_keywords="芯片,晶圆", business_scope="芯片制造")
    db.session.add(enterprise)
    db.session.commit()
    record = build_news_record({
        "title": "成都芯片制造有限公司扩建晶圆产线",
        "description": "企业宣布新增芯片制造产能，完善供应链布局。",
        "url": "https://example.com/news/chip-1",
        "publishedAt": "2026-09-15T08:00:00Z",
        "source": {"name": "行业媒体"},
    })
    assert record["relevance_score"] >= 70
    assert enterprise.id in record["related_enterprise_ids"]
    assert record["chain_stage"] in {"核心零部件", "制造加工", "上游原材料", "下游应用"}


def test_irrelevant_news_is_not_publishable(_db):
    record = build_news_record({
        "title": "明星发布全新综艺节目",
        "description": "娱乐新闻和节目资讯。",
        "url": "https://example.com/news/entertainment",
        "publishedAt": "2026-09-15T08:00:00Z",
        "source": {"name": "娱乐媒体"},
    })
    assert record["relevance_score"] < 60
    assert record["is_published"] is False


def test_policy_category_relevance_is_publishable_when_policy_terms_match(_db):
    record = build_news_record({
        "title": "工信部发布制造业设备更新政策",
        "description": "政策支持工业设备和产线升级。",
        "url": "https://example.com/news/policy-score",
        "publishedAt": "2026-09-15T08:00:00Z",
        "source": {"name": "工信部"},
    }, category_hint="政策法规")
    assert record["relevance_score"] >= 60
    assert record["is_published"] is True


def test_newsapi_list_persists_items_and_detail_uses_same_slug(client, _db, monkeypatch):
    monkeypatch.setattr("app.routes.api.fetch_newsapi", lambda **kwargs: {"status": "ok", "totalResults": 1, "articles": [{
        "title": "制造企业扩建芯片产线", "description": "企业新增制造产能并完善供应链。",
        "url": "https://example.com/news/persisted", "publishedAt": "2026-09-15T08:00:00Z",
        "source": {"name": "行业协会"},
    }]})
    response = client.get("/api/public/industry-news")
    data = response.get_json()
    assert response.status_code == 200
    assert len(data["items"]) == 1
    assert data["items"][0]["slug"]
    detail = client.get(f"/api/public/industry-news/{data['items'][0]['slug']}")
    assert detail.status_code == 200
    article = detail.get_json()["article"]
    assert article["title"] == "制造企业扩建芯片产线"
    assert article["chain_stage"]


def test_category_filter_changes_newsapi_query_and_results(client, _db, monkeypatch):
    captured = {}

    def fake_newsapi(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "totalResults": 1, "articles": [{
            "title": "工信部发布制造业设备更新政策", "description": "政策支持工业设备和产线升级。",
            "url": "https://example.com/news/policy", "publishedAt": "2026-09-15T08:00:00Z",
            "source": {"name": "工信部"},
        }]}

    monkeypatch.setattr("app.routes.api.fetch_newsapi", fake_newsapi)
    assert "政策" in newsapi_query_for_category("政策法规")
    response = client.get("/api/public/industry-news?category=政策法规")
    data = response.get_json()
    assert response.status_code == 200
    assert captured["keyword"] == newsapi_query_for_category("政策法规")
    assert data["items"][0]["category"] == "政策法规"
    assert data["items"][0]["slug"]


def test_low_relevance_legacy_news_is_excluded_from_public_filters(client, _db):
    db.session.add(IndustryNewsArticle(
        slug="legacy-noise", title="娱乐节目发布新消息", summary="与制造业无关",
        category="产业趋势", source_name="无关来源", source_url="https://example.com/noise",
        canonical_url="https://example.com/noise", content_hash="a" * 64,
        published_at=datetime(2026, 1, 1), is_published=True, relevance_score=0,
    ))
    db.session.commit()
    data = client.get("/api/public/industry-news?category=产业趋势").get_json()
    assert all(item["slug"] != "legacy-noise" for item in data["items"])

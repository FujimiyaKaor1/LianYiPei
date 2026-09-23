from datetime import datetime, timedelta

from app.models import Inquiry, Quote
from app.applications.fulfillment.services.quote_pool import QuotePoolManager
from app.applications.fulfillment.services.intent_quote_service import IntentQuoteService


def test_price_index_does_not_invent_history_for_cold_start(_db, test_enterprise):
    index = QuotePoolManager().calculate_price_index("不存在的产品")

    assert index["median_price"] is None
    assert index["sample_count"] == 0
    assert index["history"] == []


def test_price_index_history_contains_only_persisted_quotes(_db, test_enterprise, test_supplier):
    inquiry = Inquiry(
        poster_id=test_enterprise.id,
        buyer_id=test_enterprise.id,
        direction="demand",
        product_name="连接器",
        status="open",
    )
    _db.session.add(inquiry)
    _db.session.flush()
    for price, created_at in ((10.0, datetime.utcnow() - timedelta(days=1)), (12.0, datetime.utcnow())):
        _db.session.add(Quote(
            inquiry_id=inquiry.id,
            supplier_id=test_supplier.id,
            product_name="连接器",
            price=price,
            status="active",
            created_at=created_at,
        ))
    _db.session.commit()

    index = QuotePoolManager().calculate_price_index("连接器")

    assert index["sample_count"] == 2
    assert [item["price"] for item in index["history"]] == [10.0, 12.0]
    assert all("sample_count" in item for item in index["history"])


def test_quote_suggestion_does_not_invent_price_on_cold_start(_db, test_supplier, monkeypatch):
    monkeypatch.setattr(
        "app.services.quote_pool.get_price_index",
        lambda product_name: {"median_price": None, "sample_count": 0, "history": [], "is_cold_start": True},
    )

    suggestion = IntentQuoteService().generate_ai_price_suggestion(
        seller_id=test_supplier.id,
        product_name="没有历史报价的产品",
        quantity=100,
    )

    assert suggestion["suggested_price"] is None
    assert suggestion["price_range"] is None
    assert suggestion["generation_mode"] == "database_rules"
    assert suggestion["basis"] == "没有已持久化的有效报价样本，无法估算价格"


def test_quote_suggestion_does_not_invent_capacity_or_delivery(_db, test_supplier, monkeypatch):
    test_supplier.capacity = None
    test_supplier.max_capacity = None
    _db.session.commit()
    monkeypatch.setattr(
        "app.services.quote_pool.get_price_index",
        lambda product_name: {"median_price": 120.0, "sample_count": 3, "history": [], "is_cold_start": False},
    )

    suggestion = IntentQuoteService().generate_ai_price_suggestion(
        seller_id=test_supplier.id,
        product_name="有历史报价的产品",
        quantity=100,
    )

    assert suggestion["suggested_price"] is not None
    assert suggestion["delivery_estimate"] == "无法根据已登记产能估算"
    assert suggestion["capacity_available"] is None
    assert suggestion["capacity_ratio"] is None
    assert "产能数据未登记" in suggestion["basis"]

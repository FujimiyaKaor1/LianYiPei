from datetime import datetime, timedelta

from app.models import Inquiry, Quote
from app.applications.fulfillment.services.quote_pool import QuotePoolManager


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

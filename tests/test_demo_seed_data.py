from app.models import (
    Alert,
    BusinessCard,
    ChatMessage,
    Enterprise,
    FavoriteSupplier,
    Inquiry,
    InquiryChat,
    IntentQuote,
    MatchRecord,
    Message,
    PriceIndex,
    Product,
    Quote,
    RecruitmentTask,
    Transaction,
)
from scripts.seed.seed_demo_full_flow import DEMO_ENTERPRISE_NAMES, seed_demo_data


def test_seed_demo_data_creates_complete_idempotent_story(app, _db):
    first = seed_demo_data(app)
    second = seed_demo_data(app)

    assert first == second
    assert first["enterprises"] >= 30
    assert first["products"] >= 70
    assert first["inquiries"] >= 16
    assert first["quotes"] >= 28
    assert first["transactions"] >= 8
    assert first["match_feedbacks"] >= 12
    assert first["match_records"] >= 10
    assert first["inquiry_chats"] >= 8
    assert first["chat_messages"] >= 30
    assert first["intent_quotes"] >= 6
    assert first["business_cards"] >= 4
    assert first["favorite_suppliers"] >= 10
    assert first["recruitment_tasks"] >= 6
    assert first["alerts"] >= 14
    assert first["messages"] >= 30
    assert first["price_indices"] >= 10

    demo_enterprises = Enterprise.query.filter(
        Enterprise.name.in_(DEMO_ENTERPRISE_NAMES)
    ).all()
    assert len(demo_enterprises) == first["enterprises"]

    assert Product.query.count() == first["products"]
    assert Inquiry.query.count() == first["inquiries"]
    assert Inquiry.query.filter(Inquiry.seller_id.is_(None)).count() == 0
    assert Quote.query.count() == first["quotes"]
    assert Transaction.query.count() == first["transactions"]
    assert MatchRecord.query.count() == first["match_records"]
    assert InquiryChat.query.count() == first["inquiry_chats"]
    assert ChatMessage.query.count() == first["chat_messages"]
    assert IntentQuote.query.filter_by(status="accepted").count() >= 3
    assert BusinessCard.query.count() == first["business_cards"]
    assert FavoriteSupplier.query.count() == first["favorite_suppliers"]
    assert RecruitmentTask.query.count() == first["recruitment_tasks"]
    assert Message.query.count() == first["messages"]
    assert PriceIndex.query.count() == first["price_indices"]

    red_alert = Alert.query.filter_by(level="red", is_active=True).first()
    assert red_alert is not None
    assert red_alert.analysis_data["risk_reason"]
    assert red_alert.analysis_data["impact_scope"]
    assert red_alert.workflow_history

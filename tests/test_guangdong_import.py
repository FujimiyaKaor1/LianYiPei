from app.models import Enterprise, Product
from app.services.chain_xiaoyi.orchestrator import _data_freshness_view, _match
from scripts.seed.import_guangdong_data import import_guangdong_data


def test_public_directory_import_is_incremental_and_never_fakes_private_fields(_db, test_enterprise, tmp_path):
    source = tmp_path / "guangdong.csv"
    source.write_text("企业名称,省份,城市,经营范围\n可信电子制造有限公司,广东,东莞,电子连接器制造\n", encoding="utf-8-sig")

    inserted, skipped_non_mfg, skipped_bad = import_guangdong_data(source)

    assert (inserted, skipped_non_mfg, skipped_bad) == (1, 0, 0)
    assert Enterprise.query.get(test_enterprise.id) is not None
    candidate = Enterprise.query.filter_by(name="可信电子制造有限公司").one()
    assert candidate.contact is None
    assert candidate.phone is None
    assert candidate.address is None
    assert candidate.registered_capital is None
    assert candidate.credit_score == 0
    assert candidate.password_hash is None
    trust = candidate.extras["trust_profile"]
    assert trust["claim_status"] == "unclaimed"
    assert trust["contact_authorized"] is False
    assert trust["sources"][0]["is_mock"] is False
    assert trust["sources"][0]["source_url"] is None
    assert trust["sources"][0]["confidence"] == 0.6
    assert trust["sources"][0]["authorization"] == "public_directory_only"
    assert set(candidate.extras["data_evidence"]) >= {"name", "province", "city", "business_scope"}
    assert candidate.extras["data_evidence"]["name"]["source_type"] == "public_directory"
    assert "credit_score" in candidate.extras["unverified_fields"]
    assert Product.query.filter_by(enterprise_id=candidate.id).count() == 0


def test_public_directory_imports_only_explicit_product_capabilities(_db, tmp_path):
    source = tmp_path / "guangdong-with-products.csv"
    source.write_text(
        "企业名称,省份,城市,经营范围,主营产品\n"
        "连接器制造有限公司,广东,深圳,电子连接器制造,精密连接器;线束组件\n",
        encoding="utf-8-sig",
    )

    inserted, skipped_non_mfg, skipped_bad = import_guangdong_data(source)

    assert (inserted, skipped_non_mfg, skipped_bad) == (1, 0, 0)
    enterprise = Enterprise.query.filter_by(name="连接器制造有限公司").one()
    assert [row.name for row in Product.query.filter_by(enterprise_id=enterprise.id).order_by(Product.name)] == [
        "精密连接器",
        "线束组件",
    ]


def test_imported_product_is_searchable_but_not_contact_eligible(app, _db, tmp_path, test_enterprise):
    source = tmp_path / "guangdong-searchable.csv"
    source.write_text(
        "企业名称,省份,城市,经营范围,主营产品\n"
        "公开连接器工厂,广东,东莞,电子连接器制造,精密连接器\n",
        encoding="utf-8-sig",
    )
    import_guangdong_data(source)

    with app.app_context():
        result, _provider = _match(
            {"product": "精密连接器", "region": "广东", "quantity": 100, "raw_text": "找广东精密连接器"},
            test_enterprise.id,
            explain_with_model=False,
        )

    row = next(item for item in result["results"] if item["name"] == "公开连接器工厂")
    assert row["trust_profile"]["claim_status"] == "unclaimed"
    assert row["contact_eligible"] is False
    assert row["data_freshness"]["status"] == "fresh"


def test_data_freshness_is_explicit_and_stale_records_are_not_latest(app):
    with app.app_context():
        fresh = _data_freshness_view("2026-09-17T00:00:00")
        stale = _data_freshness_view("2025-01-01T00:00:00")
        unknown = _data_freshness_view(None)

    assert fresh["status"] == "fresh"
    assert stale["status"] == "stale"
    assert stale["is_latest"] is False
    assert unknown["status"] == "unknown"
    assert unknown["is_latest"] is False

from scripts.seed.enrich_tianxiagongchang_data import (
    build_demo_metrics,
    build_product_names,
    build_demo_coordinates,
    classify_industry_code,
    merge_source_extras,
)


def test_industry_code_is_derived_from_source_text():
    assert classify_industry_code("电子元器件、PCB电路板", "电子设备制造") == "C39"
    assert classify_industry_code("五金加工、模具", "金属制品制造") == "C33"
    assert classify_industry_code("未知行业", "") == "C34"


def test_demo_metrics_are_stable_and_coherent():
    first = build_demo_metrics(2424765, "电子元器件,PCB电路板")
    second = build_demo_metrics(2424765, "电子元器件,PCB电路板")

    assert first == second
    assert 30 <= first["capacity"] <= 95
    assert first["current_orders"] <= first["max_capacity"]
    assert 70 <= first["credit_score"] <= 96


def test_product_names_are_nonempty_and_deduplicated():
    names = build_product_names("五金加工,模具制造", "C33", 2424765)
    assert 2 <= len(names) <= 4
    assert len(names) == len(set(names))
    assert all(names)


def test_demo_coordinates_are_stable_and_in_china_bounds():
    first = build_demo_coordinates("广东省", "东莞市", 2424765)
    assert first == build_demo_coordinates("广东省", "东莞市", 2424765)
    assert 73 <= first[0] <= 135
    assert 3 <= first[1] <= 54


def test_source_extras_preserve_existing_values_and_mark_generated_fields():
    merged = merge_source_extras(
        {"source": "tianxiagongchang.com", "custom": "keep"},
        {"isForeignTrade": 2, "isSpecialized": True},
    )
    assert merged["custom"] == "keep"
    assert merged["source_flags"]["is_foreign_trade"] is True
    assert merged["source_flags"]["is_specialized"] is True
    assert "capacity" in merged["synthetic_fields"]

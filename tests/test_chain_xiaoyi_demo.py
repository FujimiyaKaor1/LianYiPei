from pathlib import Path

import pytest

from scripts.verify.chain_xiaoyi_demo import (
    material_demo_summary,
    read_api_key_from_hidden_input,
    resolve_intent_provider,
    validate_material_paths,
)


def test_validate_material_paths_accepts_supported_files(tmp_path):
    first = tmp_path / "采购需求.xlsx"
    second = tmp_path / "技术要求.pdf"
    first.write_bytes(b"xlsx")
    second.write_bytes(b"pdf")

    result = validate_material_paths([str(first), str(second)])

    assert result == [first, second]


def test_validate_material_paths_rejects_missing_and_unsupported_files(tmp_path):
    missing = tmp_path / "missing.xlsx"
    unsupported = tmp_path / "需求.txt"
    unsupported.write_text("product", encoding="utf-8")

    with pytest.raises(ValueError, match="材料文件不存在"):
        validate_material_paths([str(missing)])
    with pytest.raises(ValueError, match="仅支持"):
        validate_material_paths([str(unsupported)])


def test_validate_material_paths_rejects_empty_list():
    with pytest.raises(ValueError, match="至少提供一个"):
        validate_material_paths([])


def test_material_demo_summary_preserves_scan_and_field_evidence_without_file_content():
    payload = {
        "file": {
            "id": 7,
            "filename": "采购需求.csv",
            "scan_status": "clean",
            "preview": {"security_scan": {"status": "clean", "engine": "signature-and-archive"}},
        },
        "draft": {
            "missing_required": [],
            "fields": {
                "product": {"value": "精密连接器", "evidence": {"row": 2, "column": "产品"}},
                "quantity": {"value": 2000, "evidence": {"row": 2, "column": "数量"}},
            },
        },
    }

    summary = material_demo_summary(payload)

    assert summary == {
        "id": 7,
        "filename": "采购需求.csv",
        "scan_status": "clean",
        "scan_engine": "signature-and-archive",
        "missing_required": [],
        "fields": {
            "product": {"value": "精密连接器", "evidence": {"row": 2, "column": "产品"}},
            "quantity": {"value": 2000, "evidence": {"row": 2, "column": "数量"}},
        },
    }


def test_resolve_intent_provider_uses_material_confirmation_model_status():
    """A material draft has no chat confidence field, but its confirmation does."""
    assert resolve_intent_provider(
        {"model_status": {"active_provider": "deepseek"}},
        {"product": "连接器"},
    ) == "deepseek"
    assert resolve_intent_provider(
        {"model_status": {"active_provider": "rules"}},
        {"confidence": "local"},
    ) == "local"
    assert resolve_intent_provider({}, {}) is None


def test_read_api_key_from_hidden_input_rejects_empty_value(monkeypatch):
    monkeypatch.setattr("scripts.verify.chain_xiaoyi_demo.getpass.getpass", lambda _prompt: "  ")
    with pytest.raises(ValueError, match="有效 DeepSeek API key"):
        read_api_key_from_hidden_input()


def test_read_api_key_from_hidden_input_trims_key_without_logging(monkeypatch):
    monkeypatch.setattr("scripts.verify.chain_xiaoyi_demo.getpass.getpass", lambda _prompt: "  secret  ")
    assert read_api_key_from_hidden_input() == "secret"

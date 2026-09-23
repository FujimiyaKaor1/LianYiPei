import pytest

from scripts.verify.live_chain_xiaoyi_smoke import normalize_base_url, run_live_smoke


def test_normalize_base_url_keeps_only_http_origin():
    assert normalize_base_url("https://agent.example.test/some/path") == "https://agent.example.test"


def test_live_smoke_requires_explicit_buyer_credentials():
    with pytest.raises(ValueError, match="专用验收采购账号"):
        run_live_smoke(
            "http://127.0.0.1:5050",
            buyer_name="",
            buyer_password="",
        )


@pytest.mark.parametrize(
    "value",
    [
        "agent.example.test",
        "https://user:password@agent.example.test",
        "https://agent.example.test/?token=secret",
        "https://agent.example.test/#secret",
    ],
)
def test_normalize_base_url_rejects_unsafe_values(value):
    with pytest.raises(ValueError):
        normalize_base_url(value)

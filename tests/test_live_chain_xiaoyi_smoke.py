import pytest

from scripts.verify.live_chain_xiaoyi_smoke import normalize_base_url


def test_normalize_base_url_keeps_only_http_origin():
    assert normalize_base_url("https://agent.example.test/some/path") == "https://agent.example.test"


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

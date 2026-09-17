"""Provider configuration for Chain XiaoYi.

Providers are intentionally not called until explicitly enabled. This keeps a
fresh installation honest and makes the rule-engine fallback deterministic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelStatus:
    local_enabled: bool
    cloud_enabled: bool
    local_model: str
    cloud_provider: str
    cloud_model: str
    configured_provider: str
    active_provider: str

    def to_dict(self) -> dict:
        return {
            "local_enabled": self.local_enabled,
            "cloud_enabled": self.cloud_enabled,
            "local_model": self.local_model,
            "cloud_provider": self.cloud_provider,
            "cloud_model": self.cloud_model,
            "configured_provider": self.configured_provider,
            "active_provider": self.active_provider,
            "is_configured": self.active_provider != "rules",
            "message": "智能模型尚未配置，当前使用基础规则" if self.configured_provider == "rules" else "已检测到模型配置，但模型 Provider 尚未启用，当前使用基础规则",
        }


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def get_model_status() -> ModelStatus:
    local_model = (os.getenv("CHAINXIAOYI_LOCAL_MODEL") or os.getenv("BIZMIND_OLLAMA_MODEL") or "").strip()
    local_enabled = _enabled("CHAINXIAOYI_LOCAL_ENABLED") and bool(local_model)
    cloud_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip()
    cloud_enabled = _enabled("CHAINXIAOYI_CLOUD_ENABLED") and bool(cloud_key)
    routing_mode = os.getenv("CHAINXIAOYI_ROUTING_MODE", "local_first").strip().lower()
    # Provider calls remain deliberately disabled until their adapters are
    # implemented and reviewed. Environment variables alone must not make the
    # UI claim that an LLM has processed a request.
    configured_provider = "deepseek" if routing_mode == "cloud_first" and cloud_enabled else "local" if local_enabled else "deepseek" if cloud_enabled else "rules"
    active_provider = "rules"
    return ModelStatus(
        local_enabled=local_enabled,
        cloud_enabled=cloud_enabled,
        local_model=local_model,
        cloud_provider="deepseek",
        cloud_model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        configured_provider=configured_provider,
        active_provider=active_provider,
    )

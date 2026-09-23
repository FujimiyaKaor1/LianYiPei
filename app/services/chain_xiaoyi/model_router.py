"""Provider configuration for Chain XiaoYi.

Providers are intentionally not called until explicitly enabled. This keeps a
fresh installation honest and makes the rule-engine fallback deterministic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from app.services.deepseek_client import DEFAULT_DEEPSEEK_MODEL


@dataclass(frozen=True)
class ModelStatus:
    local_enabled: bool
    cloud_enabled: bool
    local_model: str
    cloud_provider: str
    cloud_model: str
    cloud_required: bool
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
            "cloud_required": self.cloud_required,
            "is_configured": self.active_provider in {"deepseek", "local"},
            "message": (
                "生产环境要求 DeepSeek，但当前未配置或不可用"
                if self.active_provider == "unavailable"
                else "智能模型尚未配置，当前使用基础规则"
                if self.active_provider == "rules"
                else "当前使用 DeepSeek 模型，失败将停止本轮执行，不会降级为规则结果"
                if self.active_provider == "deepseek" and self.cloud_required
                else f"当前使用 {self.active_provider} 模型，失败时自动降级为基础规则"
            ),
        }


def _enabled(name: str) -> bool:
    return os.getenv(name, "false").strip().lower() in {"1", "true", "yes", "on"}


def _credential_present(value: str | None) -> bool:
    """Reject template prompts so a copied deployment sample cannot route to a fake model."""
    candidate = str(value or "").strip().lower()
    if not candidate:
        return False
    return not any(
        marker in candidate
        for marker in (
            "placeholder",
            "change-me",
            "changeme",
            "replace-me",
            "your-",
            "your_",
            "请填写",
            "请使用",
            "请从",
            "密钥管理系统",
        )
    )


def cloud_model_required() -> bool:
    """Whether production must fail closed instead of using rule fallback.

    Prefer the Flask config when an application context exists so tests and
    deployment overlays can set the policy without mutating process globals;
    the environment remains the standalone-worker fallback.
    """
    try:
        from flask import current_app

        configured = current_app.config.get("CHAINXIAOYI_CLOUD_REQUIRED")
        if configured is not None:
            return bool(configured)
    except (ImportError, RuntimeError):
        pass
    return _enabled("CHAINXIAOYI_CLOUD_REQUIRED")


def cloud_model_enabled() -> bool:
    """Return whether the DeepSeek adapter may be used.

    A key injected by a secret manager is an explicit opt-in in production.
    ``CHAINXIAOYI_CLOUD_ENABLED=false`` remains an emergency kill switch, but
    operators no longer need to maintain a second flag merely because a key
    was mounted into the process environment.  This also keeps a missing key
    truthful: the model is never reported as configured without credentials.
    """
    if not _credential_present(os.getenv("DEEPSEEK_API_KEY")):
        return False
    raw_flag = os.getenv("CHAINXIAOYI_CLOUD_ENABLED")
    if raw_flag is None or not raw_flag.strip():
        return True
    return _enabled("CHAINXIAOYI_CLOUD_ENABLED")


def get_model_status() -> ModelStatus:
    local_model = (os.getenv("CHAINXIAOYI_LOCAL_MODEL") or os.getenv("BIZMIND_OLLAMA_MODEL") or "").strip()
    local_enabled = _enabled("CHAINXIAOYI_LOCAL_ENABLED") and bool(local_model)
    cloud_enabled = cloud_model_enabled()
    cloud_required = cloud_model_required()
    routing_mode = os.getenv("CHAINXIAOYI_ROUTING_MODE", "local_first").strip().lower()
    configured_provider = (
        "unavailable"
        if cloud_required and not cloud_enabled
        else "deepseek" if routing_mode == "cloud_first" and cloud_enabled
        else "local" if local_enabled
        else "deepseek" if cloud_enabled
        else "rules"
    )
    # Adapters are implemented in the orchestrator; expose the selected
    # provider so requests can use it instead of silently claiming rule-only
    # execution. Development may fall back to deterministic parsing; a
    # production cloud-required policy is enforced at the execution boundary.
    active_provider = configured_provider
    return ModelStatus(
        local_enabled=local_enabled,
        cloud_enabled=cloud_enabled,
        local_model=local_model,
        cloud_provider="deepseek",
        cloud_model=os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL).strip() or DEFAULT_DEEPSEEK_MODEL,
        cloud_required=cloud_required,
        configured_provider=configured_provider,
        active_provider=active_provider,
    )

"""Deprecated import shim. All cloud calls are routed to DeepSeek."""
from app.services.deepseek_client import (
    DEFAULT_DEEPSEEK_BASE_URL,
    DEFAULT_DEEPSEEK_MODEL,
    DeepSeekChatModel,
    create_deepseek_chat_model_from_env,
)

DEFAULT_MIMO_BASE_URL = DEFAULT_DEEPSEEK_BASE_URL
DEFAULT_MIMO_MODEL = DEFAULT_DEEPSEEK_MODEL
MiMoChatModel = DeepSeekChatModel


def create_mimo_chat_model_from_env() -> DeepSeekChatModel:
    """Compatibility alias for older imports; reads only DEEPSEEK_* settings."""
    return create_deepseek_chat_model_from_env()

"""Production model adapters — local HF/path first; HTTP optional."""

from __future__ import annotations

from mom.adapters.anthropic_chat import AnthropicChatModel
from mom.adapters.local_chat import LocalChatModel
from mom.adapters.local_embed import LocalEmbedModel
from mom.adapters.local_router import LocalRouterModel
from mom.adapters.openai_chat import OpenAIChatModel
from mom.adapters.openai_embed import OpenAIEmbedModel
from mom.adapters.openai_router import OpenAIRouterModel

__all__ = [
    "AnthropicChatModel",
    "LocalChatModel",
    "LocalEmbedModel",
    "LocalRouterModel",
    "OpenAIChatModel",
    "OpenAIEmbedModel",
    "OpenAIRouterModel",
]

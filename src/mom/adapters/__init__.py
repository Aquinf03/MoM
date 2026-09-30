"""Production model adapters — real HTTP backends behind Model.run."""

from __future__ import annotations

from mom.adapters.anthropic_chat import AnthropicChatModel
from mom.adapters.openai_chat import OpenAIChatModel
from mom.adapters.openai_embed import OpenAIEmbedModel
from mom.adapters.openai_router import OpenAIRouterModel

__all__ = [
    "AnthropicChatModel",
    "OpenAIChatModel",
    "OpenAIEmbedModel",
    "OpenAIRouterModel",
]

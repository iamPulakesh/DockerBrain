"""LLM provider abstraction layer."""

from __future__ import annotations

from dockerbrain.config.settings import LLMConfig
from dockerbrain.llm.base import LLMProvider
from dockerbrain.llm.anthropic_provider import AnthropicProvider
from dockerbrain.llm.openai_compat_provider import OpenAICompatProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAICompatProvider,
}


def get_provider(config: LLMConfig) -> LLMProvider:
    """Return the correct LLMProvider instance for the given config."""
    provider_cls = _PROVIDERS[config.provider]
    return provider_cls(config)


__all__ = ["get_provider", "LLMProvider"]

"""LLM-specific error types."""

from __future__ import annotations


class LLMConfigError(Exception):
    """Raised when the LLM configuration is invalid or incomplete."""


class MissingAPIKeyError(LLMConfigError):
    """Raised when the API key is missing for a provider that requires one."""


class UnsupportedProviderError(LLMConfigError):
    """Raised when the provider name is not recognized."""


class SDKNotInstalledError(LLMConfigError):
    """Raised when the required SDK for a provider is not installed."""

"""LLMConfig dataclass, provider defaults, and configuration loading."""

from __future__ import annotations

from dataclasses import dataclass

from dockerbrain.config.rc_file import read_rc_section
from dockerbrain.ui.cli.console import get_console
from dockerbrain.ui.cli.panels import print_missing_key_error

_PROVIDER_BASE_URLS: dict[str, str] = {
    "chatgpt": "https://api.openai.com/v1",
    "anthropic": "",  # uses anthropic SDK
}

_VALID_PROVIDERS = set(_PROVIDER_BASE_URLS.keys())


@dataclass
class LLMConfig:
    """Resolved LLM configuration."""

    provider: str
    model: str
    api_key: str
    base_url: str


def load_llm_config() -> LLMConfig:
    """Resolve LLM configuration from .dockerbrainrc only."""
    console = get_console()

    rc = read_rc_section("llm")
    provider = rc.get("provider")
    if not provider:
        raise ValueError("Missing 'provider' in config! Run 'dockerb config' or set it in ~/.dockerbrain/.dockerbrainrc")
    provider = provider.lower().strip()

    if provider not in _VALID_PROVIDERS:
        console.print(
            f"[red bold]Unknown LLM provider:[/] [cyan]{provider}[/]\n"
            f"[dim]Valid providers: {', '.join(sorted(_VALID_PROVIDERS))}[/]"
        )
        raise ValueError(f"Unknown LLM provider: {provider}")

    model = rc.get("model")
    if not model:
        raise ValueError("Missing 'model' in config! Please set it in ~/.dockerbrain/.dockerbrainrc")
    base_url = rc.get("base_url") or _PROVIDER_BASE_URLS[provider]
    api_key = rc.get("api_key") or ""

    if not api_key:
        print_missing_key_error()
        raise ValueError("Missing API key! Run 'dockerb config' to set up API key.")

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )

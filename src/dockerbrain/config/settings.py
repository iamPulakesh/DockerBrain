"""LLMConfig dataclass, provider defaults, and configuration loading."""

from __future__ import annotations

from dataclasses import dataclass

from dockerbrain.config.rc_file import read_rc_section
from dockerbrain.ui.cli.console import get_console
from dockerbrain.ui.cli.panels import print_missing_key_error

_PROVIDER_DEFAULTS: dict[str, dict[str, str]] = {
    "gemini": {
        "model": "gemini-3.1-flash-lite-preview",
        "base_url": "",  # uses google-genai SDK
    },
    "chatgpt": {
        "model": "gpt-5.4-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "claude": {
        "model": "claude-sonnet-4-6",
        "base_url": "",  # uses anthropic SDK
    },
    "groq": {
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434/v1",
    },
}

_VALID_PROVIDERS = set(_PROVIDER_DEFAULTS.keys())


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
    provider = (rc.get("provider") or "gemini").lower().strip()

    if provider not in _VALID_PROVIDERS:
        console.print(
            f"[red bold]Unknown LLM provider:[/] [cyan]{provider}[/]\n"
            f"[dim]Valid providers: {', '.join(sorted(_VALID_PROVIDERS))}[/]"
        )
        raise SystemExit(1)

    defaults = _PROVIDER_DEFAULTS[provider]
    model = rc.get("model") or defaults["model"]
    base_url = rc.get("base_url") or defaults["base_url"]
    api_key = rc.get("api_key") or ""

    if not api_key and provider != "ollama":
        print_missing_key_error()
        raise SystemExit(1)

    if provider == "ollama" and not api_key:
        api_key = "ollama"

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

console = Console()

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


def _read_rc_section(section: str = "llm") -> dict[str, str]:
    """Read a section from ~/.dockerbrain/.dockerbrainrc (simple TOML-like INI parser)."""
    rc_path = Path.home() / ".dockerbrain" / ".dockerbrainrc"
    if not rc_path.exists():
        return {}

    data: dict[str, str] = {}
    in_section = False

    for line in rc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            in_section = stripped.strip("[] ").lower() == section
            continue
        if in_section and "=" in stripped:
            key, _, val = stripped.partition("=")
            val = val.split("#")[0].strip().strip('"').strip("'")
            data[key.strip()] = val

    return data


def load_llm_config() -> LLMConfig:
    """Resolve LLM configuration from .dockerbrainrc only."""

    rc = _read_rc_section("llm")
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
        _show_missing_key_error(provider)
        raise SystemExit(1)

    if provider == "ollama" and not api_key:
        api_key = "ollama"

    return LLMConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def _show_missing_key_error(provider: str) -> None:
    """Show a brief error for missing API key."""
    console.print(
        Panel(
            f"Add your key to [cyan]~/.dockerbrain/.dockerbrainrc[/]:\n"
            f'  [cyan]api_key = "your_key_here"[/]',
            title="[bold red]Missing API Key[/]",
            border_style="red",
            expand=False,
        )
    )


def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences that LLMs sometimes wrap responses in."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1 :] if "\n" in text else text
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def generate(
    prompt: str,
    system_instruction: str,
    config: LLMConfig | None = None,
) -> str:
    """Send a prompt to the configured LLM and return the response text.

    Works with any provider: Gemini uses google-genai SDK,
    all others use the OpenAI-compatible API.
    """
    if config is None:
        config = load_llm_config()

    if config.provider == "gemini":
        return _generate_gemini(prompt, system_instruction, config)
    elif config.provider == "claude":
        return _generate_anthropic(prompt, system_instruction, config)
    else:
        return _generate_openai_compat(prompt, system_instruction, config)


def generate_stream(
    prompt: str,
    system_instruction: str,
    config: LLMConfig | None = None,
):
    """Yield response chunks from the configured LLM (streaming)."""
    if config is None:
        config = load_llm_config()

    if config.provider == "gemini":
        yield from _stream_gemini(prompt, system_instruction, config)
    elif config.provider == "claude":
        yield from _stream_anthropic(prompt, system_instruction, config)
    else:
        yield from _stream_openai_compat(prompt, system_instruction, config)


# Gemini backend
def _generate_gemini(prompt: str, system_instruction: str, config: LLMConfig) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.api_key)
    response = client.models.generate_content(
        model=config.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
        ),
    )
    return _strip_code_fences(response.text)


def _stream_gemini(prompt: str, system_instruction: str, config: LLMConfig):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.api_key)
    stream = client.models.generate_content_stream(
        model=config.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


# Anthropic backend
def _generate_anthropic(prompt: str, system_instruction: str, config: LLMConfig) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.api_key)
    response = client.messages.create(
        model=config.model,
        max_tokens=4096,
        system=system_instruction,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text if response.content else ""
    return _strip_code_fences(text)


def _stream_anthropic(prompt: str, system_instruction: str, config: LLMConfig):
    import anthropic

    client = anthropic.Anthropic(api_key=config.api_key)
    with client.messages.stream(
        model=config.model,
        max_tokens=4096,
        system=system_instruction,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


# OpenAI-compatible backend
def _generate_openai_compat(
    prompt: str, system_instruction: str, config: LLMConfig
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    response = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
    )
    return _strip_code_fences(response.choices[0].message.content or "")


def _stream_openai_compat(prompt: str, system_instruction: str, config: LLMConfig):
    from openai import OpenAI

    client = OpenAI(api_key=config.api_key, base_url=config.base_url)
    stream = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": prompt},
        ],
        stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta if chunk.choices else None
        if delta and delta.content:
            yield delta.content

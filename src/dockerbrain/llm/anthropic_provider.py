"""Anthropic provider — uses anthropic SDK."""

from __future__ import annotations

from typing import Iterator

from dockerbrain.llm.base import LLMProvider, strip_code_fences
from dockerbrain.ui.cli.console import get_console


class AnthropicProvider(LLMProvider):
    """LLM provider for Anthropic Claude."""

    def generate(self, prompt: str, system_instruction: str) -> str:
        anthropic = self._import_sdk()
        client = anthropic.Anthropic(api_key=self.config.api_key)
        response = client.messages.create(
            model=self.config.model,
            max_tokens=4096,
            system=system_instruction,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        return strip_code_fences(text)

    def stream(self, prompt: str, system_instruction: str) -> Iterator[str]:
        anthropic = self._import_sdk()
        client = anthropic.Anthropic(api_key=self.config.api_key)
        with client.messages.stream(
            model=self.config.model,
            max_tokens=4096,
            system=system_instruction,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    @staticmethod
    def _import_sdk():
        try:
            import anthropic
            return anthropic
        except ImportError:
            console = get_console()
            console.print(
                '[red]Anthropic SDK is missing.[/] Run: [cyan]pip install "dockerbrain[anthropic]"[/]'
            )
            raise SystemExit(1)

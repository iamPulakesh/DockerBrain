"""OpenAI-compatible provider — covers ChatGPT."""

from __future__ import annotations

from typing import Iterator

from dockerbrain.llm.base import LLMProvider, strip_code_fences
from dockerbrain.ui.cli.console import get_console


class OpenAICompatProvider(LLMProvider):
    """LLM provider for OpenAI-compatible APIs (ChatGPT)."""

    def generate(self, prompt: str, system_instruction: str) -> str:
        OpenAI = self._import_sdk()
        client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        response = client.chat.completions.create(
            model=self.config.model,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt},
            ],
        )
        return strip_code_fences(response.choices[0].message.content or "")

    def stream(self, prompt: str, system_instruction: str) -> Iterator[str]:
        OpenAI = self._import_sdk()
        client = OpenAI(api_key=self.config.api_key, base_url=self.config.base_url)
        stream = client.chat.completions.create(
            model=self.config.model,
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

    @staticmethod
    def _import_sdk():
        try:
            from openai import OpenAI
            return OpenAI
        except ImportError:
            console = get_console()
            console.print(
                '[red]OpenAI SDK is missing.[/] Run: [cyan]pip install "dockerbrain[openai]"[/]'
            )
            raise SystemExit(1)

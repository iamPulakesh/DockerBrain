"""Gemini provider — uses google-genai SDK."""

from __future__ import annotations

from typing import Iterator

from dockerbrain.llm.base import LLMProvider, strip_code_fences
from dockerbrain.ui.cli.console import get_console


class GeminiProvider(LLMProvider):
    """LLM provider for Google Gemini via google-genai SDK."""

    def generate(self, prompt: str, system_instruction: str) -> str:
        genai, types = self._import_sdk()
        client = genai.Client(api_key=self.config.api_key)
        response = client.models.generate_content(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
            ),
        )
        return strip_code_fences(response.text)

    def stream(self, prompt: str, system_instruction: str) -> Iterator[str]:
        genai, types = self._import_sdk()
        client = genai.Client(api_key=self.config.api_key)
        stream = client.models.generate_content_stream(
            model=self.config.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
            ),
        )
        for chunk in stream:
            if chunk.text:
                yield chunk.text

    @staticmethod
    def _import_sdk():
        try:
            from google import genai
            from google.genai import types
            return genai, types
        except ImportError:
            console = get_console()
            console.print(
                '[red]Google GenAI SDK is missing.[/] Run: [cyan]pip install "dockerbrain[gemini]"[/]'
            )
            raise SystemExit(1)

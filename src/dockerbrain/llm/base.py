"""LLMProvider ABC and shared helpers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterator, TYPE_CHECKING

if TYPE_CHECKING:
    from dockerbrain.config.settings import LLMConfig


class LLMProvider(ABC):
    """Abstract base for all LLM providers."""

    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str) -> str: ...

    @abstractmethod
    def stream(self, prompt: str, system_instruction: str) -> Iterator[str]: ...


def strip_code_fences(text: str) -> str:
    """Shared helper — strip markdown code fences that LLMs sometimes wrap responses in."""
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:] if "\n" in text else text
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text

"""Rule ABC, Suggestion, and Severity — base types for all optimization rules."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docker.models.containers import Container


class Severity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    @property
    def rank(self) -> int:
        return {"HIGH": 0, "MEDIUM": 1, "LOW": 2}[self.value]

    @property
    def style(self) -> str:
        return {"HIGH": "bold red", "MEDIUM": "bold yellow", "LOW": "bold green"}[self.value]


@dataclass
class Suggestion:
    """A single optimisation suggestion produced by a rule."""

    container_name: str
    rule_name: str
    severity: Severity
    message: str
    action_command: str | None = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


class Rule(ABC):
    """Base class for all optimisation rules."""

    name: str = "UnnamedRule"

    @abstractmethod
    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        """Return zero or more suggestions for the given container."""
        ...

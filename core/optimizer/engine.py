from __future__ import annotations

from typing import TYPE_CHECKING

import docker
from docker.errors import APIError, DockerException
from rich.console import Console
from rich.panel import Panel

from core.optimizer.rules import (
    Suggestion,
    IdleContainerRule,
    MemoryHogRule,
    NoMemoryLimitRule,
    HighRestartRule,
    StaleImageRule,
    Rule,
)
from core.utils import get_docker_offline_hint

if TYPE_CHECKING:
    from docker.models.containers import Container

console = Console()


class RuleBasedOptimizer:
    """Evaluates all registered rules against running containers."""

    def __init__(self) -> None:
        self.client = self._connect()
        self.rules: list[Rule] = [
            IdleContainerRule(),
            MemoryHogRule(),
            NoMemoryLimitRule(),
            HighRestartRule(),
            StaleImageRule(),
        ]

    @staticmethod
    def _connect() -> docker.DockerClient:
        try:
            return docker.from_env()
        except DockerException as exc:
            console.print(
                Panel(
                    "[red bold]Could not connect to Docker daemon.[/]\n\n"
                    f"{get_docker_offline_hint()}\n\n",
                    title="[bold red]Docker Unavailable[/]",
                    border_style="red",
                    expand=False,
                )
            )
            raise SystemExit(3) from exc

    def analyze(self, container_name: str | None = None) -> list[Suggestion]:
        """Run every rule against target containers and return suggestions."""
        containers: list[Container] = (
            [self.client.containers.get(container_name)]
            if container_name
            else self.client.containers.list()
        )

        if not containers:
            return []

        suggestions: list[Suggestion] = []

        for ctr in containers:
            try:
                ctr.reload()
                raw_stats = ctr.stats(stream=False)
            except (APIError, DockerException) as exc:
                console.print(
                    f"[yellow] Skipping {ctr.name}: {exc}[/]",
                    highlight=False,
                )
                continue

            for rule in self.rules:
                suggestions.extend(rule.evaluate(ctr, raw_stats))

        suggestions.sort(key=lambda s: s.severity.rank)
        return suggestions

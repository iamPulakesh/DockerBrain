"""RuleEngine — iterates RULE_REGISTRY against running containers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from docker.errors import APIError, DockerException

from dockerbrain.docker_client.connection import connect_docker
from dockerbrain.optimizer.rules import RULE_REGISTRY, Suggestion, Rule
from dockerbrain.ui.cli.console import get_console

if TYPE_CHECKING:
    from docker.models.containers import Container


class RuleEngine:
    """Evaluates all registered rules against running containers."""

    def __init__(self, rules: list[Rule] | None = None) -> None:
        self.client = connect_docker()
        self.rules: list[Rule] = rules or [rule_cls() for rule_cls in RULE_REGISTRY]

    def analyze(self, container_name: str | None = None) -> list[Suggestion]:
        """Run every rule against target containers and return suggestions."""
        console = get_console()

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

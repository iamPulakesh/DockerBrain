"""HighRestartRule — flag containers with a restart count > 3."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.optimizer.rules.base import Rule, Suggestion, Severity

if TYPE_CHECKING:
    from docker.models.containers import Container


class HighRestartRule(Rule):
    """Flag containers with a restart count > 3."""

    name = "HighRestartRule"
    _THRESHOLD = 3

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        restart_count = ctr.attrs.get("RestartCount", 0)
        if restart_count <= self._THRESHOLD:
            return []

        return [
            Suggestion(
                container_name=ctr.name,
                rule_name=self.name,
                severity=Severity.HIGH,
                message=(
                    f"Container has restarted {restart_count} times. "
                    "Investigate crash loops — check logs with the action command."
                ),
                action_command=f"docker logs --tail 50 {ctr.name}",
            )
        ]

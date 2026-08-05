"""RunningAsRootRule — flag privileged containers or those running as root."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.optimizer.rules.base import Rule, Suggestion, Severity

if TYPE_CHECKING:
    from docker.models.containers import Container


class RunningAsRootRule(Rule):
    """Flag containers running in privileged mode or as root user."""

    name = "RunningAsRootRule"

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        try:
            is_privileged = ctr.attrs.get("HostConfig", {}).get("Privileged", False)
            user = ctr.attrs.get("Config", {}).get("User", "")
        except AttributeError:
            return []

        suggestions = []

        if is_privileged:
            suggestions.append(
                Suggestion(
                    container_name=ctr.name,
                    rule_name=self.name,
                    severity=Severity.HIGH,
                    message="Container is running in privileged mode.",
                    action_command="",
                )
            )

        if not user or user == "0" or user == "root":
            suggestions.append(
                Suggestion(
                    container_name=ctr.name,
                    rule_name=self.name,
                    severity=Severity.HIGH,
                    message="Container is running as root user. Consider using a non-root user for better security.",
                    action_command="",
                )
            )

        return suggestions

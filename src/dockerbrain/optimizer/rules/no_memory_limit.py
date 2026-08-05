"""NoMemoryLimitRule — flag containers with no memory limit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.optimizer.rules.base import Rule, Suggestion, Severity

if TYPE_CHECKING:
    from docker.models.containers import Container


class NoMemoryLimitRule(Rule):
    """Flag containers with no memory limit (limit == total host RAM)."""

    name = "NoMemoryLimitRule"

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        mem_limit = stats.get("memory_stats", {}).get("limit", 0)
        mem_usage = stats.get("memory_stats", {}).get("usage", 0)

        _16_GIB = 16 * 1024 * 1024 * 1024
        if mem_limit < _16_GIB:
            return []

        usage_mb = mem_usage / (1024 * 1024)
        suggested_mb = max(256, int(usage_mb * 2))

        return [
            Suggestion(
                container_name=ctr.name,
                rule_name=self.name,
                severity=Severity.MEDIUM,
                message=(
                    "No memory limit is set. The container can cause OOM. "
                    f"Current usage: {usage_mb:.0f} MB. Consider adding a --memory flag."
                ),
                action_command=f"docker update --memory {suggested_mb}m {ctr.name}",
            )
        ]

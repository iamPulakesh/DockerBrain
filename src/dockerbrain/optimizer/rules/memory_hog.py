"""MemoryHogRule — flag containers using > 80% of their memory limit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.optimizer.rules.base import Rule, Suggestion, Severity

if TYPE_CHECKING:
    from docker.models.containers import Container


class MemoryHogRule(Rule):
    """Flag containers using > 80% of their memory limit."""

    name = "MemoryHogRule"
    _THRESHOLD = 80.0

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        mem_usage = stats.get("memory_stats", {}).get("usage", 0)
        mem_limit = stats.get("memory_stats", {}).get("limit", 0)

        if not mem_limit or mem_limit <= 0:
            return []

        mem_pct = (mem_usage / mem_limit) * 100.0
        if mem_pct <= self._THRESHOLD:
            return []

        usage_mb = mem_usage / (1024 * 1024)
        limit_mb = mem_limit / (1024 * 1024)
        new_limit = int(limit_mb * 1.5)

        return [
            Suggestion(
                container_name=ctr.name,
                rule_name=self.name,
                severity=Severity.HIGH,
                message=(
                    f"Memory usage is {mem_pct:.1f}% ({usage_mb:.0f} MB / {limit_mb:.0f} MB). "
                    f"Consider increasing the limit or profiling the application."
                ),
                action_command=f"docker update --memory {new_limit}m {ctr.name}",
            )
        ]

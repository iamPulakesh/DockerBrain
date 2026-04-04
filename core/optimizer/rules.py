from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING

from core.utils import calc_cpu_percent

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


class IdleContainerRule(Rule):
    """Flag containers that have been idle (CPU < 0.5%) for > 10 minutes.

    Heuristic: if current CPU is near-zero **and** the container has been
    running for more than 10 minutes, we flag it.  A more precise detection
    relies on the monitor's consecutive-poll tracker, but this gives a good
    one-shot signal during ``analyze``.
    """

    name = "IdleContainerRule"
    _CPU_THRESHOLD = 0.5
    _MIN_UPTIME_SECS = 600

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        cpu = calc_cpu_percent(stats)
        if cpu >= self._CPU_THRESHOLD:
            return []

        started_at = ctr.attrs.get("State", {}).get("StartedAt", "")
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime = (datetime.now(timezone.utc) - start_dt).total_seconds()
                if uptime < self._MIN_UPTIME_SECS:
                    return []
            except (ValueError, TypeError):
                pass

        return [
            Suggestion(
                container_name=ctr.name,
                rule_name=self.name,
                severity=Severity.MEDIUM,
                message=(
                    f"Container is idle (CPU {cpu:.2f}%) and has been running for "
                    f"over 10 minutes. Consider stopping it to reclaim resources."
                ),
                action_command=f"docker stop {ctr.name}",
            )
        ]


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
                    "No memory limit is set. The container can consume all host memory. "
                    f"Current usage: {usage_mb:.0f} MB. Consider adding a --memory flag."
                ),
                action_command=f"docker update --memory {suggested_mb}m {ctr.name}",
            )
        ]


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


class StaleImageRule(Rule):
    """Flag containers whose image is older than 30 days."""

    name = "StaleImageRule"
    _MAX_AGE_DAYS = 30

    def evaluate(self, ctr: Container, stats: dict) -> list[Suggestion]:
        try:
            image = ctr.image
            created_str = image.attrs.get("Created", "")
            if not created_str:
                return []

            created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created_dt).days

            if age_days <= self._MAX_AGE_DAYS:
                return []

            image_tag = image.tags[0] if image.tags else image.short_id
            return [
                Suggestion(
                    container_name=ctr.name,
                    rule_name=self.name,
                    severity=Severity.LOW,
                    message=(
                        f"Image '{image_tag}' is {age_days} days old. "
                        "Consider rebuilding with the latest base to pick up security patches."
                    ),
                    action_command=f"docker pull {image_tag}" if image.tags else None,
                )
            ]
        except Exception:
            return []

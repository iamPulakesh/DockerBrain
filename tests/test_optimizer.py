from __future__ import annotations

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

from dockerbrain.optimizer.rules import (
    MemoryHogRule,
    NoMemoryLimitRule,
    HighRestartRule,
    RunningAsRootRule,
    Severity,
    Suggestion,
)
from dockerbrain.optimizer.engine import RuleEngine


def _mock_container(
    name: str = "test-ctr",
    restart_count: int = 0,
    started_minutes_ago: int = 30,
    image_days_old: int = 5,
    image_tags: list[str] | None = None,
) -> MagicMock:
    ctr = MagicMock()
    ctr.name = name

    started = datetime.now(timezone.utc) - timedelta(minutes=started_minutes_ago)
    ctr.attrs = {
        "RestartCount": restart_count,
        "State": {"StartedAt": started.isoformat()},
    }

    image = MagicMock()
    created = datetime.now(timezone.utc) - timedelta(days=image_days_old)
    image.attrs = {"Created": created.isoformat()}
    image.tags = image_tags or ["myapp:latest"]
    image.short_id = "sha256:abc123"
    ctr.image = image

    return ctr


def _mock_stats(
    cpu_delta: int = 5000,
    system_delta: int = 100000,
    online_cpus: int = 4,
    mem_usage: int = 200 * 1024 * 1024,
    mem_limit: int = 512 * 1024 * 1024,
) -> dict:
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 100000 + cpu_delta, "percpu_usage": [0] * online_cpus},
            "system_cpu_usage": 9000000 + system_delta,
            "online_cpus": online_cpus,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100000, "percpu_usage": [0] * online_cpus},
            "system_cpu_usage": 9000000,
        },
        "memory_stats": {"usage": mem_usage, "limit": mem_limit},
        "networks": {"eth0": {"rx_bytes": 1024, "tx_bytes": 2048}},
    }


class TestSeverity:
    def test_rank_order(self):
        assert Severity.HIGH.rank < Severity.MEDIUM.rank < Severity.LOW.rank

    def test_styles(self):
        assert "red" in Severity.HIGH.style
        assert "yellow" in Severity.MEDIUM.style
        assert "green" in Severity.LOW.style


class TestSuggestion:
    def test_to_dict(self):
        s = Suggestion(
            container_name="web",
            rule_name="TestRule",
            severity=Severity.HIGH,
            message="test message",
            action_command="docker stop web",
        )
        d = s.to_dict()
        assert d["severity"] == "HIGH"
        assert d["container_name"] == "web"
        assert d["action_command"] == "docker stop web"

    def test_to_dict_without_action(self):
        s = Suggestion(
            container_name="web",
            rule_name="TestRule",
            severity=Severity.LOW,
            message="test",
        )
        d = s.to_dict()
        assert d["action_command"] is None


class TestMemoryHogRule:
    def test_high_memory(self):
        rule = MemoryHogRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_usage=450 * 1024 * 1024, mem_limit=512 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].severity == Severity.HIGH
        assert "docker update" in results[0].action_command

    def test_normal_memory(self):
        rule = MemoryHogRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_usage=200 * 1024 * 1024, mem_limit=512 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_exactly_at_threshold(self):
        rule = MemoryHogRule()
        ctr = _mock_container()
        limit = 1000 * 1024 * 1024
        usage = int(limit * 0.80)
        stats = _mock_stats(mem_usage=usage, mem_limit=limit)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_zero_limit_returns_nothing(self):
        rule = MemoryHogRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_usage=100, mem_limit=0)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0


class TestNoMemoryLimitRule:
    def test_no_limit(self):
        rule = NoMemoryLimitRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_limit=32 * 1024 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].severity == Severity.MEDIUM

    def test_with_limit(self):
        rule = NoMemoryLimitRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_limit=512 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_exactly_16gib_is_flagged(self):
        rule = NoMemoryLimitRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_limit=16 * 1024 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1

    def test_suggested_limit_at_least_256mb(self):
        rule = NoMemoryLimitRule()
        ctr = _mock_container()
        stats = _mock_stats(mem_usage=50 * 1024 * 1024, mem_limit=32 * 1024 * 1024 * 1024)

        results = rule.evaluate(ctr, stats)
        assert "256m" in results[0].action_command


class TestHighRestartRule:
    def test_many_restarts(self):
        rule = HighRestartRule()
        ctr = _mock_container(restart_count=7)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].severity == Severity.HIGH
        assert "docker logs" in results[0].action_command

    def test_few_restarts(self):
        rule = HighRestartRule()
        ctr = _mock_container(restart_count=2)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_exactly_at_threshold(self):
        rule = HighRestartRule()
        ctr = _mock_container(restart_count=3)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_zero_restarts(self):
        rule = HighRestartRule()
        ctr = _mock_container(restart_count=0)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0


class TestRunningAsRootRule:
    def test_privileged(self):
        rule = RunningAsRootRule()
        ctr = _mock_container()
        ctr.attrs["HostConfig"] = {"Privileged": True}
        ctr.attrs["Config"] = {"User": "1000"}

        results = rule.evaluate(ctr, {})
        assert len(results) == 1
        assert results[0].severity == Severity.HIGH
        assert "privileged mode" in results[0].message

    def test_root_user(self):
        rule = RunningAsRootRule()
        ctr = _mock_container()
        ctr.attrs["HostConfig"] = {"Privileged": False}
        ctr.attrs["Config"] = {"User": "0"}

        results = rule.evaluate(ctr, {})
        assert len(results) == 1
        assert results[0].severity == Severity.HIGH
        assert "running as root" in results[0].message

    def test_empty_user(self):
        rule = RunningAsRootRule()
        ctr = _mock_container()
        ctr.attrs["HostConfig"] = {"Privileged": False}
        ctr.attrs["Config"] = {"User": ""}

        results = rule.evaluate(ctr, {})
        assert len(results) == 1
        assert results[0].severity == Severity.HIGH
        assert "running as root" in results[0].message

    def test_safe_container(self):
        rule = RunningAsRootRule()
        ctr = _mock_container()
        ctr.attrs["HostConfig"] = {"Privileged": False}
        ctr.attrs["Config"] = {"User": "1001:1001"}

        results = rule.evaluate(ctr, {})
        assert len(results) == 0

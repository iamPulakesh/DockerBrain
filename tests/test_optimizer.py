from __future__ import annotations

from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

import pytest

from core.optimizer import (
    IdleContainerRule,
    MemoryHogRule,
    NoMemoryLimitRule,
    HighRestartRule,
    StaleImageRule,
    RuleBasedOptimizer,
    Severity,
    Suggestion,
)


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


class TestIdleContainerRule:
    def test_idle_detected(self):
        rule = IdleContainerRule()
        ctr = _mock_container(started_minutes_ago=15)
        stats = _mock_stats(cpu_delta=0, system_delta=100000)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].severity == Severity.MEDIUM
        assert "docker stop" in results[0].action_command

    def test_not_idle_high_cpu(self):
        rule = IdleContainerRule()
        ctr = _mock_container(started_minutes_ago=15)
        stats = _mock_stats(cpu_delta=50000, system_delta=100000)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_not_idle_short_uptime(self):
        rule = IdleContainerRule()
        ctr = _mock_container(started_minutes_ago=5)
        stats = _mock_stats(cpu_delta=0, system_delta=100000)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_missing_started_at(self):
        rule = IdleContainerRule()
        ctr = _mock_container()
        ctr.attrs = {"State": {"StartedAt": ""}}
        stats = _mock_stats(cpu_delta=0, system_delta=100000)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1

    def test_invalid_started_at(self):
        rule = IdleContainerRule()
        ctr = _mock_container()
        ctr.attrs = {"State": {"StartedAt": "not-a-date"}}
        stats = _mock_stats(cpu_delta=0, system_delta=100000)

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1


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


class TestStaleImageRule:
    def test_stale_image(self):
        rule = StaleImageRule()
        ctr = _mock_container(image_days_old=60)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].severity == Severity.LOW

    def test_fresh_image(self):
        rule = StaleImageRule()
        ctr = _mock_container(image_days_old=10)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_exactly_at_threshold(self):
        rule = StaleImageRule()
        ctr = _mock_container(image_days_old=30)
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0

    def test_image_without_tags(self):
        rule = StaleImageRule()
        ctr = _mock_container(image_days_old=60)
        ctr.image.tags = []
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 1
        assert results[0].action_command is None

    def test_missing_created_attr(self):
        rule = StaleImageRule()
        ctr = _mock_container()
        ctr.image.attrs = {"Created": ""}
        stats = _mock_stats()

        results = rule.evaluate(ctr, stats)
        assert len(results) == 0


class TestRuleBasedOptimizer:
    @patch("core.optimizer.engine.docker.from_env")
    def test_analyze_returns_sorted_suggestions(self, mock_docker):
        ctr = _mock_container(restart_count=5, image_days_old=60)
        ctr.reload = MagicMock()
        ctr.stats = MagicMock(return_value=_mock_stats(
            mem_usage=450 * 1024 * 1024, mem_limit=512 * 1024 * 1024
        ))

        client = MagicMock()
        client.containers.list.return_value = [ctr]
        mock_docker.return_value = client

        optimizer = RuleBasedOptimizer()
        suggestions = optimizer.analyze()

        assert len(suggestions) > 0
        severities = [s.severity for s in suggestions]
        assert severities == sorted(severities, key=lambda s: s.rank)

    @patch("core.optimizer.engine.docker.from_env")
    def test_analyze_no_containers(self, mock_docker):
        client = MagicMock()
        client.containers.list.return_value = []
        mock_docker.return_value = client

        optimizer = RuleBasedOptimizer()
        assert optimizer.analyze() == []

    @patch("core.optimizer.engine.docker.from_env")
    def test_analyze_specific_container(self, mock_docker):
        ctr = _mock_container(name="target")
        ctr.reload = MagicMock()
        ctr.stats = MagicMock(return_value=_mock_stats())

        client = MagicMock()
        client.containers.get.return_value = ctr
        mock_docker.return_value = client

        optimizer = RuleBasedOptimizer()
        suggestions = optimizer.analyze(container_name="target")
        for s in suggestions:
            assert s.container_name == "target"

    @patch("core.optimizer.engine.docker.from_env")
    def test_analyze_skips_failed_containers(self, mock_docker):
        from docker.errors import APIError

        ctr = _mock_container()
        ctr.reload = MagicMock(side_effect=APIError("boom"))

        client = MagicMock()
        client.containers.list.return_value = [ctr]
        mock_docker.return_value = client

        optimizer = RuleBasedOptimizer()
        assert optimizer.analyze() == []

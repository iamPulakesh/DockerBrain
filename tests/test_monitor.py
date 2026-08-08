from __future__ import annotations

from dockerbrain.ui.dashboard.formatters import (
    format_uptime as _format_uptime,
    get_cpu_color as _cpu_color,
    get_mem_color as _mem_color,
)
from dockerbrain.monitor.snapshot import (
    ContainerSnapshot,
    MEM_WARNING_PCT,
    MEM_CRITICAL_PCT,
)


class TestFormatUptime:
    def test_seconds(self):
        assert _format_uptime(30) == "30s"

    def test_minutes(self):
        assert _format_uptime(300) == "5m"

    def test_hours_and_minutes(self):
        result = _format_uptime(3700)
        assert "1h" in result

    def test_days_and_hours(self):
        result = _format_uptime(100000)
        assert "d" in result

    def test_zero(self):
        assert _format_uptime(0) == "0s"

    def test_exactly_60_seconds(self):
        assert _format_uptime(60) == "1m"

    def test_exactly_one_hour(self):
        result = _format_uptime(3600)
        assert "1h" in result

    def test_exactly_one_day(self):
        result = _format_uptime(86400)
        assert "1d" in result


class TestCpuColor:
    def test_high_cpu(self):
        assert "red" in _cpu_color(90)

    def test_medium_cpu(self):
        assert _cpu_color(60) == "yellow"

    def test_low_cpu(self):
        assert _cpu_color(20) == "green"

    def test_zero(self):
        assert _cpu_color(0) == "green"

    def test_boundary_80(self):
        assert _cpu_color(80) == "yellow"

    def test_boundary_50(self):
        assert _cpu_color(50) == "green"

    def test_above_80(self):
        assert "red" in _cpu_color(81)

    def test_above_50(self):
        assert _cpu_color(51) == "yellow"


class TestMemColor:
    def test_critical(self):
        assert "red" in _mem_color(90)

    def test_warning(self):
        assert _mem_color(75) == "yellow"

    def test_normal(self):
        assert _mem_color(50) == "cyan"

    def test_at_critical_threshold(self):
        assert _mem_color(MEM_CRITICAL_PCT) == "yellow"

    def test_at_warning_threshold(self):
        assert _mem_color(MEM_WARNING_PCT) == "cyan"


class TestContainerSnapshot:
    def _make_snapshot(self, **kwargs):
        defaults = {
            "name": "test",
            "status": "running",
            "cpu_percent": 10.0,
            "mem_usage_mb": 100.0,
            "mem_limit_mb": 512.0,
            "mem_percent": 19.5,
            "net_rx_bytes": 1024,
            "net_tx_bytes": 2048,
        }
        defaults.update(kwargs)
        return ContainerSnapshot(**defaults)

    def test_healthy_snapshot(self):
        snap = self._make_snapshot()
        assert snap.health_label == "HEALTHY"
        assert snap.health_style == "green"

    def test_idle_snapshot(self):
        snap = self._make_snapshot(is_idle=True)
        assert snap.health_label == "IDLE"
        assert snap.health_style == "red"

    def test_critical_memory(self):
        snap = self._make_snapshot(mem_percent=90.0)
        assert snap.health_label == "CRITICAL"
        assert snap.health_style == "red"

    def test_warning_memory(self):
        snap = self._make_snapshot(mem_percent=75.0)
        assert snap.health_label == "WARNING"
        assert snap.health_style == "yellow"

    def test_idle_takes_priority_over_memory(self):
        snap = self._make_snapshot(is_idle=True, mem_percent=90.0)
        assert snap.health_label == "IDLE"

    def test_timestamp_auto_generated(self):
        snap = self._make_snapshot()
        assert snap.timestamp is not None
        assert len(snap.timestamp) > 0

    def test_default_values(self):
        snap = self._make_snapshot()
        assert snap.mem_cache_mb == 0.0
        assert snap.is_idle is False
        assert snap.idle_polls == 0
        assert snap.restart_count == 0
        assert snap.image_tag == ""

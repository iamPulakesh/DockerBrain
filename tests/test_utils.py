from __future__ import annotations

import sys
from unittest.mock import patch

from dockerbrain.ui.cli.tables import format_bytes
from dockerbrain.docker_client.metrics import calc_cpu_percent
from dockerbrain.docker_client.connection import get_docker_offline_hint


class TestFormatBytes:
    def test_bytes(self):
        assert format_bytes(500) == "500.00 B"

    def test_kibibytes(self):
        result = format_bytes(2048)
        assert "KiB" in result
        assert "2.00" in result

    def test_mebibytes(self):
        result = format_bytes(5 * 1024 * 1024)
        assert "MiB" in result
        assert "5.00" in result

    def test_gibibytes(self):
        result = format_bytes(2.5 * 1024 ** 3)
        assert "GiB" in result

    def test_tebibytes(self):
        result = format_bytes(3 * 1024 ** 4)
        assert "TiB" in result

    def test_zero(self):
        assert format_bytes(0) == "0.00 B"

    def test_negative(self):
        result = format_bytes(-1024)
        assert "KiB" in result

    def test_very_large(self):
        result = format_bytes(5 * 1024 ** 5)
        assert "PiB" in result

    def test_fractional(self):
        result = format_bytes(1536)
        assert "KiB" in result
        assert "1.50" in result


class TestCalcCpuPercent:
    def test_normal_usage(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 110000},
                "system_cpu_usage": 9100000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100000},
                "system_cpu_usage": 9000000,
            },
        }
        result = calc_cpu_percent(stats)
        assert result > 0

    def test_zero_delta(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100000},
                "system_cpu_usage": 9000000,
                "online_cpus": 4,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100000},
                "system_cpu_usage": 9000000,
            },
        }
        assert calc_cpu_percent(stats) == 0.0

    def test_empty_stats(self):
        assert calc_cpu_percent({}) == 0.0

    def test_missing_precpu_still_calculates(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100000},
                "system_cpu_usage": 9000000,
                "online_cpus": 4,
            },
        }
        result = calc_cpu_percent(stats)
        assert result > 0

    def test_uses_percpu_usage_when_online_cpus_missing(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 110000,
                    "percpu_usage": [50000, 60000],
                },
                "system_cpu_usage": 9100000,
            },
            "precpu_stats": {
                "cpu_usage": {
                    "total_usage": 100000,
                    "percpu_usage": [45000, 55000],
                },
                "system_cpu_usage": 9000000,
            },
        }
        result = calc_cpu_percent(stats)
        assert result > 0


class TestGetDockerOfflineHint:
    def test_windows(self):
        with patch.object(sys, "platform", "win32"):
            hint = get_docker_offline_hint()
            assert "Docker Desktop" in hint

    def test_macos(self):
        with patch.object(sys, "platform", "darwin"):
            hint = get_docker_offline_hint()
            assert "Docker Desktop" in hint or "OrbStack" in hint

    def test_linux(self):
        with patch.object(sys, "platform", "linux"):
            hint = get_docker_offline_hint()
            assert "systemctl" in hint

    def test_returns_string(self):
        assert isinstance(get_docker_offline_hint(), str)
        assert len(get_docker_offline_hint()) > 0

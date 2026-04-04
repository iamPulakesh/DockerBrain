from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from core.storage import (
    _get_connection,
    store_snapshot,
    store_metrics,
    get_recent_metrics,
    get_metrics_since,
    get_all_container_names,
    store_ai_suggestion,
    get_last_ai_suggestion,
)
from core.monitor import ContainerSnapshot


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    temp_db = tmp_path / "test_metrics.db"
    monkeypatch.setattr("core.storage._DB_PATH", temp_db)
    yield


class TestDatabaseSetup:
    def test_creates_tables(self, tmp_path):
        conn = _get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "container_metrics" in tables
        assert "ai_suggestions" in tables

    def test_creates_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "nested" / "dir"
        monkeypatch.setattr("core.storage._DB_PATH", nested / "db.sqlite")
        conn = _get_connection()
        conn.close()
        assert nested.exists()


class TestStoreSnapshot:
    def test_persists_snapshot(self):
        snap = ContainerSnapshot(
            name="web",
            status="running",
            cpu_percent=12.5,
            mem_usage_mb=256.0,
            mem_limit_mb=512.0,
            mem_percent=50.0,
            net_rx_bytes=1024,
            net_tx_bytes=2048,
            is_idle=True,
            idle_polls=15,
        )
        store_snapshot(snap)
        results = get_recent_metrics("web", limit=10)
        assert len(results) == 1
        assert results[0]["container"] == "web"
        assert results[0]["cpu_percent"] == 12.5
        assert results[0]["is_idle"] == 1


class TestStoreAndRetrieveMetrics:
    def test_store_and_get(self):
        row = {
            "name": "web-app",
            "cpu_percent": 12.5,
            "mem_usage_mb": 256.0,
            "mem_limit_mb": 512.0,
            "mem_percent": 50.0,
            "net_rx_bytes": 1024,
            "net_tx_bytes": 2048,
        }
        store_metrics(row)
        results = get_recent_metrics("web-app", limit=10)
        assert len(results) == 1
        assert results[0]["container"] == "web-app"
        assert results[0]["cpu_percent"] == 12.5

    def test_multiple_rows_ordered_desc(self):
        for i in range(5):
            store_metrics({
                "name": "test-ctr",
                "cpu_percent": float(i),
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })

        results = get_recent_metrics("test-ctr", limit=3)
        assert len(results) == 3
        assert results[0]["cpu_percent"] == 4.0

    def test_limit_respected(self):
        for i in range(20):
            store_metrics({
                "name": "bulk",
                "cpu_percent": 1.0,
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })

        results = get_recent_metrics("bulk", limit=5)
        assert len(results) == 5

    def test_different_containers_isolated(self):
        for name in ("alpha", "beta"):
            store_metrics({
                "name": name,
                "cpu_percent": 1.0,
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })
        assert len(get_recent_metrics("alpha")) == 1
        assert len(get_recent_metrics("beta")) == 1

    def test_nonexistent_container_returns_empty(self):
        assert get_recent_metrics("ghost") == []

    def test_legacy_dict_format_with_raw_keys(self):
        row = {
            "name": "legacy",
            "cpu_percent": 5.0,
            "mem_percent": 10.0,
            "mem_usage": 100 * 1024 * 1024,
            "mem_limit": 512 * 1024 * 1024,
            "net_rx": 500,
            "net_tx": 600,
        }
        store_metrics(row)
        results = get_recent_metrics("legacy")
        assert len(results) == 1
        assert results[0]["mem_usage_mb"] == pytest.approx(100.0, rel=0.1)


class TestGetMetricsSince:
    def test_time_filtering(self):
        store_metrics({
            "name": "app", "cpu_percent": 1.0, "mem_percent": 0.0,
            "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
            "net_rx_bytes": 0, "net_tx_bytes": 0,
        })

        rows = get_metrics_since("2000-01-01T00:00:00+00:00")
        assert len(rows) >= 1

        rows = get_metrics_since("2099-01-01T00:00:00+00:00")
        assert len(rows) == 0

    def test_container_filter(self):
        for name in ("alpha", "beta", "alpha"):
            store_metrics({
                "name": name, "cpu_percent": 1.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        rows = get_metrics_since("2000-01-01T00:00:00+00:00", container="alpha")
        assert all(r["container"] == "alpha" for r in rows)
        assert len(rows) == 2

    def test_no_container_filter_returns_all(self):
        for name in ("x", "y"):
            store_metrics({
                "name": name, "cpu_percent": 1.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        rows = get_metrics_since("2000-01-01T00:00:00+00:00")
        containers = {r["container"] for r in rows}
        assert "x" in containers
        assert "y" in containers


class TestGetAllContainerNames:
    def test_returns_distinct_sorted(self):
        for name in ("zebra", "alpha", "alpha", "middle"):
            store_metrics({
                "name": name, "cpu_percent": 0.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        names = get_all_container_names()
        assert names == ["alpha", "middle", "zebra"]

    def test_empty_db(self):
        assert get_all_container_names() == []


class TestAiSuggestionCache:
    def test_store_and_get(self):
        assert get_last_ai_suggestion() is None

        store_ai_suggestion(summary="Test summary", full_response="Full text here")
        result = get_last_ai_suggestion()
        assert result is not None
        assert result["summary"] == "Test summary"
        assert result["full_response"] == "Full text here"
        assert "timestamp" in result

    def test_returns_latest(self):
        store_ai_suggestion(summary="Old one", full_response="old")
        store_ai_suggestion(summary="New one", full_response="new")
        result = get_last_ai_suggestion()
        assert result["summary"] == "New one"

    def test_empty_full_response(self):
        store_ai_suggestion(summary="Short")
        result = get_last_ai_suggestion()
        assert result["full_response"] == ""

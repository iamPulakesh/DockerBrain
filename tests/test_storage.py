from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from dockerbrain.storage.database import get_connection
from dockerbrain.storage.metrics_repository import MetricsRepository
from dockerbrain.storage.suggestions_repository import SuggestionsRepository
from dockerbrain.monitor.snapshot import ContainerSnapshot


@pytest.fixture(autouse=True)
def _use_temp_db(tmp_path, monkeypatch):
    temp_db = tmp_path / "test_metrics.db"
    monkeypatch.setattr("dockerbrain.storage.database._DB_PATH", temp_db)
    yield


@pytest.fixture()
def metrics_repo():
    return MetricsRepository()


@pytest.fixture()
def suggestions_repo():
    return SuggestionsRepository()


class TestDatabaseSetup:
    def test_creates_tables(self, tmp_path):
        conn = get_connection()
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        assert "container_metrics" in tables
        assert "ai_suggestions" in tables

    def test_creates_directory(self, tmp_path, monkeypatch):
        nested = tmp_path / "deep" / "nested" / "dir"
        monkeypatch.setattr("dockerbrain.storage.database._DB_PATH", nested / "db.sqlite")
        conn = get_connection()
        conn.close()
        assert nested.exists()


class TestStoreSnapshot:
    def test_persists_snapshot(self, metrics_repo):
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
        metrics_repo.store_snapshot(snap)
        results = metrics_repo.get_recent("web", limit=10)
        assert len(results) == 1
        assert results[0]["container"] == "web"
        assert results[0]["cpu_percent"] == 12.5
        assert results[0]["is_idle"] == 1


class TestStoreAndRetrieveMetrics:
    def test_store_and_get(self, metrics_repo):
        row = {
            "name": "web-app",
            "cpu_percent": 12.5,
            "mem_usage_mb": 256.0,
            "mem_limit_mb": 512.0,
            "mem_percent": 50.0,
            "net_rx_bytes": 1024,
            "net_tx_bytes": 2048,
        }
        metrics_repo.store_raw(row)
        results = metrics_repo.get_recent("web-app", limit=10)
        assert len(results) == 1
        assert results[0]["container"] == "web-app"
        assert results[0]["cpu_percent"] == 12.5

    def test_multiple_rows_ordered_desc(self, metrics_repo):
        for i in range(5):
            metrics_repo.store_raw({
                "name": "test-ctr",
                "cpu_percent": float(i),
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })

        results = metrics_repo.get_recent("test-ctr", limit=3)
        assert len(results) == 3
        assert results[0]["cpu_percent"] == 4.0

    def test_limit_respected(self, metrics_repo):
        for i in range(20):
            metrics_repo.store_raw({
                "name": "bulk",
                "cpu_percent": 1.0,
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })

        results = metrics_repo.get_recent("bulk", limit=5)
        assert len(results) == 5

    def test_different_containers_isolated(self, metrics_repo):
        for name in ("alpha", "beta"):
            metrics_repo.store_raw({
                "name": name,
                "cpu_percent": 1.0,
                "mem_percent": 0.0,
                "mem_usage_mb": 0.0,
                "mem_limit_mb": 0.0,
                "net_rx_bytes": 0,
                "net_tx_bytes": 0,
            })
        assert len(metrics_repo.get_recent("alpha")) == 1
        assert len(metrics_repo.get_recent("beta")) == 1

    def test_nonexistent_container_returns_empty(self, metrics_repo):
        assert metrics_repo.get_recent("ghost") == []

    def test_legacy_dict_format_with_raw_keys(self, metrics_repo):
        row = {
            "name": "legacy",
            "cpu_percent": 5.0,
            "mem_percent": 10.0,
            "mem_usage": 100 * 1024 * 1024,
            "mem_limit": 512 * 1024 * 1024,
            "net_rx": 500,
            "net_tx": 600,
        }
        metrics_repo.store_raw(row)
        results = metrics_repo.get_recent("legacy")
        assert len(results) == 1
        assert results[0]["mem_usage_mb"] == pytest.approx(100.0, rel=0.1)


class TestGetMetricsSince:
    def test_time_filtering(self, metrics_repo):
        metrics_repo.store_raw({
            "name": "app", "cpu_percent": 1.0, "mem_percent": 0.0,
            "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
            "net_rx_bytes": 0, "net_tx_bytes": 0,
        })

        rows = metrics_repo.get_since("2000-01-01T00:00:00+00:00")
        assert len(rows) >= 1

        rows = metrics_repo.get_since("2099-01-01T00:00:00+00:00")
        assert len(rows) == 0

    def test_container_filter(self, metrics_repo):
        for name in ("alpha", "beta", "alpha"):
            metrics_repo.store_raw({
                "name": name, "cpu_percent": 1.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        rows = metrics_repo.get_since("2000-01-01T00:00:00+00:00", container="alpha")
        assert all(r["container"] == "alpha" for r in rows)
        assert len(rows) == 2

    def test_no_container_filter_returns_all(self, metrics_repo):
        for name in ("x", "y"):
            metrics_repo.store_raw({
                "name": name, "cpu_percent": 1.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        rows = metrics_repo.get_since("2000-01-01T00:00:00+00:00")
        containers = {r["container"] for r in rows}
        assert "x" in containers
        assert "y" in containers


class TestGetAllContainerNames:
    def test_returns_distinct_sorted(self, metrics_repo):
        for name in ("zebra", "alpha", "alpha", "middle"):
            metrics_repo.store_raw({
                "name": name, "cpu_percent": 0.0, "mem_percent": 0.0,
                "mem_usage_mb": 0.0, "mem_limit_mb": 0.0,
                "net_rx_bytes": 0, "net_tx_bytes": 0,
            })

        names = metrics_repo.get_all_container_names()
        assert names == ["alpha", "middle", "zebra"]

    def test_empty_db(self, metrics_repo):
        assert metrics_repo.get_all_container_names() == []


class TestAiSuggestionCache:
    def test_store_and_get(self, suggestions_repo):
        assert suggestions_repo.get_last() is None

        suggestions_repo.store(summary="Test summary", full_response="Full text here")
        result = suggestions_repo.get_last()
        assert result is not None
        assert result["summary"] == "Test summary"
        assert result["full_response"] == "Full text here"
        assert "timestamp" in result

    def test_returns_latest(self, suggestions_repo):
        suggestions_repo.store(summary="Old one", full_response="old")
        suggestions_repo.store(summary="New one", full_response="new")
        result = suggestions_repo.get_last()
        assert result["summary"] == "New one"

    def test_empty_full_response(self, suggestions_repo):
        suggestions_repo.store(summary="Short")
        result = suggestions_repo.get_last()
        assert result["full_response"] == ""

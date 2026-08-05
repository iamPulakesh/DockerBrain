"""MetricsRepository — container_metrics table operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.storage.database import Database

if TYPE_CHECKING:
    from dockerbrain.monitor.snapshot import ContainerSnapshot


class MetricsRepository:
    """Repository for container metric snapshots."""

    def __init__(self, database: Database | None = None) -> None:
        self._db = database or Database()

    def store_snapshot(self, snap: ContainerSnapshot) -> None:
        """Persist a single ContainerSnapshot row."""
        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO container_metrics
                    (timestamp, container, status, cpu_percent,
                     mem_usage_mb, mem_limit_mb, mem_percent,
                     net_rx_bytes, net_tx_bytes, is_idle, idle_polls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap.timestamp,
                    snap.name,
                    snap.status,
                    snap.cpu_percent,
                    snap.mem_usage_mb,
                    snap.mem_limit_mb,
                    snap.mem_percent,
                    snap.net_rx_bytes,
                    snap.net_tx_bytes,
                    int(snap.is_idle),
                    snap.idle_polls,
                ),
            )
            conn.commit()

    def get_recent(self, container: str, limit: int = 60) -> list[dict]:
        """Retrieve the most recent *limit* rows for a given container."""
        with self._db.connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM container_metrics WHERE container = ? ORDER BY id DESC LIMIT ?",
                (container, limit),
            )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, r)) for r in cursor.fetchall()]

    def get_since(self, since_iso: str, container: str | None = None) -> list[dict]:
        """Return all rows with timestamp >= *since_iso*."""
        with self._db.connect() as conn:
            if container:
                cursor = conn.execute(
                    "SELECT * FROM container_metrics WHERE timestamp >= ? AND container = ? ORDER BY timestamp",
                    (since_iso, container),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM container_metrics WHERE timestamp >= ? ORDER BY timestamp",
                    (since_iso,),
                )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, r)) for r in cursor.fetchall()]

    def get_all_container_names(self) -> list[str]:
        """Return distinct container names from the metrics table."""
        with self._db.connect() as conn:
            cursor = conn.execute(
                "SELECT DISTINCT container FROM container_metrics ORDER BY container"
            )
            return [row[0] for row in cursor.fetchall()]

    def store_raw(self, row: dict) -> None:
        """Store a raw dict of metrics (backward-compat with old store_metrics API).

        Handles both ``mem_usage_mb`` and raw byte keys (``mem_usage``).
        """
        from datetime import datetime, timezone

        name = row.get("name", "unknown")
        cpu_pct = row.get("cpu_percent", 0.0)

        mem_usage_mb = row.get("mem_usage_mb")
        mem_limit_mb = row.get("mem_limit_mb")

        if mem_usage_mb is None:
            raw_usage = row.get("mem_usage", 0)
            mem_usage_mb = raw_usage / (1024 * 1024) if raw_usage else 0.0

        if mem_limit_mb is None:
            raw_limit = row.get("mem_limit", 0)
            mem_limit_mb = raw_limit / (1024 * 1024) if raw_limit else 0.0

        mem_pct = row.get("mem_percent", 0.0)
        net_rx = row.get("net_rx_bytes", row.get("net_rx", 0))
        net_tx = row.get("net_tx_bytes", row.get("net_tx", 0))
        is_idle = int(row.get("is_idle", False))
        idle_polls = row.get("idle_polls", 0)
        ts = row.get("timestamp", datetime.now(timezone.utc).isoformat())

        with self._db.connect() as conn:
            conn.execute(
                """
                INSERT INTO container_metrics
                    (timestamp, container, status, cpu_percent,
                     mem_usage_mb, mem_limit_mb, mem_percent,
                     net_rx_bytes, net_tx_bytes, is_idle, idle_polls)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts, name, row.get("status", "running"), cpu_pct,
                    mem_usage_mb, mem_limit_mb, mem_pct,
                    net_rx, net_tx, is_idle, idle_polls,
                ),
            )
            conn.commit()

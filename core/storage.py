from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.monitor import ContainerSnapshot

_DB_PATH = Path.home() / ".dockerbrain" / "metrics.db"

_METRICS_SCHEMA = """
CREATE TABLE IF NOT EXISTS container_metrics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    container       TEXT    NOT NULL,
    status          TEXT,
    cpu_percent     REAL,
    mem_usage_mb    REAL,
    mem_limit_mb    REAL,
    mem_percent     REAL,
    net_rx_bytes    INTEGER,
    net_tx_bytes    INTEGER,
    is_idle         INTEGER DEFAULT 0,
    idle_polls      INTEGER DEFAULT 0
);
"""

_AI_SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT    NOT NULL,
    summary         TEXT    NOT NULL,
    full_response   TEXT
);
"""


def _get_connection() -> sqlite3.Connection:
    """Return a connection, creating the database and tables if needed."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    conn.execute(_METRICS_SCHEMA)
    conn.execute(_AI_SCHEMA)
    conn.commit()
    return conn

# Write
def store_snapshot(snap: ContainerSnapshot) -> None:
    """Persist a single ContainerSnapshot row."""
    with _get_connection() as conn:
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

def store_metrics(row: dict) -> None:
    """Legacy helper — accepts a plain dict (backward compat)."""
    with _get_connection() as conn:
        conn.execute(
            """
            INSERT INTO container_metrics
                (timestamp, container, cpu_percent,
                 mem_usage_mb, mem_limit_mb, mem_percent,
                 net_rx_bytes, net_tx_bytes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                row["name"],
                row["cpu_percent"],
                row.get("mem_usage_mb", row.get("mem_usage", 0) / (1024 * 1024)),
                row.get("mem_limit_mb", row.get("mem_limit", 0) / (1024 * 1024)),
                row["mem_percent"],
                row.get("net_rx_bytes", row.get("net_rx", 0)),
                row.get("net_tx_bytes", row.get("net_tx", 0)),
            ),
        )
        conn.commit()

# Read
def get_recent_metrics(container: str, limit: int = 60) -> list[dict]:
    """Retrieve the most recent *limit* rows for a given container."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM container_metrics WHERE container = ? ORDER BY id DESC LIMIT ?",
            (container, limit),
        )
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, r)) for r in cursor.fetchall()]


def get_metrics_since(since_iso: str, container: str | None = None) -> list[dict]:
    """Return all rows with timestamp >= *since_iso*.

    Args:
        since_iso: ISO-8601 UTC timestamp string (lower bound, inclusive).
        container: Optional container name filter.
    """
    with _get_connection() as conn:
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


def get_all_container_names() -> list[str]:
    """Return distinct container names from the metrics table."""
    with _get_connection() as conn:
        cursor = conn.execute("SELECT DISTINCT container FROM container_metrics ORDER BY container")
        return [row[0] for row in cursor.fetchall()]


# LLM suggestion cache
def store_ai_suggestion(summary: str, full_response: str = "") -> None:
    """Cache an AI suggestion for later retrieval."""
    with _get_connection() as conn:
        conn.execute(
            "INSERT INTO ai_suggestions (timestamp, summary, full_response) VALUES (?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), summary, full_response),
        )
        conn.commit()

def get_last_ai_suggestion() -> dict | None:
    """Retrieve the most recent AI suggestion row."""
    with _get_connection() as conn:
        cursor = conn.execute(
            "SELECT timestamp, summary, full_response FROM ai_suggestions ORDER BY id DESC LIMIT 1"
        )
        row = cursor.fetchone()
    if row:
        return {"timestamp": row[0], "summary": row[1], "full_response": row[2]}
    return None

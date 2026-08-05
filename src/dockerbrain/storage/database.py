"""Connection factory and schema creation."""

from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".dockerbrain" / "metrics.db"

# Module-level path — can be monkeypatched in tests
_DB_PATH = DEFAULT_DB_PATH

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


class Database:
    """Manages the SQLite connection and schema initialization."""

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or _DB_PATH

    def connect(self) -> sqlite3.Connection:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(_METRICS_SCHEMA)
        conn.execute(_AI_SCHEMA)
        conn.commit()
        return conn


def get_connection() -> sqlite3.Connection:
    """Module-level convenience function — uses _DB_PATH."""
    return Database(_DB_PATH).connect()

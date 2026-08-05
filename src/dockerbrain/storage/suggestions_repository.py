"""SuggestionsRepository — ai_suggestions table operations."""

from __future__ import annotations

from datetime import datetime, timezone

from dockerbrain.storage.database import Database


class SuggestionsRepository:
    """Repository for AI suggestion cache."""

    def __init__(self, database: Database | None = None) -> None:
        self._db = database or Database()

    def store(self, summary: str, full_response: str = "") -> None:
        """Cache an AI suggestion for later retrieval."""
        with self._db.connect() as conn:
            conn.execute(
                "INSERT INTO ai_suggestions (timestamp, summary, full_response) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), summary, full_response),
            )
            conn.commit()

    def get_last(self) -> dict | None:
        """Retrieve the most recent AI suggestion row."""
        with self._db.connect() as conn:
            cursor = conn.execute(
                "SELECT timestamp, summary, full_response FROM ai_suggestions ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
        if row:
            return {"timestamp": row[0], "summary": row[1], "full_response": row[2]}
        return None

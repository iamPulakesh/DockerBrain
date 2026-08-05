from __future__ import annotations
from textual.widgets import DataTable, Static

class SummaryBar(Static):
    """Displays global counts and stats."""
    pass

class ContainerTable(DataTable):
    """Table for displaying container snapshots."""
    def on_mount(self) -> None:
        self.add_columns(
            "  State",
            "Name",
            "Image",
            "CPU %",
            "MEM",
            "MEM %",
            "Net ↓ / ↑",
            "Status",
            "Uptime",
        )

"""UI updater mixin — table rendering, sorting, and row event handlers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dockerbrain.ui.cli.tables import format_bytes
from dockerbrain.ui.dashboard.widgets import SummaryBar, ContainerTable
from dockerbrain.ui.dashboard.sorter import sort_snapshots
from dockerbrain.ui.dashboard.formatters import (
    format_uptime, get_cpu_color, get_mem_color,
    STATUS_ICON, STATUS_STYLE,
)

if TYPE_CHECKING:
    from dockerbrain.monitor.snapshot import ContainerSnapshot
    from dockerbrain.ui.dashboard.app import DockerBrainMonitor


class UIUpdaterMixin:
    """Handles table rendering, in-place updates, sorting, and row events."""

    @staticmethod
    def _format_row(snapshot: "ContainerSnapshot") -> tuple[str, ...]:
        """Format a snapshot into a tuple of Rich-styled cell values."""
        icon = STATUS_ICON.get(snapshot.status, "? ")
        style = STATUS_STYLE.get(snapshot.status, "white")
        cpu_color = get_cpu_color(snapshot.cpu_percent)
        mem_color = get_mem_color(snapshot.mem_percent)
        status_text = "stopped" if snapshot.status == "exited" else snapshot.status
        return (
            f"[{style}]{icon}{status_text}[/]",
            f"[bold]{snapshot.name}[/]",
            f"[dim]{snapshot.image_tag}[/]",
            f"[{cpu_color}]{snapshot.cpu_percent:.1f}%[/]",
            f"{snapshot.mem_usage_mb:.1f} MB",
            f"[{mem_color}]{snapshot.mem_percent:.1f}%[/]",
            f"{format_bytes(snapshot.net_rx_bytes)} / {format_bytes(snapshot.net_tx_bytes)}",
            f"[bold {snapshot.health_style}]{snapshot.health_label}[/]",
            f"[dim]{format_uptime(snapshot.uptime_seconds)}[/]",
        )

    def _update_ui(self: "DockerBrainMonitor", snaps: list["ContainerSnapshot"]) -> None:
        """Redraw the table and summary bar from fresh snapshots."""
        table = self.query_one(ContainerTable)

        snaps = sort_snapshots(snaps, self._sort_key, self._sort_reverse)
        self._snapshots = snaps

        running = sum(1 for s in snaps if s.status == "running")
        stopped = sum(1 for s in snaps if s.status == "exited")
        paused = sum(1 for s in snaps if s.status == "paused")

        arrow = "asc" if not self._sort_reverse else "desc"
        sort_label = f"[dim cyan]sort: {self._sort_key} {arrow}[/]"

        summary = (
            f"[ansi_bright_green]{running} running[/]   "
            f"[bold red]{stopped} stopped[/]   "
            f"[bold #ff8c00]{paused} paused[/]   "
            f"[dim]total: {len(snaps)}[/]   "
            f"{sort_label}"
        )
        self.query_one("#summary_bar", SummaryBar).update(summary)

        current_names = [str(r.value) for r in table.rows.keys()]
        desired_names = [s.name for s in snaps]

        self._suppress_highlight = True
        try:
            if current_names != desired_names:
                table.clear()
                for s in snaps:
                    table.add_row(*self._format_row(s), key=s.name)

                if self._selected_name:
                    try:
                        for idx, key in enumerate(table.rows.keys()):
                            if str(key.value) == self._selected_name:
                                table.move_cursor(row=idx)
                                break
                    except Exception:
                        pass
            else:
                col_keys = list(table.columns.keys())
                for s in snaps:
                    row_data = self._format_row(s)
                    for col_idx, val in enumerate(row_data):
                        table.update_cell(s.name, col_keys[col_idx], val, update_width=True)
        finally:
            self._suppress_highlight = False

    def on_data_table_row_selected(
        self: "DockerBrainMonitor", event: ContainerTable.RowSelected
    ) -> None:
        self._pause_log_refresh = False
        self._selected_name = str(event.row_key.value)
        self._fetch_logs(self._selected_name)

    def on_data_table_row_highlighted(
        self: "DockerBrainMonitor", event: ContainerTable.RowHighlighted
    ) -> None:
        if self._suppress_highlight:
            return
        if event.row_key:
            new_name = str(event.row_key.value)
            if new_name != self._selected_name:
                self._pause_log_refresh = False
                self._selected_name = new_name
                self._fetch_logs(new_name)

    def action_cycle_sort(self: "DockerBrainMonitor") -> None:
        states = [
            ("name", False),
            ("name", True),
            ("cpu", True),
            ("cpu", False),
            ("mem", True),
            ("mem", False),
        ]
        current = (self._sort_key, self._sort_reverse)
        try:
            idx = states.index(current)
            next_idx = (idx + 1) % len(states)
        except ValueError:
            next_idx = 0

        next_state = states[next_idx]
        self._sort_key = next_state[0]
        self._sort_reverse = next_state[1]

        self._update_ui(self._snapshots)

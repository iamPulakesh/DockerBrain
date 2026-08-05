"""Textual TUI app — refactored to use extracted modules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, Log
from textual import work

from dockerbrain.ui.cli.tables import format_bytes
from dockerbrain.ui.dashboard.widgets import SummaryBar, ContainerTable
from dockerbrain.ui.dashboard.sorter import sort_snapshots
from dockerbrain.ui.dashboard.docker_actions import DockerActionService
from dockerbrain.ui.dashboard.formatters import (
    format_uptime, get_cpu_color, get_mem_color, 
    STATUS_ICON, STATUS_STYLE, parse_and_format_logs
)
from dockerbrain.ui.dashboard.app_mixins import ContainerLifecycleMixin

if TYPE_CHECKING:
    from dockerbrain.monitor.collector import ContainerMonitor
    from dockerbrain.monitor.snapshot import ContainerSnapshot


class DockerBrainMonitor(App, ContainerLifecycleMixin):
    """DockerBrain — Interactive Docker Monitor TUI."""

    TITLE = "DockerBrain Monitor"

    CSS = """
    Screen {
        background: $background;
    }
    SummaryBar {
        height: 3;
        background: $surface;
        border: hkey $accent;
        padding: 0 2;
        color: $text-muted;
    }
    #main_table {
        height: 1fr;
        border: round $primary;
    }
    ContainerTable {
        height: 1fr;
    }
    ContainerTable > .datatable--header {
        background: $primary-darken-2;
        color: $accent;
        text-style: bold;
    }
    ContainerTable > .datatable--cursor {
        background: $accent 30%;
        color: $text;
    }
    #log_pane {
        height: 15;
        border: round $primary;
    }
    Footer {
        background: $surface;
    }
    .logs-expanded #main_table {
        display: none;
    }
    .logs-expanded #summary_bar {
        display: none;
    }
    .logs-expanded #log_pane {
        height: 1fr;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "stop_container", "Stop"),
        Binding("p", "pause_container", "Start/Pause"),
        Binding("t", "restart_container", "Restart"),
        Binding("e", "toggle_expand", "Expand"),
        Binding("x", "remove_container", "Remove"),
        Binding("c", "cycle_sort", "Sort"),
        Binding("i", "scan_issues", "Scan Issues"),
    ]

    _snapshots: list[ContainerSnapshot] = []
    _selected_name: str | None = None
    _sort_key: str = "name"
    _sort_reverse: bool = False

    def __init__(
        self, monitor: ContainerMonitor, duration: int | None = None, **kwargs
    ):
        super().__init__(**kwargs)
        self._monitor = monitor
        self._duration = duration
        self._action_service = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Vertical():
            yield SummaryBar(id="summary_bar")
            with Container(id="main_table"):
                yield ContainerTable(zebra_stripes=True, cursor_type="row")
            yield Log(id="log_pane", auto_scroll=True, max_lines=500)
        yield Footer()

    def on_mount(self) -> None:
        if self._monitor.client:
            self._action_service = DockerActionService(self._monitor.client)
            
        self.set_interval(self._monitor.interval, self._poll_stats)
        if self._duration:
            self.set_timer(self._duration, lambda: self.exit())
        self._poll_stats()

    @work(thread=True)
    def _poll_stats(self) -> None:
        """Run ContainerMonitor.poll() in a background thread."""
        try:
            snaps = self._monitor.poll()
            
            # Lazy init action service if client connected late
            if not self._action_service and self._monitor.client:
                self._action_service = DockerActionService(self._monitor.client)
                
            self.call_from_thread(self._update_ui, snaps)
        except Exception as e:
            self.call_from_thread(
                self.query_one("#summary_bar", SummaryBar).update,
                f"[red]Error: {e}[/]",
            )

    def _update_ui(self, snaps: list[ContainerSnapshot]) -> None:
        """Redraw the table and summary bar from fresh snapshots."""
        table = self.query_one(ContainerTable)
        table.clear()

        snaps = sort_snapshots(snaps, self._sort_key, self._sort_reverse)
        self._snapshots = snaps

        running = sum(1 for s in snaps if s.status == "running")
        stopped = sum(1 for s in snaps if s.status == "exited")
        paused = sum(1 for s in snaps if s.status == "paused")
        total_cpu = sum(s.cpu_percent for s in snaps)
        total_mem = sum(s.mem_usage_mb for s in snaps)

        arrow = "↑" if not self._sort_reverse else "↓"
        sort_label = f"[dim cyan]sort: {self._sort_key} {arrow}[/]"

        summary = (
            f"[ansi_bright_green]● {running} running[/]   "
            f"[bold red]● {stopped} stopped[/]   "
            f"[bold #ff8c00]● {paused} paused[/]   "
            f"[dim]total: {len(snaps)}[/]   "
            f"[dim]CPU: {total_cpu:.1f}%[/]   "
            f"[dim]MEM: {total_mem:.0f} MB[/]   "
            f"{sort_label}"
        )
        self.query_one("#summary_bar", SummaryBar).update(summary)

        for s in snaps:
            icon = STATUS_ICON.get(s.status, "? ")
            style = STATUS_STYLE.get(s.status, "white")
            cpu_c = get_cpu_color(s.cpu_percent)
            mem_c = get_mem_color(s.mem_percent)
            status_text = "stopped" if s.status == "exited" else s.status

            table.add_row(
                f"[{style}]{icon}{status_text}[/]",
                f"[bold]{s.name}[/]",
                f"[dim]{s.image_tag}[/]",
                f"[{cpu_c}]{s.cpu_percent:.1f}%[/]",
                f"{s.mem_usage_mb:.1f} MB",
                f"[{mem_c}]{s.mem_percent:.1f}%[/]",
                f"↓{format_bytes(s.net_rx_bytes)} ↑{format_bytes(s.net_tx_bytes)}",
                f"[bold {s.health_style}]{s.health_label}[/]",
                f"[dim]{format_uptime(s.uptime_seconds)}[/]",
                key=s.name,
            )

        if self._selected_name:
            try:
                for idx, key in enumerate(table.rows.keys()):
                    if str(key.value) == self._selected_name:
                        table.move_cursor(row=idx)
                        break
            except Exception:
                pass

    def on_data_table_row_selected(self, event: ContainerTable.RowSelected) -> None:
        self._selected_name = str(event.row_key.value)
        self._fetch_logs(self._selected_name)

    def on_data_table_row_highlighted(self, event: ContainerTable.RowHighlighted) -> None:
        if event.row_key:
            new_name = str(event.row_key.value)
            if new_name != self._selected_name:
                self._selected_name = new_name
                self._fetch_logs(new_name)

    def action_cycle_sort(self) -> None:
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

    def action_toggle_expand(self) -> None:
        """Toggle fullscreen mode for the logs pane."""
        self.toggle_class("logs-expanded")

    def action_refresh(self) -> None:
        self._poll_stats()
        if self._selected_name:
            self._fetch_logs(self._selected_name)



    @work(thread=True)
    def _fetch_logs(self, target_name: str) -> None:
        if not target_name or not self._action_service:
            return
        try:
            raw_logs = self._action_service.fetch_logs(target_name)
            formatted_logs = parse_and_format_logs(raw_logs)

            if self._selected_name != target_name:
                return

            log_widget = self.query_one("#log_pane", Log)
            self.call_from_thread(log_widget.clear)
            self.call_from_thread(
                log_widget.write,
                f"=== Logs: {target_name} ===\n{formatted_logs}",
            )
        except Exception as e:
            if self._selected_name == target_name:
                self.call_from_thread(self.notify, str(e), severity="error")



from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Label,
    Static,
    ProgressBar,
    TabbedContent,
    TabPane,
    Log,
)
from textual import work

from core.monitor.snapshot import (
    ContainerSnapshot,
    MEM_WARNING_PCT,
    MEM_CRITICAL_PCT,
)
from core.utils import format_bytes

if TYPE_CHECKING:
    from core.monitor.collector import ContainerMonitor


def _format_uptime(seconds: float) -> str:
    """Convert seconds to a human-readable uptime string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    if seconds < 3600:
        return f"{seconds / 60:.0f}m"
    hours = seconds // 3600
    mins = (seconds % 3600) // 60
    if hours < 24:
        return f"{hours:.0f}h {mins:.0f}m"
    days = hours // 24
    hours = hours % 24
    return f"{days:.0f}d {hours:.0f}h"


def _cpu_color(pct: float) -> str:
    """Return a color name for a CPU percentage."""
    if pct > 80:
        return "red"
    if pct > 50:
        return "yellow"
    return "green"


def _mem_color(pct: float) -> str:
    """Return a color name for a memory percentage."""
    if pct > MEM_CRITICAL_PCT:
        return "red"
    if pct > MEM_WARNING_PCT:
        return "yellow"
    return "cyan"

STATUS_ICON = {
    "running": "● ",
    "exited":  "● ",
    "paused":  "● ",
    "created": "◌ ",
    "dead":    "✗ ",
}

STATUS_STYLE = {
    "running": "bold green",
    "exited":  "bold #FF0000",
    "paused":  "bold #ff8c00",
    "created": "cyan",
    "dead":    "bold red",
}

class StatBar(Static):
    """A labeled progress bar for a single metric."""

    DEFAULT_CSS = """
    StatBar {
        height: 3;
        margin-bottom: 1;
    }
    StatBar Label {
        color: $text-muted;
    }
    """

    def __init__(self, label: str, bar_id: str, **kwargs):
        super().__init__(**kwargs)
        self._label = label
        self._bar_id = bar_id

    def compose(self) -> ComposeResult:
        yield Label(f"{self._label}: —")
        yield ProgressBar(total=100, show_eta=False, show_percentage=True, id=self._bar_id)

    def update_stat(self, pct: float, detail: str):
        try:
            self.query_one(Label).update(f"{self._label}: {detail}")
            self.query_one(ProgressBar).progress = min(pct, 100)
        except Exception:
            pass

class ContainerDetail(Static):
    """Expandable detail panel for the selected container."""

    DEFAULT_CSS = """
    ContainerDetail {
        border: round $accent;
        padding: 1 2;
        height: auto;
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("Select a container from the table above", id="detail_header")
        yield StatBar("CPU ", bar_id="bar_cpu", id="cpu_stat")
        yield StatBar("MEM ", bar_id="bar_mem", id="mem_stat")
        yield StatBar("NET↓", bar_id="bar_net", id="net_stat")
        yield Label("", id="detail_footer")

    def refresh_snapshot(self, snap: ContainerSnapshot):
        """Update every element in the detail panel from a snapshot."""
        try:
            icon = STATUS_ICON.get(snap.status, "? ")
            style = STATUS_STYLE.get(snap.status, "white")
            status_text = "stopped" if snap.status == "exited" else snap.status
            self.query_one("#detail_header", Label).update(
                f"[bold cyan]{snap.name}[/]  "
                f"[dim]{snap.image_tag}[/]  "
                f"[{style}]{icon}{status_text}[/]  "
                f"[dim]uptime {_format_uptime(snap.uptime_seconds)}[/]"
            )

            cpu_c = _cpu_color(snap.cpu_percent)
            self.query_one("#cpu_stat", StatBar).update_stat(
                snap.cpu_percent,
                f"[{cpu_c}]{snap.cpu_percent:.1f}%[/]",
            )

            mem_c = _mem_color(snap.mem_percent)
            self.query_one("#mem_stat", StatBar).update_stat(
                snap.mem_percent,
                f"[{mem_c}]{snap.mem_usage_mb:.1f} / {snap.mem_limit_mb:.0f} MB "
                f"({snap.mem_percent:.1f}%)[/]",
            )

            self.query_one("#net_stat", StatBar).update_stat(
                min(snap.net_rx_bytes / 1_000_000, 100),
                f"↓{format_bytes(snap.net_rx_bytes)}  ↑{format_bytes(snap.net_tx_bytes)}",
            )

            errs = snap.net_rx_errors + snap.net_tx_errors
            drops = snap.net_rx_dropped + snap.net_tx_dropped
            err_s = "bold red" if errs else "dim"
            drop_s = "bold red" if drops else "dim"

            self.query_one("#detail_footer", Label).update(
                f"  [bold {snap.health_style}]{snap.health_label}[/]  "
                f"[dim]restarts:[/] {snap.restart_count}  "
                f"[dim]idle polls:[/] {snap.idle_polls}  "
                f"[{err_s}]errors: {errs}[/]  "
                f"[{drop_s}]drops: {drops}[/]"
            )
        except Exception:
            pass


class DockerBrainMonitor(App):
    """DockerBrain — Interactive Docker Monitor TUI."""

    TITLE = "DockerBrain Monitor"

    CSS = """
    Screen {
        background: $background;
    }
    #summary_bar {
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
    DataTable {
        height: 1fr;
    }
    DataTable > .datatable--header {
        background: $primary-darken-2;
        color: $accent;
        text-style: bold;
    }
    DataTable > .datatable--cursor {
        background: $accent 30%;
        color: $text;
    }
    #detail_panel {
        height: auto;
        max-height: 16;
    }
    #log_pane {
        height: 1fr;
        border: round $primary;
    }
    Footer {
        background: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("s", "stop_container", "Stop"),
        Binding("p", "pause_container", "Start/Pause"),
        Binding("t", "restart_container", "Restart"),
        Binding("x", "remove_container", "Remove"),
        Binding("d", "toggle_detail", "Detail"),

        Binding("c", "sort_cpu", "Sort:CPU"),
        Binding("m", "sort_mem", "Sort:Mem"),
        Binding("1", "tab_monitor", "1:Monitor", show=False),
        Binding("2", "view_logs", "2:Logs", show=False),
    ]

    _snapshots: list[ContainerSnapshot] = []
    _selected_name: str | None = None
    _sort_key: str = "name"
    _sort_reverse: bool = False

    def __init__(self, monitor: ContainerMonitor, duration: int | None = None, **kwargs):
        super().__init__(**kwargs)
        self._monitor = monitor
        self._duration = duration

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with TabbedContent(initial="monitor"):
            with TabPane("  Monitor  ", id="monitor"):
                with Vertical():
                    yield Static(id="summary_bar")
                    with Container(id="main_table"):
                        yield DataTable(zebra_stripes=True, cursor_type="row")
                    with Container(id="detail_panel"):
                        yield ContainerDetail(id="detail_view")
            with TabPane("  Logs  ", id="logs"):
                yield Log(id="log_pane", auto_scroll=True, max_lines=500)
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns(
            "  State", "Name", "Image", "CPU %", "MEM",
            "MEM %", "Net ↓ / ↑", "Status", "Uptime",
        )
        self.set_interval(self._monitor.interval, self._poll_stats)
        if self._duration:
            self.set_timer(self._duration, lambda: self.exit())
        self._poll_stats()

    @work(thread=True)
    def _poll_stats(self) -> None:
        """Run ContainerMonitor.poll() in a background thread."""
        try:
            snaps = self._monitor.poll()
            self.call_from_thread(self._update_ui, snaps)
        except Exception as e:
            self.call_from_thread(
                self.query_one("#summary_bar", Static).update,
                f"[red]Error: {e}[/]",
            )

    def _update_ui(self, snaps: list[ContainerSnapshot]) -> None:
        """Redraw the table and summary bar from fresh snapshots."""
        self._snapshots = snaps
        table = self.query_one(DataTable)
        table.clear()

        running = sum(1 for s in snaps if s.status == "running")
        stopped = sum(1 for s in snaps if s.status == "exited")
        paused = sum(1 for s in snaps if s.status == "paused")
        idle = sum(1 for s in snaps if s.is_idle)
        total_cpu = sum(s.cpu_percent for s in snaps)
        total_mem = sum(s.mem_usage_mb for s in snaps)

        # Apply sorting
        sort_map = {
            "name": lambda s: s.name.lower(),
            "cpu":  lambda s: s.cpu_percent,
            "mem":  lambda s: s.mem_usage_mb,
        }
        key_fn = sort_map.get(self._sort_key, sort_map["name"])
        snaps = sorted(snaps, key=key_fn, reverse=self._sort_reverse)
        self._snapshots = snaps

        arrow = "↑" if not self._sort_reverse else "↓"
        sort_label = f"[dim cyan]sort: {self._sort_key} {arrow}[/]"

        summary = (
            f"[ansi_bright_green]● {running} running[/]   "
            f"[bold red]● {stopped} stopped[/]   "
            f"[bold #ff8c00]● {paused} paused[/]   "
        )
        summary += (
            f"[dim]total: {len(snaps)}[/]   "
            f"[dim]CPU: {total_cpu:.1f}%[/]   "
            f"[dim]MEM: {total_mem:.0f} MB[/]   "
            f"{sort_label}"
        )
        self.query_one("#summary_bar", Static).update(summary)

        for s in snaps:
            icon = STATUS_ICON.get(s.status, "? ")
            style = STATUS_STYLE.get(s.status, "white")
            cpu_c = _cpu_color(s.cpu_percent)
            mem_c = _mem_color(s.mem_percent)

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
                f"[dim]{_format_uptime(s.uptime_seconds)}[/]",
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
            self._update_detail(self._selected_name)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        self._selected_name = str(event.row_key.value)
        self._update_detail(self._selected_name)

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key:
            self._selected_name = str(event.row_key.value)
            self._update_detail(self._selected_name)

    def _update_detail(self, name: str) -> None:
        for s in self._snapshots:
            if s.name == name:
                self.query_one("#detail_view", ContainerDetail).refresh_snapshot(s)
                break

    def _toggle_sort(self, key: str, default_reverse: bool = False) -> None:
        if self._sort_key == key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_key = key
            self._sort_reverse = default_reverse
        self._update_ui(self._snapshots)



    def action_sort_cpu(self) -> None:
        self._toggle_sort("cpu", default_reverse=True)

    def action_sort_mem(self) -> None:
        self._toggle_sort("mem", default_reverse=True)

    def action_refresh(self) -> None:
        self._poll_stats()

    def action_toggle_detail(self) -> None:
        panel = self.query_one("#detail_panel")
        panel.display = not panel.display

    def action_tab_monitor(self) -> None:
        self.query_one(TabbedContent).active = "monitor"

    def action_stop_container(self) -> None:
        if not self._selected_name:
            self.notify("No container selected", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status == "running":
                self._do_stop(s.name)
                return
        self.notify("Container is not running", severity="warning")

    @work(thread=True)
    def _do_stop(self, name: str) -> None:
        try:
            ctr = self._monitor.client.containers.get(name)
            ctr.stop()
            self.call_from_thread(self.notify, f"Stopped {name}")
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_pause_container(self) -> None:
        if not self._selected_name:
            self.notify("No container selected", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name:
                self._do_pause(s.name, s.status)
                return

    @work(thread=True)
    def _do_pause(self, name: str, status: str) -> None:
        try:
            ctr = self._monitor.client.containers.get(name)
            if status == "running":
                ctr.pause()
                self.call_from_thread(self.notify, f"Paused {name}")
            elif status == "paused":
                ctr.unpause()
                self.call_from_thread(self.notify, f"Resumed {name}")
            elif status in ("exited", "created"):
                ctr.start()
                self.call_from_thread(self.notify, f"Started {name}")
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_restart_container(self) -> None:
        if not self._selected_name:
            self.notify("No container selected", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status in ("running", "paused"):
                self._do_restart(s.name)
                return
        self.notify("Container is not running", severity="warning")

    @work(thread=True)
    def _do_restart(self, name: str) -> None:
        try:
            ctr = self._monitor.client.containers.get(name)
            self.call_from_thread(self.notify, f"Restarting {name}...")
            ctr.restart()
            self.call_from_thread(self.notify, f"Restarted {name}")
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_remove_container(self) -> None:
        if not self._selected_name:
            self.notify("No container selected", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status in ("exited", "created"):
                self._do_remove(s.name)
                return
        self.notify("Only stopped containers can be removed", severity="warning")

    @work(thread=True)
    def _do_remove(self, name: str) -> None:
        try:
            ctr = self._monitor.client.containers.get(name)
            ctr.remove(force=True)
            self.call_from_thread(self.notify, f"Removed {name}")
            self._selected_name = None
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    @work(thread=True)
    def action_view_logs(self) -> None:
        if not self._selected_name:
            self.call_from_thread(
                self.notify, "No container selected", severity="warning",
            )
            return
        try:
            ctr = self._monitor.client.containers.get(self._selected_name)
            logs = ctr.logs(tail=200, timestamps=True).decode("utf-8", errors="replace")
            log_widget = self.query_one("#log_pane", Log)
            self.call_from_thread(log_widget.clear)
            self.call_from_thread(
                log_widget.write,
                f"=== Logs: {self._selected_name} ===\n{logs}",
            )
            self.call_from_thread(
                setattr, self.query_one(TabbedContent), "active", "logs",
            )
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

"""DockerBrain TUI app — thin orchestrator that composes mixins."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical
from textual.widgets import Header, Footer, RichLog

from dockerbrain.ui.dashboard.widgets import SummaryBar, ContainerTable
from dockerbrain.ui.dashboard.docker_actions import DockerActionService
from dockerbrain.ui.dashboard.polling import PollingMixin
from dockerbrain.ui.dashboard.ui_updater import UIUpdaterMixin
from dockerbrain.ui.dashboard.app_mixins import ContainerLifecycleMixin

if TYPE_CHECKING:
    from dockerbrain.monitor.collector import ContainerMonitor
    from dockerbrain.monitor.snapshot import ContainerSnapshot


class DockerBrainMonitor(App, PollingMixin, UIUpdaterMixin, ContainerLifecycleMixin):
    """DockerBrain -- Interactive Docker Monitor TUI."""

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
    _suppress_highlight: bool = False
    _is_polling: bool = False
    _pause_log_refresh: bool = False

    def __init__(
        self, monitor: "ContainerMonitor", duration: int | None = None, **kwargs
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
            yield RichLog(id="log_pane", auto_scroll=True, max_lines=500, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        if self._monitor.client:
            self._action_service = DockerActionService(self._monitor.client)

        self.set_interval(self._monitor.interval, self._poll_stats)
        if self._duration:
            self.set_timer(self._duration, lambda: self.exit())
        self._poll_stats()

    def action_toggle_expand(self) -> None:
        """Toggle fullscreen mode for the logs pane."""
        self.toggle_class("logs-expanded")

    def action_refresh(self) -> None:
        self._pause_log_refresh = False
        self._poll_stats()

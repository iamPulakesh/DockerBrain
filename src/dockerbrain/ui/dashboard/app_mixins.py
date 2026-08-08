from __future__ import annotations

from typing import TYPE_CHECKING
from textual import work
from textual.widgets import RichLog

if TYPE_CHECKING:
    from dockerbrain.ui.dashboard.app import DockerBrainMonitor

class ContainerLifecycleMixin:
    """Mixin for DockerBrainMonitor containing container action handlers."""

    def action_stop_container(self: "DockerBrainMonitor") -> None:
        if not self._selected_name or not self._action_service:
            self.notify("Cannot perform action", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status == "running":
                self._do_stop(s.name)
                return
        self.notify("Container is not running", severity="warning")

    @work(thread=True)
    def _do_stop(self: "DockerBrainMonitor", name: str) -> None:
        try:
            self._action_service.stop_container(name)
            self.call_from_thread(self.notify, f"Stopped {name}")
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_pause_container(self: "DockerBrainMonitor") -> None:
        if not self._selected_name or not self._action_service:
            self.notify("Cannot perform action", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name:
                self._do_pause(s.name, s.status)
                return

    @work(thread=True)
    def _do_pause(self: "DockerBrainMonitor", name: str, status: str) -> None:
        try:
            msg = self._action_service.pause_container(name, status)
            if msg:
                self.call_from_thread(self.notify, msg)
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_restart_container(self: "DockerBrainMonitor") -> None:
        if not self._selected_name or not self._action_service:
            self.notify("Cannot perform action", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status in ("running", "paused"):
                self._do_restart(s.name)
                return
        self.notify("Container is not running", severity="warning")

    @work(thread=True)
    def _do_restart(self: "DockerBrainMonitor", name: str) -> None:
        try:
            self.call_from_thread(self.notify, f"Restarting {name}...")
            self._action_service.restart_container(name)
            self.call_from_thread(self.notify, f"Restarted {name}")
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    def action_remove_container(self: "DockerBrainMonitor") -> None:
        if not self._selected_name or not self._action_service:
            self.notify("Cannot perform action", severity="warning")
            return
        for s in self._snapshots:
            if s.name == self._selected_name and s.status in ("exited", "created"):
                self._do_remove(s.name)
                return
        self.notify("Only stopped containers can be removed", severity="warning")

    @work(thread=True)
    def _do_remove(self: "DockerBrainMonitor", name: str) -> None:
        try:
            self._action_service.remove_container(name)
            self.call_from_thread(self.notify, f"Removed {name}")
            self._selected_name = None
            self._poll_stats()
        except Exception as e:
            self.call_from_thread(self.notify, str(e), severity="error")

    @work(thread=True)
    def action_scan_issues(self: "DockerBrainMonitor") -> None:
        from dockerbrain.monitor.log_analyzer import check_container_status, analyze_logs_stream

        if not self._selected_name or not self._monitor.client:
            self.call_from_thread(self.notify, "Cannot scan right now", severity="warning")
            return

        self._pause_log_refresh = True

        log_widget = self.query_one("#log_pane", RichLog)
        self.call_from_thread(log_widget.clear)
        self.call_from_thread(log_widget.write, f"Scanning {self._selected_name}...\n")

        result = check_container_status(self._monitor.client, self._selected_name)

        if result.healthy:
            self.call_from_thread(log_widget.write, f"\n{result.message}\n")
            return

        self.call_from_thread(log_widget.write, f"\n{result.message[:-1]}, Please wait...\n\n")

        try:
            buffer = ""
            for chunk in analyze_logs_stream(self._monitor.client, self._selected_name):
                buffer += chunk
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self.call_from_thread(log_widget.write, line)
            if buffer:
                self.call_from_thread(log_widget.write, buffer)
            self.call_from_thread(log_widget.write, "\n\n--- End of Analysis ---\n")
        except Exception as e:
            self.call_from_thread(log_widget.write, f"\n LLM analysis failed: {e}\n")

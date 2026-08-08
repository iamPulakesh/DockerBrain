"""Polling mixin — background stats collection and log refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.widgets import RichLog

from dockerbrain.ui.dashboard.docker_actions import DockerActionService
from dockerbrain.ui.dashboard.formatters import parse_and_format_logs

if TYPE_CHECKING:
    from dockerbrain.ui.dashboard.app import DockerBrainMonitor


class PollingMixin:
    """Handles background polling of Docker stats and log refresh."""

    @work(thread=True)
    def _poll_stats(self: "DockerBrainMonitor") -> None:
        """Run ContainerMonitor.poll() in a background thread."""
        if self._is_polling:
            return
        self._is_polling = True
        try:
            snaps = self._monitor.poll()

            if not self._action_service and self._monitor.client:
                self._action_service = DockerActionService(self._monitor.client)

            self.call_from_thread(self._update_ui, snaps)

            # Auto-refresh logs for the selected container
            if self._selected_name and self._action_service:
                self._refresh_logs(self._selected_name)
        except Exception:
            pass
        finally:
            self._is_polling = False

    def _refresh_logs(self: "DockerBrainMonitor", container_name: str) -> None:
        """Fetch and display logs for a container (called from poll thread)."""
        if self._pause_log_refresh:
            return
        try:
            raw_logs = self._action_service.fetch_logs(container_name)
            formatted_logs = parse_and_format_logs(raw_logs)
            log_widget = self.query_one("#log_pane", RichLog)
            self.call_from_thread(log_widget.clear)
            self.call_from_thread(
                log_widget.write,
                f"=== Logs: {container_name} ===\n{formatted_logs}",
            )
        except Exception:
            pass

    @work(thread=True)
    def _fetch_logs(self: "DockerBrainMonitor", target_name: str) -> None:
        """Fetch logs on demand (triggered by row selection)."""
        if not target_name or not self._action_service:
            return
        try:
            raw_logs = self._action_service.fetch_logs(target_name)
            formatted_logs = parse_and_format_logs(raw_logs)

            if self._selected_name != target_name:
                return

            log_widget = self.query_one("#log_pane", RichLog)
            self.call_from_thread(log_widget.clear)
            self.call_from_thread(
                log_widget.write,
                f"=== Logs: {target_name} ===\n{formatted_logs}",
            )
        except Exception as exc:
            if self._selected_name == target_name:
                self.call_from_thread(self.notify, str(exc), severity="error")

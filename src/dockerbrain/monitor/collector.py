"""ContainerMonitor — polls Docker, stores snapshots via injected repository."""

from __future__ import annotations

import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

from dockerbrain.docker_client.connection import connect_docker
from dockerbrain.docker_client.metrics import calc_cpu_percent, parse_container_stats
from dockerbrain.monitor.snapshot import (
    ContainerSnapshot,
    IDLE_CPU_THRESHOLD,
    IDLE_CONSECUTIVE_POLLS,
)
from dockerbrain.storage.metrics_repository import MetricsRepository


class ContainerMonitor:
    """Polls Docker container stats and tracks idle state."""

    def __init__(
        self,
        interval: int = 1,
        metrics_repo: MetricsRepository | None = None,
    ) -> None:
        self.interval = interval
        self.client = connect_docker()
        self._metrics_repo = metrics_repo or MetricsRepository()
        self._idle_counter: dict[str, int] = defaultdict(int)
        self._paused_uptime: dict[str, float] = {}
        self._lock = threading.Lock()

    def _fetch_one(self, ctr: object) -> ContainerSnapshot | None:
        """Fetch stats for a single container. Returns None on any error."""
        try:
            raw = ctr.stats(stream=False)
            ctr.reload()

            cpu = calc_cpu_percent(raw)
            status = ctr.status
            started_at = ctr.attrs.get("State", {}).get("StartedAt", "")
            prev_uptime = self._paused_uptime.get(ctr.name, 0.0)

            parsed = parse_container_stats(
                raw=raw,
                status=status,
                previous_paused_uptime=prev_uptime,
                started_at=started_at,
            )

            if status == "running":
                self._paused_uptime[ctr.name] = parsed["uptime_seconds"]
            elif status not in ("running", "paused"):
                self._paused_uptime.pop(ctr.name, None)

            restart_count = ctr.attrs.get("RestartCount", 0)
            image_tag = ctr.image.tags[0] if ctr.image.tags else ctr.image.short_id

            with self._lock:
                if cpu < IDLE_CPU_THRESHOLD:
                    self._idle_counter[ctr.name] += 1
                else:
                    self._idle_counter[ctr.name] = 0
                idle_polls = self._idle_counter[ctr.name]

            return ContainerSnapshot(
                name=ctr.name,
                status=ctr.status,
                cpu_percent=cpu,
                mem_usage_mb=parsed["mem_usage_mb"],
                mem_limit_mb=parsed["mem_limit_mb"],
                mem_percent=parsed["mem_percent"],
                mem_cache_mb=parsed["mem_cache_mb"],
                net_rx_bytes=parsed["net_rx_bytes"],
                net_tx_bytes=parsed["net_tx_bytes"],
                is_idle=idle_polls >= IDLE_CONSECUTIVE_POLLS,
                idle_polls=idle_polls,
                uptime_seconds=parsed["uptime_seconds"],
                restart_count=restart_count,
                image_tag=image_tag,
            )
        except Exception:
            return None

    def poll(self) -> list[ContainerSnapshot]:
        """Collect one snapshot for every container in parallel."""
        containers = self.client.containers.list(all=True)
        if not containers:
            return []

        snapshots: list[ContainerSnapshot] = []

        with ThreadPoolExecutor(max_workers=min(len(containers), 20)) as pool:
            futures = {pool.submit(self._fetch_one, ctr): ctr for ctr in containers}
            for fut in as_completed(futures):
                try:
                    result = fut.result()
                except Exception:
                    continue
                if result is not None:
                    snapshots.append(result)
                    self._metrics_repo.store_snapshot(result)

        snapshots.sort(key=lambda s: s.name)
        return snapshots


def run_monitor(interval: int = 1, duration: int | None = None) -> None:
    """Create a ContainerMonitor and launch the interactive TUI."""
    monitor = ContainerMonitor(interval=interval)

    from dockerbrain.ui.dashboard.app import DockerBrainMonitor

    app = DockerBrainMonitor(monitor=monitor, duration=duration)
    app.run()

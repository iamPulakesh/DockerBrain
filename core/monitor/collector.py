from __future__ import annotations

import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import docker
from docker.errors import APIError, DockerException
from rich.console import Console

from rich.panel import Panel

from core.monitor.snapshot import (
    ContainerSnapshot,
    IDLE_CPU_THRESHOLD,
    IDLE_CONSECUTIVE_POLLS,
)

from core.storage import store_snapshot
from core.utils import calc_cpu_percent, get_docker_offline_hint

console = Console()


class ContainerMonitor:
    """Polls Docker container stats and tracks idle state."""

    def __init__(self, interval: int = 1) -> None:
        self.interval = interval
        self.client = self._connect()
        self._idle_counter: dict[str, int] = defaultdict(int)
        self._paused_uptime: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _connect() -> docker.DockerClient:
        try:
            return docker.from_env()
        except DockerException as exc:
            console.print(
                Panel(
                    "[red bold]Could not connect to Docker daemon.[/]\n\n"
                    f"{get_docker_offline_hint()}\n\n",
                    title="[bold red]Docker Unavailable[/]",
                    border_style="red",
                    expand=False,
                )
            )
            raise SystemExit(3) from exc

    def _fetch_one(self, ctr: object) -> ContainerSnapshot | None:
        """Fetch stats for a single container."""
        try:
            raw = ctr.stats(stream=False)
            ctr.reload()
        except (APIError, DockerException) as exc:
            console.print(f"[yellow] Skipping {ctr.name}: {exc}[/]", highlight=False)
            return None

        cpu = calc_cpu_percent(raw)

        mem_stats = raw.get("memory_stats", {})
        mem_raw = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 1)

        cache = mem_stats.get("stats", {}).get("inactive_file", 0)
        if not cache:
            cache = mem_stats.get("stats", {}).get("cache", 0)
        mem_usage = mem_raw - cache

        mem_usage_mb = mem_usage / (1024 * 1024)
        mem_limit_mb = mem_limit / (1024 * 1024)
        mem_percent = (mem_usage / mem_limit) * 100.0 if mem_limit else 0.0

        networks = raw.get("networks", {})
        net_rx = sum(v.get("rx_bytes", 0) for v in networks.values())
        net_tx = sum(v.get("tx_bytes", 0) for v in networks.values())
        net_rx_pkts = sum(v.get("rx_packets", 0) for v in networks.values())
        net_tx_pkts = sum(v.get("tx_packets", 0) for v in networks.values())
        net_rx_errs = sum(v.get("rx_errors", 0) for v in networks.values())
        net_tx_errs = sum(v.get("tx_errors", 0) for v in networks.values())
        net_rx_drop = sum(v.get("rx_dropped", 0) for v in networks.values())
        net_tx_drop = sum(v.get("tx_dropped", 0) for v in networks.values())

        uptime_secs = 0.0
        status = ctr.status

        if status == "running":
            started_at = ctr.attrs.get("State", {}).get("StartedAt", "")
            if started_at:
                try:
                    start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                    uptime_secs = (datetime.now(timezone.utc) - start_dt).total_seconds()
                except (ValueError, TypeError):
                    pass
    
            self._paused_uptime[ctr.name] = uptime_secs
        elif status == "paused":

            uptime_secs = self._paused_uptime.get(ctr.name, 0.0)
        else:
    
            uptime_secs = 0.0
            self._paused_uptime.pop(ctr.name, None)

        restart_count = ctr.attrs.get("RestartCount", 0)
        image_tag = ctr.image.tags[0] if ctr.image.tags else ctr.image.short_id

        with self._lock:
            if cpu < IDLE_CPU_THRESHOLD:
                self._idle_counter[ctr.name] += 1
            else:
                self._idle_counter[ctr.name] = 0
            idle_polls = self._idle_counter[ctr.name]

        is_idle = idle_polls >= IDLE_CONSECUTIVE_POLLS

        return ContainerSnapshot(
            name=ctr.name,
            status=ctr.status,
            cpu_percent=cpu,
            mem_usage_mb=mem_usage_mb,
            mem_limit_mb=mem_limit_mb,
            mem_percent=mem_percent,
            mem_cache_mb=cache / (1024 * 1024),
            net_rx_bytes=net_rx,
            net_tx_bytes=net_tx,
            net_rx_packets=net_rx_pkts,
            net_tx_packets=net_tx_pkts,
            net_rx_errors=net_rx_errs,
            net_tx_errors=net_tx_errs,
            net_rx_dropped=net_rx_drop,
            net_tx_dropped=net_tx_drop,
            is_idle=is_idle,
            idle_polls=idle_polls,
            uptime_seconds=uptime_secs,
            restart_count=restart_count,
            image_tag=image_tag,
        )

    def poll(self) -> list[ContainerSnapshot]:
        """Collect one snapshot for every running container in parallel.
        Uses a thread pool so N containers finish in ~1s (time of slowest
        single stats call), not N seconds.
        """
        containers = self.client.containers.list(all=True)
        if not containers:
            return []

        snapshots: list[ContainerSnapshot] = []

        with ThreadPoolExecutor(max_workers=min(len(containers), 20)) as pool:
            futures = {pool.submit(self._fetch_one, ctr): ctr for ctr in containers}
            for fut in as_completed(futures):
                result = fut.result()
                if result is not None:
                    snapshots.append(result)
                    store_snapshot(result)

        snapshots.sort(key=lambda s: s.name)
        return snapshots


def run_monitor(interval: int = 1, duration: int | None = None) -> None:
    """Create a ContainerMonitor and launch the interactive TUI."""
    monitor = ContainerMonitor(interval=interval)

    from core.monitor.display import DockerBrainMonitor

    app = DockerBrainMonitor(monitor=monitor, duration=duration)
    app.run()

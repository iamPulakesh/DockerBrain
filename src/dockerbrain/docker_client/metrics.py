"""Docker-stats-specific CPU calculation."""

from __future__ import annotations


from datetime import datetime, timezone


def calc_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from Docker stats JSON.

    Uses the same formula as ``docker stats``::

        delta_container / delta_system * num_cpus * 100
    """
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})

    container_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get(
        "cpu_usage", {}
    ).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    num_cpus = cpu.get("online_cpus") or len(
        cpu.get("cpu_usage", {}).get("percpu_usage", []) or [1]
    )

    if system_delta > 0 and container_delta > 0:
        return (container_delta / system_delta) * num_cpus * 100.0
    return 0.0


def parse_container_stats(
    raw: dict,
    status: str,
    previous_paused_uptime: float = 0.0,
    started_at: str = "",
) -> dict:
    """Pure transform: raw Docker stats dict -> typed metric fields.
    Returns a dict with keys: mem_usage_mb, mem_limit_mb, mem_percent,
    mem_cache_mb, net_rx_bytes, net_tx_bytes, net_rx_packets, net_tx_packets,
    net_rx_errors, net_tx_errors, net_rx_dropped, net_tx_dropped, uptime_seconds.
    No side effects, no I/O, no class state — must be independently unit-testable
    with a plain dict fixture."""
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
    if status == "running":
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00"))
                uptime_secs = (datetime.now(timezone.utc) - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass
    elif status == "paused":
        uptime_secs = previous_paused_uptime

    return {
        "mem_usage_mb": mem_usage_mb,
        "mem_limit_mb": mem_limit_mb,
        "mem_percent": mem_percent,
        "mem_cache_mb": cache / (1024 * 1024),
        "net_rx_bytes": net_rx,
        "net_tx_bytes": net_tx,
        "net_rx_packets": net_rx_pkts,
        "net_tx_packets": net_tx_pkts,
        "net_rx_errors": net_rx_errs,
        "net_tx_errors": net_tx_errs,
        "net_rx_dropped": net_rx_drop,
        "net_tx_dropped": net_tx_drop,
        "uptime_seconds": uptime_secs,
    }

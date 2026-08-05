from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

IDLE_CPU_THRESHOLD: float = 0.5
IDLE_CONSECUTIVE_POLLS: int = 10
MEM_WARNING_PCT: float = 70.0
MEM_CRITICAL_PCT: float = 85.0


@dataclass
class ContainerSnapshot:
    """One point-in-time snapshot of a container's resource usage."""

    name: str
    status: str
    cpu_percent: float
    mem_usage_mb: float
    mem_limit_mb: float
    mem_percent: float
    net_rx_bytes: int
    net_tx_bytes: int
    net_rx_packets: int = 0
    net_tx_packets: int = 0
    net_rx_errors: int = 0
    net_tx_errors: int = 0
    net_rx_dropped: int = 0
    net_tx_dropped: int = 0
    mem_cache_mb: float = 0.0
    is_idle: bool = False
    idle_polls: int = 0
    uptime_seconds: float = 0.0
    restart_count: int = 0
    image_tag: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def health_style(self) -> str:
        """Return a Rich style string based on health status."""
        if self.is_idle:
            return "red"
        if self.mem_percent > MEM_CRITICAL_PCT:
            return "red"
        if self.mem_percent > MEM_WARNING_PCT:
            return "yellow"
        return "green"

    @property
    def health_label(self) -> str:
        if self.is_idle:
            return "IDLE"
        if self.mem_percent > MEM_CRITICAL_PCT:
            return "CRITICAL"
        if self.mem_percent > MEM_WARNING_PCT:
            return "WARNING"
        return "HEALTHY"

from __future__ import annotations
import sys

def format_bytes(b: int | float) -> str:
    """Human-readable byte string (e.g. 1.23 GiB)."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(b) < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PiB"


def calc_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from Docker stats JSON.

    Uses the same formula as ``docker stats``:
        delta_container / delta_system * num_cpus * 100
    """
    cpu = stats.get("cpu_stats", {})
    precpu = stats.get("precpu_stats", {})

    container_delta = cpu.get("cpu_usage", {}).get("total_usage", 0) - precpu.get("cpu_usage", {}).get("total_usage", 0)
    system_delta = cpu.get("system_cpu_usage", 0) - precpu.get("system_cpu_usage", 0)
    num_cpus = cpu.get("online_cpus") or len(cpu.get("cpu_usage", {}).get("percpu_usage", []) or [1])

    if system_delta > 0 and container_delta > 0:
        return (container_delta / system_delta) * num_cpus * 100.0
    return 0.0


def get_docker_offline_hint() -> str:
    """Return an OS-specific hint for starting Docker."""
    if sys.platform == "win32":
        return "Make sure Docker Desktop is running, then try again."
    elif sys.platform == "darwin":
        return "Make sure Docker Desktop (or OrbStack/Colima) is running, then try again."
    else:
        return "Make sure the Docker daemon is running (e.g. `sudo systemctl start docker`), then try again."

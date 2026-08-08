from __future__ import annotations
from datetime import datetime

from dockerbrain.monitor.snapshot import MEM_WARNING_PCT, MEM_CRITICAL_PCT

def format_uptime(seconds: float) -> str:
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

def get_cpu_color(pct: float) -> str:
    if pct > 80:
        return "red"
    if pct > 50:
        return "yellow"
    return "green"

def get_mem_color(pct: float) -> str:
    if pct > MEM_CRITICAL_PCT:
        return "red"
    if pct > MEM_WARNING_PCT:
        return "yellow"
    return "cyan"

STATUS_ICON = {
    "running": "* ",
    "exited": "* ",
    "paused": "* ",
    "created": "- ",
    "dead": "x ",
}

STATUS_STYLE = {
    "running": "bold green",
    "exited": "bold #FF0000",
    "paused": "bold #ff8c00",
    "created": "cyan",
    "dead": "bold red",
}

def parse_and_format_logs(logs: str) -> str:
    """Clean and parse Docker timestamps from raw logs."""
    clean_logs = []
    for line in logs.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2 and "T" in parts[0] and parts[0].endswith("Z"):
            try:
                t_str = parts[0].replace("Z", "+00:00")
                if "." in t_str:
                    left, right = t_str.split(".", 1)
                    t_str = f"{left}.{right.split('+')[0][:6]}+00:00"

                dt = datetime.fromisoformat(t_str)
                time_part = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                time_part = parts[0][:10] + " " + parts[0].split("T")[1][:8]

            clean_logs.append(f"[{time_part}] {parts[1]}")
        else:
            clean_logs.append(line)
    return "\n".join(clean_logs)

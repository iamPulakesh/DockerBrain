from __future__ import annotations

from rich.align import Align
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from core.monitor.snapshot import (
    ContainerSnapshot,
    MEM_WARNING_PCT,
    MEM_CRITICAL_PCT,
)
from core.utils import format_bytes

_BLOCKS = " ▏▎▍▌▋▊▉█"


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


def _make_bar(value: float, max_value: float, width: int, color: str) -> Text:
    """Build a Unicode bar with sub-character precision.

    Uses eighth-block characters (▏▎▍▌▋▊▉█) so a 30-char bar
    effectively has 240 discrete steps of resolution.
    """
    if max_value <= 0:
        return Text("░" * width, style="dim")

    ratio = min(value / max_value, 1.0)
    total_eighths = int(ratio * width * 8)
    full = total_eighths // 8
    frac = total_eighths % 8
    empty = width - full - (1 if frac else 0)

    bar = Text()
    bar.append("█" * full, style=color)
    if frac:
        bar.append(_BLOCKS[frac], style=color)
    bar.append("░" * empty, style="dim")
    return bar


def _cpu_color(pct: float) -> str:
    """Return a Rich style for a CPU percentage."""
    if pct > 80:
        return "bold red"
    if pct > 50:
        return "yellow"
    return "green"


def _mem_color(pct: float) -> str:
    """Return a Rich style for a memory percentage."""
    if pct > MEM_CRITICAL_PCT:
        return "bold red"
    if pct > MEM_WARNING_PCT:
        return "yellow"
    return "cyan"


def build_monitor_layout(snapshots: list[ContainerSnapshot]) -> Layout:
    """Build a full-screen Rich Layout with bar graphs and panels."""
    n = max(len(snapshots), 1)
    BAR_WIDTH = 30

    header_text = Text()
    header_text.append("DockerBrain", style="bold cyan")
    header_text.append("  Monitor", style="dim")

    header = Panel(
        Align.center(header_text),
        border_style="bright_blue",
        style="on #1a1a2e",
    )

    running = sum(1 for s in snapshots if s.status == "running")
    idle = sum(1 for s in snapshots if s.is_idle)
    healthy = sum(1 for s in snapshots if s.health_label == "HEALTHY")
    warning = sum(1 for s in snapshots if s.health_label == "WARNING")
    critical = sum(1 for s in snapshots if s.health_label == "CRITICAL")

    total_cpu = sum(s.cpu_percent for s in snapshots)
    total_mem = sum(s.mem_usage_mb for s in snapshots)
    total_mem_limit = max((s.mem_limit_mb for s in snapshots), default=1)
    avg_mem_pct = (total_mem / total_mem_limit) * 100 if snapshots else 0
    total_cache = sum(s.mem_cache_mb for s in snapshots)

    stats = Text()
    stats.append("  Containers ", style="bold")
    stats.append(f"{len(snapshots)}", style="bold cyan")
    stats.append("  Running ", style="bold")
    stats.append(f"{running}", style="bold green")
    stats.append("  Idle ", style="bold")
    stats.append(f"{idle}", style="bold red" if idle else "dim")
    stats.append("  Healthy ", style="bold")
    stats.append(f"{healthy}", style="bold green")
    stats.append("  Warn ", style="bold")
    stats.append(f"{warning}", style="bold yellow" if warning else "dim")
    stats.append("  Crit ", style="bold")
    stats.append(f"{critical}\n", style="bold red" if critical else "dim")
    stats.append("  CPU ", style="bold")
    stats.append(f"{total_cpu:.1f}%", style=_cpu_color(total_cpu))
    stats.append("  Mem ", style="bold")
    stats.append(f"{total_mem:.0f}/{total_mem_limit:.0f} MB", style=_mem_color(avg_mem_pct))
    stats.append("  Cache ", style="bold")
    stats.append(f"{total_cache:.0f} MB", style="dim")

    overview_panel = Panel(
        stats,
        title="[bold cyan]System Overview[/]",
        border_style="cyan",
        padding=(0, 1),
    )

    table = Table(expand=True, border_style="dim", show_lines=False, pad_edge=False)
    table.add_column("Container", style="bold cyan", no_wrap=True)
    table.add_column("Image", style="dim", no_wrap=True, max_width=28)
    table.add_column("Status", justify="center")
    table.add_column("Uptime", justify="right")
    table.add_column("Health", justify="center")

    for s in snapshots:
        dot_style = "green" if s.status == "running" else "red"
        status_text = Text()
        status_text.append("● ", style=dot_style)
        status_text.append(s.status)

        table.add_row(
            s.name,
            s.image_tag,
            status_text,
            _format_uptime(s.uptime_seconds),
            Text(s.health_label, style=f"bold {s.health_style}"),
        )

    if not snapshots:
        table.add_row(
            Text("No running containers", style="yellow"),
            "", "", "", "",
        )

    table_panel = Panel(
        table,
        title="[bold cyan]Containers[/]",
        border_style="cyan",
        padding=(0, 1),
    )

    cpu_content = Text()
    for i, s in enumerate(snapshots):
        color = _cpu_color(s.cpu_percent)
        label = s.name if len(s.name) <= 14 else s.name[:11] + "…"
        cpu_content.append(f" {label:<14} ", style="cyan")
        cpu_content.append_text(_make_bar(s.cpu_percent, 100, BAR_WIDTH, color))
        cpu_content.append(f" {s.cpu_percent:>5.1f}%", style=f"bold {color}")
        if s.is_idle:
            cpu_content.append(" idle", style="bold red")
        if i < len(snapshots) - 1:
            cpu_content.append("\n")

    if not snapshots:
        cpu_content.append("  Waiting for containers…", style="dim italic")

    cpu_panel = Panel(
        cpu_content,
        title="[bold green]CPU Usage[/]",
        border_style="green",
        padding=(0, 1),
    )

    mem_content = Text()
    for i, s in enumerate(snapshots):
        color = _mem_color(s.mem_percent)
        label = s.name if len(s.name) <= 14 else s.name[:11] + "…"
        mem_content.append(f" {label:<14} ", style="cyan")
        mem_content.append_text(_make_bar(s.mem_percent, 100, BAR_WIDTH, color))
        mem_content.append(
            f" {s.mem_usage_mb:>6.1f}/{s.mem_limit_mb:>.0f}MB",
            style=color,
        )
        mem_content.append(f" {s.mem_percent:.0f}%", style=f"bold {color}")
        if i < len(snapshots) - 1:
            mem_content.append("\n")

    if not snapshots:
        mem_content.append("  Waiting for containers…", style="dim italic")

    mem_panel = Panel(
        mem_content,
        title="[bold blue]Memory Usage[/]",
        border_style="blue",
        padding=(0, 1),
    )

    net_table = Table(expand=True, show_header=True, show_lines=False, border_style="dim", pad_edge=False)
    net_table.add_column("Container", style="cyan", no_wrap=True)
    net_table.add_column("↓ Recv", justify="right", style="green")
    net_table.add_column("↑ Sent", justify="right", style="yellow")
    net_table.add_column("Rx Pkts", justify="right", style="blue")
    net_table.add_column("Tx Pkts", justify="right", style="blue")
    net_table.add_column("Err", justify="right")
    net_table.add_column("Drop", justify="right")

    total_rx = total_tx = 0
    total_rx_pkts = total_tx_pkts = 0
    total_errs = total_drops = 0
    for s in snapshots:
        total_rx += s.net_rx_bytes
        total_tx += s.net_tx_bytes
        total_rx_pkts += s.net_rx_packets
        total_tx_pkts += s.net_tx_packets
        errs = s.net_rx_errors + s.net_tx_errors
        drops = s.net_rx_dropped + s.net_tx_dropped
        total_errs += errs
        total_drops += drops

        err_style = "bold red" if errs > 0 else "dim"
        drop_style = "bold red" if drops > 0 else "dim"

        net_table.add_row(
            s.name,
            format_bytes(s.net_rx_bytes),
            format_bytes(s.net_tx_bytes),
            f"{s.net_rx_packets:,}",
            f"{s.net_tx_packets:,}",
            Text(str(errs), style=err_style),
            Text(str(drops), style=drop_style),
        )


    if not snapshots:
        net_table.add_row(
            Text("Waiting for containers…", style="dim italic"),
            "", "", "", "", "", "",
        )

    net_panel = Panel(
        net_table,
        title="[bold magenta]Network I/O[/]",
        border_style="magenta",
        padding=(0, 1),
    )

    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="overview", size=4),
        Layout(name="table", ratio=2),
        Layout(name="bars_row", ratio=1),
        Layout(name="network", ratio=2),
    )

    layout["header"].update(header)
    layout["overview"].update(overview_panel)
    layout["table"].update(table_panel)
    layout["bars_row"].split_row(
        Layout(name="cpu", ratio=1),
        Layout(name="mem", ratio=1),
    )
    layout["cpu"].update(cpu_panel)
    layout["mem"].update(mem_panel)
    layout["network"].update(net_panel)

    return layout

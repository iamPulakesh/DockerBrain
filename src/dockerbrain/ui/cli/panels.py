"""Shared Rich panel helpers — error panels, status panels, header panels."""

from __future__ import annotations

from rich.align import Align
from rich.panel import Panel
from rich.text import Text

from dockerbrain.ui.cli.console import get_console


def print_error_panel(message: str, title: str = "Error", detail: str | None = None) -> None:
    """Print a red error panel."""
    console = get_console()
    body = f"[red bold]{message}[/]"
    if detail:
        body += f"\n\n[dim]{detail}[/]"
    console.print(
        Panel(
            body,
            title=f"[bold red]{title}[/]",
            border_style="red",
            expand=False,
        )
    )


def print_header_panel(title: str, subtitle: str = "") -> None:
    """Print a styled header panel."""
    console = get_console()
    header_text = Text()
    header_text.append("DockerBrain", style="bold cyan")
    if subtitle:
        header_text.append(f"  {subtitle}", style="dim")
    console.print(
        Panel(
            Align.center(header_text),
            border_style="bright_blue",
            style="on #1a1a2e",
        )
    )


def print_parse_error(raw: str) -> None:
    """Print a parse-error panel for unparseable AI responses."""
    print_error_panel(
        "Could not parse AI response.",
        title="Parse Error",
        detail=raw[:500],
    )


def print_missing_key_error() -> None:
    """Print a brief error panel for missing API key."""
    console = get_console()
    console.print(
        Panel(
            f"Add your key to [cyan]~/.dockerbrain/.dockerbrainrc[/]:\n"
            f'  [cyan]api_key = "your_key_here"[/]',
            title="[bold red]Missing API Key[/]",
            border_style="red",
            expand=False,
        )
    )

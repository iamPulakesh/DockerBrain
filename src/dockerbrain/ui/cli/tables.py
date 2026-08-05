"""Shared Rich table renderers — unifies the two duplicate table functions."""

from __future__ import annotations

import json
from typing import Literal

from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from dockerbrain.ui.cli.console import get_console


def render_findings_table(
    findings: list[dict],
    mode: Literal["container", "dockerfile", "dockerfile_detailed"],
) -> None:
    """Render AI findings as a compact Rich table.

    Replaces both ``ai_advisor._render_compact_table`` and
    ``fixer/dockerfile._display_ai_issues_table``.
    """
    console = get_console()

    if not findings:
        console.print("[green bold]✓ No issues found![/]")
        return

    if mode == "dockerfile_detailed":
        _render_dockerfile_detailed(findings, console)
    elif mode == "dockerfile":
        _render_simple(findings, console, first_col_key="line", first_col_label="Line")
    else:
        _render_simple(findings, console, first_col_key="container", first_col_label="Container")


def _render_simple(
    findings: list[dict],
    console,
    *,
    first_col_key: str,
    first_col_label: str,
) -> None:
    """Compact 3-column table (container/line, issue, recommendation)."""
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue",
        show_lines=True,
        expand=True,
    )

    is_line = first_col_key == "line"
    if is_line:
        table.add_column(first_col_label, style="bold", justify="right", width=6)
    else:
        table.add_column(first_col_label, style="bold", no_wrap=True, min_width=16)
    table.add_column("Issue", style="yellow")
    table.add_column("Recommendation", style="green")

    for f in findings:
        col_val = str(f.get(first_col_key, "—")) if is_line else str(f.get(first_col_key, "?"))
        table.add_row(
            col_val,
            str(f.get("issue", "?")),
            str(f.get("recommendation", "?")),
        )

    console.print(table)
    console.print(f"\n[dim]{len(findings)} finding(s)[/]")


def _render_dockerfile_detailed(findings: list[dict], console) -> None:
    """Detailed Dockerfile issues table with severity sorting + rule column."""
    _SEV_STYLE = {"HIGH": "bold red", "MEDIUM": "bold yellow", "LOW": "bold green"}
    _SEV_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    sorted_issues = sorted(findings, key=lambda i: _SEV_RANK.get(i.get("severity", "LOW"), 9))

    table = Table(
        expand=True,
        border_style="dim",
        show_lines=True,
    )
    table.add_column("#", justify="right", style="dim", width=4)
    table.add_column("Line", justify="right", width=5)
    table.add_column("Rule", style="bold", no_wrap=True)
    table.add_column("Severity", justify="center", width=8)
    table.add_column("Message")

    for i, issue in enumerate(sorted_issues, 1):
        sev = issue.get("severity", "LOW")
        line_val = str(issue.get("line")) if issue.get("line") else "—"
        table.add_row(
            str(i),
            line_val,
            issue.get("rule", "unknown"),
            Text(sev, style=_SEV_STYLE.get(sev, "dim")),
            issue.get("message", ""),
        )

    console.print()
    console.print(table)
    console.print(f"\n[dim]{len(findings)} issue(s) detected.[/]\n")


def parse_findings_json(raw: str) -> list[dict] | None:
    """Parse raw AI response text into a list of finding dicts.

    Returns None if parsing fails (caller should handle the error display).
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:] if "\n" in text else text
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def format_bytes(b: int | float) -> str:
    """Human-readable byte string (e.g. 1.23 GiB)."""
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if abs(b) < 1024:
            return f"{b:.2f} {unit}"
        b /= 1024
    return f"{b:.2f} PiB"

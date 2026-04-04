from __future__ import annotations

import json
import subprocess

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

from core.llm import load_llm_config, generate
from core.optimizer import RuleBasedOptimizer

console = Console()

_BLOCKED_COMMANDS = {"rm", "rmi", "system prune", "volume rm", "network rm", "image rm"}


def _is_safe_command(command: str) -> bool:
    """Return True if the docker command is NOT destructive."""
    cmd_lower = command.strip().lower()
    if not cmd_lower.startswith("docker"):
        return False
    parts = cmd_lower.split()
    if len(parts) < 2:
        return False
    sub = parts[1]
    if sub in _BLOCKED_COMMANDS:
        return False
    if len(parts) >= 3:
        two_word = f"{parts[1]} {parts[2]}"
        if two_word in _BLOCKED_COMMANDS:
            return False
    return True


_CONTAINER_FIX_SYSTEM_INSTRUCTION = (
    "You are a Docker container optimization expert. Based on the metrics and issues "
    "provided, generate a JSON array of fix actions.\n\n"
    "CRITICAL: Your entire response MUST be a valid JSON array and nothing else. "
    "No markdown, no explanation, no code fences — just the raw JSON.\n\n"
    "Each element in the array must be an object with exactly these keys:\n"
    '  - "container": the container name\n'
    '  - "command": the exact docker CLI command to run (e.g. "docker update --memory 256m my_container")\n'
    '  - "reason": a one-line explanation of why this fix is needed\n\n'
    "Rules:\n"
    "- Only suggest commands that are safe and non-destructive.\n"
    "- Do NOT suggest `docker rm`, `docker rmi`, `docker system prune`, or any delete commands.\n"
    "- Allowed commands include: `docker update`, `docker restart`, `docker stop`, `docker pull`.\n"
    "- Do NOT suggest lowering memory limits just because current usage is low.\n"
    "- If no fixes are needed, return an empty array: []\n"
)


def fix_containers(container_name: str | None = None) -> None:
    """Analyze containers, get AI fix commands as JSON, confirm and execute each."""
    console.print("[dim]Running analysis...[/]\n")
    optimizer = RuleBasedOptimizer()
    suggestions = optimizer.analyze(container_name=container_name)

    if not suggestions:
        console.print("[green]No issues found — all containers look healthy![/]")
        return

    console.print(
        f"[bold]Found {len(suggestions)} issue(s). Preparing fixes...[/]\n"
    )

    issues_text = "\n".join(
        f"- [{s.severity.value}] {s.container_name} ({s.rule_name}): {s.message}"
        for s in suggestions
    )

    prompt = (
        "## Container Issues to Fix\n\n"
        f"{issues_text}\n\n"
        "Generate the JSON array of fix actions."
    )

    config = load_llm_config()

    with console.status("[bold green]Please wait...[/]", spinner="dots"):
        raw_text = generate(
            prompt=prompt,
            system_instruction=_CONTAINER_FIX_SYSTEM_INSTRUCTION,
            config=config,
        )

    try:
        actions = json.loads(raw_text)
    except json.JSONDecodeError:
        console.print(
            Panel(
                "[red bold]Could not parse response as JSON.[/]\n\n"
                f"[dim]Raw response:[/]\n{raw_text}",
                title="[bold red]Parse Error[/]",
                border_style="red",
                expand=False,
            )
        )
        return

    if not actions:
        console.print("[green]No fixes needed.[/]")
        return

    console.print(
        Panel(
            f"[bold]{len(actions)} fix action(s) proposed:[/]",
            border_style="cyan",
            expand=False,
        )
    )

    executed = 0
    skipped = 0
    blocked = 0

    for i, action in enumerate(actions, 1):
        container = action.get("container", "?")
        command = action.get("command", "")
        reason = action.get("reason", "")

        console.print(f"\n[bold cyan]Fix {i}/{len(actions)}[/]")
        console.print(f"  Container: [cyan]{container}[/]")
        console.print(f"  Reason:    [dim]{reason}[/]")
        console.print(f"  Command:   [bold]{command}[/]")

        if not _is_safe_command(command):
            console.print(
                f"  [red bold]BLOCKED[/] — This command is destructive and cannot be auto-executed."
            )
            blocked += 1
            continue

        if Confirm.ask("  Execute?", default=False):
            try:
                result = subprocess.run(
                    command.split(),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    out = result.stdout.strip()
                    console.print(f"  [green bold]Done[/]{': ' + out if out else ''}")
                    executed += 1
                else:
                    console.print(f"  [red bold]Failed[/]: {result.stderr.strip()}")
            except Exception as exc:
                console.print(f"  [red bold]Error[/]: {exc}")
        else:
            console.print("  [dim]Skipped.[/]")
            skipped += 1

    console.print()
    summary_parts = []
    if executed:
        summary_parts.append(f"[green]{executed} applied[/]")
    if skipped:
        summary_parts.append(f"[yellow]{skipped} skipped[/]")
    if blocked:
        summary_parts.append(f"[red]{blocked} blocked[/]")

    console.print(
        Panel(
            " | ".join(summary_parts),
            title="[bold]Fix Summary[/]",
            border_style="cyan",
            expand=False,
        )
    )

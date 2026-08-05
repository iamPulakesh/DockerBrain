"""Dockerfile fixer — AI-driven Dockerfile detection and rewriting."""

from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

from rich.columns import Columns
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax

from dockerbrain.config.settings import LLMConfig, load_llm_config
from dockerbrain.llm import get_provider
from dockerbrain.ui.cli.console import get_console
from dockerbrain.ui.cli.tables import render_findings_table

_DEFAULT_DOCKERIGNORE = """\
.git
.gitignore
.dockerignore
node_modules
__pycache__
*.pyc
.env
.venv
*.md
.DS_Store
Thumbs.db
"""

_DOCKERFILE_DETECT_SYSTEM = (
    "You are a Dockerfile security and optimization expert. Analyze the Dockerfile and return ONLY a "
    "valid JSON array of issues. No markdown, no explanation, no code fences — just the raw JSON.\n\n"
    "Each issue object must have exactly these keys:\n"
    '  - "line": integer (1-indexed) or null if not line-specific\n'
    '  - "rule": short snake_case rule name (e.g. "hardcoded-secret", "cache-busting-copy")\n'
    '  - "severity": one of "HIGH", "MEDIUM", or "LOW"\n'
    '  - "message": a one-sentence explanation of the issue\n\n'
    "Detect all of these if present:\n"
    "  - Hardcoded secrets or tokens in ENV instructions\n"
    "  - Large or bloated base images (ubuntu, debian, centos — suggest slim/alpine)\n"
    "  - apt-get/apk install without --no-install-recommends\n"
    "  - Multiple separate RUN apt-get/apk commands (should be chained with &&)\n"
    "  - COPY . . before dependency install step (cache-busting)\n"
    "  - Missing non-root USER directive\n"
    "  - Shell form CMD/ENTRYPOINT instead of exec form (JSON array)\n"
    "  - No HEALTHCHECK defined\n"
    "  - Packages installed but cache not cleaned (no rm -rf /var/lib/apt/lists/*)\n"
    "  - Any other security or optimization issues\n\n"
    "If no issues are found, return an empty JSON array: []"
)

_DOCKERFILE_REWRITE_SYSTEM = (
    "You are a Dockerfile optimization expert. You will be given a Dockerfile and a list of detected issues. "
    "Rewrite the Dockerfile to fix ALL the issues. "
    "Return ONLY the improved Dockerfile content with brief comments explaining changes. "
    "IMPORTANT: NEVER place comments on the same line as code (no inline comments). "
    "Always put comments on a separate line ABOVE the instruction they describe. "
    "Do NOT wrap in markdown code fences. Do NOT add any explanation outside the Dockerfile."
)


def _ai_detect_dockerfile_issues(content: str, config: LLMConfig) -> list[dict]:
    """Call LLM to detect issues in a Dockerfile. Returns a list of issue dicts."""
    console = get_console()
    provider = get_provider(config)

    with console.status("[bold green]Analyzing Dockerfile...[/]", spinner="dots"):
        raw = provider.generate(
            prompt=f"## Dockerfile to Analyze\n\n```dockerfile\n{content}\n```",
            system_instruction=_DOCKERFILE_DETECT_SYSTEM,
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        console.print(f"[red]Could not parse AI detection response as JSON.[/]\n[dim]{raw}[/]")
        return []


def _ai_rewrite_dockerfile(content: str, issues: list[dict], config: LLMConfig) -> str:
    """Call LLM to rewrite the Dockerfile fixing all detected issues."""
    console = get_console()
    provider = get_provider(config)

    issues_text = "\n".join(
        f"- [{i.get('severity')}] Line {i.get('line') or '?'} ({i.get('rule')}): {i.get('message')}"
        for i in issues
    )
    prompt = (
        f"## Dockerfile\n\n```dockerfile\n{content}\n```\n\n"
        f"## Detected Issues\n\n{issues_text}\n\n"
        "Please rewrite the Dockerfile to fix all the above issues."
    )

    with console.status("[bold green]Generating fix...[/]", spinner="dots"):
        return provider.generate(
            prompt=prompt,
            system_instruction=_DOCKERFILE_REWRITE_SYSTEM,
        )


def _show_diff(original: str, optimized: str, original_path: Path) -> None:
    """Display a side-by-side Rich diff between original and optimized Dockerfile."""
    console = get_console()

    diff = list(difflib.unified_diff(
        original.splitlines(),
        optimized.splitlines(),
        fromfile="Original",
        tofile="Optimized",
        lineterm="",
    ))
    if not diff:
        console.print("[green]The Dockerfile is already optimal.[/]")
        return

    left = Panel(
        Syntax(original, "dockerfile", theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold red]Original[/]",
        border_style="red",
        expand=True,
    )
    right = Panel(
        Syntax(optimized, "dockerfile", theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold green]Optimized[/]",
        border_style="green",
        expand=True,
    )
    console.print()
    console.print(Columns([left, right], equal=True, expand=True))


def fix_dockerfile(dockerfile_path: str) -> None:
    """AI-powered detect + fix: detects issues, displays them, then rewrites the Dockerfile."""
    console = get_console()
    original_path = Path(dockerfile_path)
    content = original_path.read_text(encoding="utf-8")
    filename = original_path.name

    config = load_llm_config()
    issues = _ai_detect_dockerfile_issues(content, config)

    if not issues:
        console.print("[green bold]No issues detected![/]")
        return

    render_findings_table(issues, mode="dockerfile_detailed")

    dockerignore_issues = [i for i in issues if i.get("rule") == "missing-dockerignore"]
    dockerfile_issues = [i for i in issues if i.get("rule") != "missing-dockerignore"]

    if dockerignore_issues:
        dockerignore_path = original_path.parent / ".dockerignore"
        if not dockerignore_path.exists():
            if Confirm.ask(
                f"[bold yellow]Create [cyan]{dockerignore_path}[/cyan]?[/] (fixes missing-dockerignore)",
                default=True,
            ):
                dockerignore_path.write_text(_DEFAULT_DOCKERIGNORE, encoding="utf-8")
                console.print(f"[green bold]Created:[/] [cyan]{dockerignore_path}[/]\n")
            else:
                console.print("[dim]Skipped .dockerignore creation.[/]\n")

    if not dockerfile_issues:
        console.print("[green]All issues resolved![/]")
        return

    optimized = _ai_rewrite_dockerfile(content, dockerfile_issues, config)
    _show_diff(content, optimized, original_path)

    console.print()
    if not Confirm.ask(
        "[bold yellow]Apply this fix?[/] (overwrites the Dockerfile, a .bak backup will be created)",
        default=False,
    ):
        console.print("[dim]Skipped. No changes made.[/]")
        return

    backup_path = original_path.with_suffix(original_path.suffix + ".bak")
    shutil.copy2(original_path, backup_path)
    console.print(f"[dim]Backup saved to: {backup_path}[/]")
    original_path.write_text(optimized, encoding="utf-8")
    console.print(f"[green bold]Dockerfile fixed![/] Written to: [cyan]{original_path}[/]")

    console.print("\n[dim]Re-checking for remaining issues...[/]")
    remaining = _ai_detect_dockerfile_issues(optimized, config)
    if not remaining:
        console.print("[green bold]All issues resolved![/]")
    else:
        console.print(f"[yellow]{len(remaining)} issue(s) still remain after fix:[/]")
        render_findings_table(remaining, mode="dockerfile_detailed")

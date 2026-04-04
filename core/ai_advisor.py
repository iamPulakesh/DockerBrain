from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import docker
from rich.align import Align
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from core.llm import load_llm_config, generate_stream
from core.optimizer import RuleBasedOptimizer
from core.storage import get_metrics_since, get_all_container_names, store_ai_suggestion


console = Console()

#  System instructions 
_CONTAINER_SYSTEM_INSTRUCTION = (
    "You are a Docker container optimization expert. Analyze the provided metrics and return "
    "ONLY a valid JSON array — no markdown, no explanation, no code fences.\n\n"
    "Each element must be an object with exactly these three keys:\n"
    '  - "container": the container name (string)\n'
    '  - "issue": a short one-line description of the problem (max 10 words)\n'
    '  - "recommendation": a short, actionable fix (max 15 words)\n\n'
    "Rules:\n"
    "- DO NOT suggest lowering memory limits just because usage is low — only flag if near/at the limit.\n"
    "- Only include real, actionable findings. If everything is healthy, return: []\n"
    "- Keep every field SHORT. No long paragraphs. No code blocks inside the JSON strings.\n"
    "- Return ONLY the raw JSON array. Nothing else."
)

_DOCKERFILE_SYSTEM_INSTRUCTION = (
    "You are a Dockerfile optimization expert. Analyze the provided Dockerfile and return "
    "ONLY a valid JSON array — no markdown, no explanation, no code fences.\n\n"
    "Each element must be an object with exactly these three keys:\n"
    '  - "line": the line number in the Dockerfile (integer), or null if general\n'
    '  - "issue": a short one-line description of the problem (max 10 words)\n'
    '  - "recommendation": a short, actionable fix (max 15 words)\n\n'
    "Detect issues like: large base images, hardcoded secrets, unchained RUN commands, "
    "missing non-root USER, no HEALTHCHECK, COPY . . before deps, missing .dockerignore, "
    "apt-get without --no-install-recommends, uncleaned apt cache, shell-form CMD.\n\n"
    "Keep every field SHORT. Return ONLY the raw JSON array."
)

def _render_compact_table(raw: str) -> None:
    """Parse JSON array from AI and render as a compact 3-column table."""
    text = raw.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:] if "\n" in text else text
    if text.endswith("```"):
        text = text[:-3].rstrip()

    try:
        findings = json.loads(text)
    except json.JSONDecodeError:
        console.print(
            Panel(
                f"[red]Could not parse AI response.[/]\n\n[dim]{raw[:500]}[/]",
                title="[bold red]Parse Error[/]",
                border_style="red",
                expand=False,
            )
        )
        return

    if not findings:
        console.print("[green bold]✓ No issues found![/]")
        return

    # Auto-detect mode: container data has "container" key, Dockerfile has "line"
    is_dockerfile = "line" in findings[0] and "container" not in findings[0]

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue",
        show_lines=True,
        expand=True,
    )

    if is_dockerfile:
        table.add_column("Line", style="bold", justify="right", width=6)
    else:
        table.add_column("Container", style="bold", no_wrap=True, min_width=16)
    table.add_column("Issue", style="yellow")
    table.add_column("Recommendation", style="green")

    for f in findings:
        first_col = str(f.get("line", "—")) if is_dockerfile else str(f.get("container", "?"))
        table.add_row(
            first_col,
            str(f.get("issue", "?")),
            str(f.get("recommendation", "?")),
        )

    console.print(table)
    console.print(f"\n[dim]{len(findings)} finding(s)[/]")


class AIAdvisor:
    """Multi-provider AI advisor for container & Dockerfile analysis."""

    def __init__(self) -> None:
        self._config = load_llm_config()

    def _build_container_prompt(
        self,
        container_name: str | None,
        window_minutes: int,
        no_rules: bool = False,
    ) -> str:
        """Build a structured prompt from SQLite history + rule-based suggestions."""

        since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
        rows = get_metrics_since(since, container=container_name)

        if container_name:
            containers = [container_name]
        elif rows:
            containers = sorted({r["container"] for r in rows})
        else:
            containers = get_all_container_names()

        rule_suggestions: list[str] = []
        if not no_rules:
            try:
                optimizer = RuleBasedOptimizer()
                suggestions = optimizer.analyze(container_name=container_name)
                for s in suggestions:
                    rule_suggestions.append(
                        f"  [{s.severity.value}] {s.container_name}: {s.message}"
                    )
            except Exception:
                rule_suggestions.append("  (Could not collect suggestions)")

        container_sections: list[str] = []

        for cname in containers:
            c_rows = [r for r in rows if r["container"] == cname]

            if c_rows:
                cpus = [r["cpu_percent"] for r in c_rows if r["cpu_percent"] is not None]
                mems = [r["mem_usage_mb"] for r in c_rows if r["mem_usage_mb"] is not None]
                idle_counts = [r["idle_polls"] for r in c_rows if r.get("idle_polls")]

                avg_cpu = sum(cpus) / len(cpus) if cpus else 0.0
                peak_mem = max(mems) if mems else 0.0
                mem_limit = c_rows[-1].get("mem_limit_mb", 0) or 0
                max_idle = max(idle_counts) if idle_counts else 0

                section = (
                    f"### {cname}\n"
                    f"- Avg CPU: {avg_cpu:.2f}%\n"
                    f"- Peak Memory: {peak_mem:.1f} MB / {mem_limit:.1f} MB limit\n"
                    f"- Data points: {len(c_rows)} (last {window_minutes} min)\n"
                    f"- Max consecutive idle polls: {max_idle}\n"
                )
            else:
                section = (
                    f"### {cname}\n"
                    f"- No historical metrics available (run `dockerbrain monitor` first)\n"
                )

            try:
                client = docker.from_env()
                ctr = client.containers.get(cname)
                ctr.reload()
                restart_count = ctr.attrs.get("RestartCount", 0)
                image_tag = ctr.image.tags[0] if ctr.image.tags else ctr.image.short_id
                section += (
                    f"- Status: {ctr.status}\n"
                    f"- Restart count: {restart_count}\n"
                    f"- Image: {image_tag}\n"
                )
            except Exception:
                section += "- (Container not currently running)\n"

            container_sections.append(section)

        prompt = (
            "## Container Metrics Report\n\n"
            + "\n".join(container_sections)
            + "\n## Current Rule-Based Findings\n\n"
            + ("\n".join(rule_suggestions) if rule_suggestions else "  None")
            + "\n\nPlease analyze the above and provide your optimization recommendations."
        )
        return prompt

    @staticmethod
    def _build_dockerfile_prompt(dockerfile_path: str) -> str:
        """Read a Dockerfile and build a prompt for Gemini."""
        path = Path(dockerfile_path)
        if not path.is_file():
            console.print(f"[red bold]Error:[/] File not found: {path}")
            raise SystemExit(1)

        content = path.read_text(encoding="utf-8")

        dockerignore_exists = (path.parent / ".dockerignore").exists()
        dockerignore_note = (
            "NOTE: A .dockerignore file already exists in this project — do NOT flag it as missing."
            if dockerignore_exists
            else "NOTE: No .dockerignore file was found in this project."
        )

        return (
            "## Dockerfile to Optimize\n\n"
            f"```dockerfile\n{content}\n```\n\n"
            f"{dockerignore_note}\n\n"
            "Please analyze this Dockerfile and suggest concrete optimizations covering:\n"
            "1. Multi-stage builds to reduce image size\n"
            "2. Optimal layer ordering for cache efficiency\n"
            "3. Removal of unnecessary packages\n"
            "4. Using smaller base images (Alpine, distroless, slim)\n"
            "5. Security best practices (non-root user, minimal permissions)\n"
            "6. Any other improvements\n\n"
            "For each suggestion, show a BEFORE → AFTER code diff."
        )

    def suggest_for_containers(
        self,
        container_name: str | None = None,
        window_minutes: int = 30,
        no_rules: bool = False,
    ) -> None:
        """Query Gemini with container metrics and render as panels."""
        prompt = self._build_container_prompt(container_name, window_minutes, no_rules=no_rules)

        self._stream(
            prompt,
            system_instruction=_CONTAINER_SYSTEM_INSTRUCTION,
        )

    def suggest_for_dockerfile(self, dockerfile_path: str) -> None:
        """Query Gemini with a Dockerfile and render as panels."""
        prompt = self._build_dockerfile_prompt(dockerfile_path)

        self._stream(
            prompt,
            system_instruction=_DOCKERFILE_SYSTEM_INSTRUCTION,
        )

    def _stream(self, prompt: str, system_instruction: str) -> None:
        """Collect AI response with a spinner, then render as styled panels."""
        console.print()

        header_text = Text()
        header_text.append("DockerBrain", style="bold cyan")
        header_text.append("  Suggest", style="dim")
        console.print(
            Panel(
                Align.center(header_text),
                border_style="bright_blue",
                style="on #1a1a2e",
            )
        )
        console.print()

        max_retries = 2
        full_text = ""
        last_error: Exception | None = None
        success = False

        for attempt in range(max_retries + 1):
            try:
                spinner_msg = (
                    "Please wait…"
                    if attempt == 0
                    else f"Retrying ({attempt}/{max_retries})…"
                )

                full_text = ""
                with Live(
                    Spinner("dots", text=f"  {spinner_msg}", style="bold green"),
                    console=console,
                    refresh_per_second=10,
                ) as live:
                    for chunk in generate_stream(prompt, system_instruction, self._config):
                        full_text += chunk
                        live.update(
                            Spinner(
                                "dots",
                                text="  Issues Found...",
                                style="bold green",
                            )
                        )

                success = True
                break
            except Exception as exc:
                last_error = exc
                if attempt < max_retries:
                    wait = 2 ** (attempt + 1)
                    console.print(
                        f"[yellow] Request failed: {exc}. "
                        f"Retrying in {wait}s…[/]"
                    )
                    time.sleep(wait)

        if not success:
            console.print(
                Panel(
                    f"[red bold]LLM API call failed after {max_retries + 1} attempts.[/]\n\n"
                    f"[dim]{last_error}[/]\n\n"
                    "Check your network connection and API key, then try again.",
                    title="[bold red]Request Failed[/]",
                    border_style="red",
                    expand=False,
                )
            )
            return

        console.print()
        _render_compact_table(full_text)

        summary = full_text[:300].replace("\n", " ").strip()
        if len(full_text) > 300:
            summary += "…"
        store_ai_suggestion(summary=summary, full_response=full_text)

def run_ai_suggest(
    container_name: str | None = None,
    window_minutes: int = 30,
    dockerfile_path: str | None = None,
    no_rules: bool = False,
) -> None:
    """Create an AIAdvisor and run the appropriate suggestion mode."""
    advisor = AIAdvisor()

    if dockerfile_path:
        advisor.suggest_for_dockerfile(dockerfile_path)
    else:
        advisor.suggest_for_containers(
            container_name=container_name,
            window_minutes=window_minutes,
            no_rules=no_rules,
        )


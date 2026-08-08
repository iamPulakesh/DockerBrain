"""AIAdvisor service — orchestration only, calls llm/ + ui/."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import docker
from rich.live import Live
from rich.spinner import Spinner

from dockerbrain.advisor.prompts import (
    CONTAINER_SYSTEM_INSTRUCTION,
    DOCKERFILE_SYSTEM_INSTRUCTION,
)
from dockerbrain.config.settings import load_llm_config
from dockerbrain.llm import get_provider
from dockerbrain.storage.metrics_repository import MetricsRepository
from dockerbrain.storage.suggestions_repository import SuggestionsRepository
from dockerbrain.ui.cli.console import get_console
from dockerbrain.ui.cli.panels import print_error_panel, print_header_panel, print_parse_error
from dockerbrain.ui.cli.tables import render_findings_table, parse_findings_json


class AIAdvisor:
    """Multi-provider AI advisor for container & Dockerfile analysis."""

    def __init__(self) -> None:
        self._config = load_llm_config()
        self._provider = get_provider(self._config)
        self._metrics_repo = MetricsRepository()
        self._suggestions_repo = SuggestionsRepository()

    def _build_container_prompt(
        self,
        container_name: str | None,
        window_minutes: int,
    ) -> str:
        """Build a structured prompt from SQLite history."""

        since = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
        rows = self._metrics_repo.get_since(since, container=container_name)

        if container_name:
            containers = [container_name]
        elif rows:
            containers = sorted({r["container"] for r in rows})
        else:
            containers = self._metrics_repo.get_all_container_names()

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
            + "\n\nPlease analyze the above and provide your optimization recommendations."
        )
        return prompt

    @staticmethod
    def _build_dockerfile_prompt(dockerfile_path: str) -> str:
        """Read a Dockerfile and build a prompt for the LLM."""
        console = get_console()
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
            "For each suggestion, show a BEFORE -> AFTER code diff."
        )

    def suggest_for_containers(
        self,
        container_name: str | None = None,
        window_minutes: int = 30,
    ) -> None:
        """Query LLM with container metrics and render as panels."""
        prompt = self._build_container_prompt(container_name, window_minutes)

        self._stream(
            prompt,
            system_instruction=CONTAINER_SYSTEM_INSTRUCTION,
        )

    def suggest_for_dockerfile(self, dockerfile_path: str) -> None:
        """Query LLM with a Dockerfile and render as panels."""
        prompt = self._build_dockerfile_prompt(dockerfile_path)

        self._stream(
            prompt,
            system_instruction=DOCKERFILE_SYSTEM_INSTRUCTION,
        )

    def _stream(self, prompt: str, system_instruction: str) -> None:
        """Collect AI response with a spinner, then render as styled panels."""
        console = get_console()
        console.print()
        print_header_panel("DockerBrain", "Suggest")
        console.print()

        max_retries = 2
        full_text = ""
        last_error: Exception | None = None
        success = False

        for attempt in range(max_retries + 1):
            try:
                spinner_msg = (
                    "Please wait..."
                    if attempt == 0
                    else f"Retrying ({attempt}/{max_retries})..."
                )

                full_text = ""
                with Live(
                    Spinner("dots", text=f"  {spinner_msg}", style="bold green"),
                    console=console,
                    refresh_per_second=10,
                ) as live:
                    for chunk in self._provider.stream(prompt, system_instruction):
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
                        f"Retrying in {wait}s...[/]"
                    )
                    time.sleep(wait)

        if not success:
            print_error_panel(
                f"LLM API call failed after {max_retries + 1} attempts.",
                title="Request Failed",
                detail=f"{last_error}\n\nCheck your network connection and API key, then try again.",
            )
            return

        console.print()
        findings = parse_findings_json(full_text)
        if findings is None:
            print_parse_error(full_text)
        else:
            # Auto-detect mode
            is_dockerfile = findings and "line" in findings[0] and "container" not in findings[0]
            mode = "dockerfile" if is_dockerfile else "container"
            render_findings_table(findings, mode=mode)

        summary = full_text[:300].replace("\n", " ").strip()
        if len(full_text) > 300:
            summary += "..."
        self._suggestions_repo.store(summary=summary, full_response=full_text)


def run_ai_suggest(
    container_name: str | None = None,
    window_minutes: int = 30,
    dockerfile_path: str | None = None,
) -> None:
    """Create an AIAdvisor and run the appropriate suggestion mode."""
    from dockerbrain.ui.cli.console import get_console
    console = get_console()
    
    try:
        advisor = AIAdvisor()
    except ValueError as e:
        console.print(f"[bold red]Config Error:[/] {e}")
        raise SystemExit(1)

    if dockerfile_path:
        advisor.suggest_for_dockerfile(dockerfile_path)
    else:
        advisor.suggest_for_containers(
            container_name=container_name,
            window_minutes=window_minutes,
        )

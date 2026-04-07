"""Log analyzer — scan container logs for issues using the configured LLM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import docker
from docker.errors import NotFound

from core.llm import load_llm_config, generate_stream, LLMConfig


_LOG_ANALYSIS_SYSTEM_INSTRUCTION = (
    "You are a Docker container debugging expert. "
    "The user will provide the last 100 lines of logs from a container that has "
    "stopped, exited, or died unexpectedly.\n\n"
    "Your job is to:\n"
    "1. Identify the root cause of the failure from the logs.\n"
    "2. Provide a clear, concise explanation of what went wrong.\n"
    "3. Suggest a specific fix or next step.\n\n"
    "Format your response as:\n"
    "## Root Cause\n"
    "<one-paragraph explanation>\n\n"
    "## Suggested Fix\n"
    "<actionable steps>\n\n"
    "Keep it SHORT and ACTIONABLE. No code fences unless showing a command."
)


@dataclass
class ScanResult:
    """Result of scanning a container for issues."""

    container_name: str
    status: str
    healthy: bool
    message: str


def check_container_status(client: docker.DockerClient, name: str) -> ScanResult:
    """Check if the container is running or in a failed state."""
    try:
        ctr = client.containers.get(name)
        status = ctr.status

        if status == "running":
            return ScanResult(
                container_name=name,
                status=status,
                healthy=True,
                message="Container is running — no issues detected.",
            )

        if status == "paused":
            return ScanResult(
                container_name=name,
                status=status,
                healthy=True,
                message="Container is paused.",
            )

        return ScanResult(
            container_name=name,
            status=status,
            healthy=False,
            message=f"Container is {status}. Analyzing logs,",
        )
    except NotFound:
        return ScanResult(
            container_name=name,
            status="not_found",
            healthy=False,
            message="Container not found.",
        )


def analyze_logs_stream(
    client: docker.DockerClient,
    name: str,
    config: LLMConfig | None = None,
) -> Iterator[str]:
    """Stream LLM analysis of the last 100 log lines from a failed container."""
    if config is None:
        config = load_llm_config()

    try:
        ctr = client.containers.get(name)
        raw_logs = ctr.logs(tail=100, timestamps=True).decode("utf-8", errors="replace")
    except NotFound:
        yield "Container not found — cannot retrieve logs."
        return
    except Exception as e:
        yield f"Error fetching logs: {e}"
        return

    if not raw_logs.strip():
        yield "No logs available for analysis."
        return

    prompt = (
        f"Container: {name}\n"
        f"Status: {ctr.status}\n\n"
        f"--- Last 100 log lines ---\n{raw_logs}"
    )

    yield from generate_stream(prompt, _LOG_ANALYSIS_SYSTEM_INSTRUCTION, config)

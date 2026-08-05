"""Docker connection wrapper and OS-specific offline hint."""

from __future__ import annotations

import sys

import docker
from docker.errors import DockerException
from rich.panel import Panel

from dockerbrain.ui.cli.console import get_console


def get_docker_offline_hint() -> str:
    """Return an OS-specific hint for starting Docker."""
    if sys.platform == "win32":
        return "Make sure Docker Desktop is running, then try again."
    elif sys.platform == "darwin":
        return (
            "Make sure Docker Desktop (or OrbStack/Colima) is running, then try again."
        )
    else:
        return "Make sure the Docker daemon is running (e.g. `sudo systemctl start docker`), then try again."


def connect_docker() -> docker.DockerClient:
    """Return a Docker client, printing a styled error on failure."""
    try:
        return docker.from_env()
    except DockerException as exc:
        console = get_console()
        console.print(
            Panel(
                "[red bold]Could not connect to Docker daemon.[/]\n\n"
                f"{get_docker_offline_hint()}\n\n",
                title="[bold red]Docker Unavailable[/]",
                border_style="red",
                expand=False,
            )
        )
        raise SystemExit(3) from exc

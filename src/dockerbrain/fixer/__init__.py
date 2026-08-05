"""Fixer — auto-fix Docker issues."""

from dockerbrain.fixer.dockerfile_fixer import fix_dockerfile
from dockerbrain.fixer.container_fixer import fix_containers


def run_fix(
    dockerfile_path: str | None = None,
    container_name: str | None = None,
) -> None:
    """Route to dockerfile or container fix mode."""
    if dockerfile_path:
        fix_dockerfile(dockerfile_path)
    else:
        fix_containers(container_name)


__all__ = ["run_fix", "fix_dockerfile", "fix_containers"]

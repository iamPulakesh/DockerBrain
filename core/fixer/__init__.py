from core.fixer.dockerfile import fix_dockerfile
from core.fixer.container import fix_containers, _is_safe_command


def run_fix(
    dockerfile_path: str | None = None,
    container_name: str | None = None,
) -> None:
    """Route to dockerfile or container fix mode."""
    if dockerfile_path:
        fix_dockerfile(dockerfile_path)
    else:
        fix_containers(container_name)


__all__ = [
    "run_fix",
    "fix_dockerfile",
    "fix_containers",
    "_is_safe_command",
]

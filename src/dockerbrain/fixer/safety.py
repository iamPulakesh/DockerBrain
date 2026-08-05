"""is_safe_command — Docker command safety checker."""

from __future__ import annotations

_BLOCKED_COMMANDS = {"rm", "rmi", "system prune", "volume rm", "network rm", "image rm"}


def is_safe_command(command: str) -> bool:
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

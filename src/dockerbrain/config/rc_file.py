""".dockerbrainrc section parsing."""

from __future__ import annotations

from pathlib import Path


def read_rc_section(section: str = "llm") -> dict[str, str]:
    """Read a section from ~/.dockerbrain/.dockerbrainrc (simple TOML-like INI parser)."""
    rc_path = Path.home() / ".dockerbrain" / ".dockerbrainrc"
    if not rc_path.exists():
        return {}

    data: dict[str, str] = {}
    in_section = False

    for line in rc_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            in_section = stripped.strip("[] ").lower() == section
            continue
        if in_section and "=" in stripped:
            key, _, val = stripped.partition("=")
            val = val.split("#")[0].strip().strip('"').strip("'")
            data[key.strip()] = val

    return data

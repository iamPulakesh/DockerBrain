"""Console singleton — every file that needs Rich output imports from here."""

from rich.console import Console

_console: Console | None = None


def get_console() -> Console:
    global _console
    if _console is None:
        _console = Console()
    return _console

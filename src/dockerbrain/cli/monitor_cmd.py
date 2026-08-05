"""monitor command."""

import click


@click.command()
@click.option(
    "--interval",
    "-i",
    default=1,
    show_default=True,
    help="Polling interval in seconds.",
)
@click.option(
    "--duration",
    "-d",
    default=None,
    type=int,
    help="Total seconds to monitor (default: unlimited).",
)
def monitor(interval: int, duration: int | None) -> None:
    """Display containers' stats."""
    from dockerbrain.monitor import run_monitor

    run_monitor(interval=interval, duration=duration)

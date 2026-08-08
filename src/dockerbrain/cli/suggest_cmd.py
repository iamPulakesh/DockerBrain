"""suggest command."""

import click


@click.command("suggest")
@click.option(
    "--container",
    "-c",
    default=None,
    help="Target a specific container (default: all).",
)
@click.option(
    "--window",
    "-w",
    default=30,
    show_default=True,
    help="Minutes of metric history to include.",
)
@click.option(
    "--dockerfile",
    "-f",
    default=None,
    type=click.Path(exists=True),
    help="Analyze a Dockerfile instead of containers.",
)
def ai_suggest(
    container: str | None, window: int, dockerfile: str | None
) -> None:
    """Get optimization suggestions for Dockerfiles and containers.

    Two modes:

    \b
      1. Container mode (default):
         Collects metrics from the last --window minutes and asks LLM
         for optimizations.
      2. Dockerfile mode (--dockerfile PATH):
         Reads the Dockerfile and asks LLM to suggest overall improvements.

    Requires an API key set in .dockerbrainrc.
    """
    from dockerbrain.advisor.service import run_ai_suggest

    run_ai_suggest(
        container_name=container,
        window_minutes=window,
        dockerfile_path=dockerfile,
    )

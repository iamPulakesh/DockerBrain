"""fix command."""

import click


@click.command()
@click.option(
    "--dockerfile",
    "-f",
    default=None,
    type=click.Path(exists=True),
    help="Path to a Dockerfile to auto-fix.",
)
@click.option(
    "--container",
    "-c",
    default=None,
    help="Target a specific container (default: all).",
)
def fix(dockerfile: str | None, container: str | None) -> None:
    """Automatically diagnose and fix Docker issues.

    \b
    Two modes:
      1. Dockerfile mode (--dockerfile PATH):
         Detects anti-patterns, issues of Dockerfile,
         and overwrites with a .bak backup on confirmation.
      2. Container mode (default):
         Runs analysis, asks LLM for improvements,
         and executes with your confirmation.

    Requires an API key set in .dockerbrainrc.
    """
    from dockerbrain.fixer import run_fix

    run_fix(dockerfile_path=dockerfile, container_name=container)

"""CLI entry point — assembles all subcommands."""

import platform
import threading
import atexit

import click

from dockerbrain import __version__

_UPDATE_AVAILABLE = None


def _run_update_check() -> None:
    global _UPDATE_AVAILABLE
    from dockerbrain.cli.update_check import check_for_updates

    _UPDATE_AVAILABLE = check_for_updates()


def _print_update_notice() -> None:
    if _UPDATE_AVAILABLE:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(
            f"\n[bold yellow]Notice:[/] A new release of DockerBrain is available! ([red]{__version__}[/] → [green]{_UPDATE_AVAILABLE}[/])"
        )
        console.print(
            "[dim]To update, run:[/] [cyan]pip install --upgrade dockerbrain[/]\n"
        )


def print_version(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Print version with build metadata and exit."""
    if not value or ctx.resilient_parsing:
        return
    click.echo(
        f"dockerbrain v{__version__} "
        f"(Python {platform.python_version()}, {platform.system()} {platform.machine()})"
    )
    ctx.exit()


class _HiddenHelpCommand(click.Command):
    """A Click Command that hides the built-in --help from the options list."""

    def get_params(self, ctx: click.Context) -> list:
        params = super().get_params(ctx)
        for p in params:
            if isinstance(p, click.Option) and p.name == "help":
                p.hidden = True
        return params


class _HiddenHelpGroup(click.Group):
    """A Click Group whose subcommands all use HiddenHelpCommand."""

    command_class = _HiddenHelpCommand

    def invoke(self, ctx: click.Context):
        if ctx.invoked_subcommand is not None:
            threading.Thread(target=_run_update_check, daemon=True).start()
            atexit.register(_print_update_notice)
        return super().invoke(ctx)

_LAZY_COMMANDS: dict[str, tuple[str, str]] = {
    "monitor": ("dockerbrain.cli.monitor_cmd", "monitor"),
    "suggest": ("dockerbrain.cli.suggest_cmd", "ai_suggest"),
    "fix": ("dockerbrain.cli.fix_cmd", "fix"),

    "template": ("dockerbrain.cli.template_cmd", "template"),
    "init": ("dockerbrain.cli.config_cmd", "init"),
    "config": ("dockerbrain.cli.config_cmd", "config"),
    "env": ("dockerbrain.cli.config_cmd", "env"),
}


class _LazyGroup(_HiddenHelpGroup):
    """A Click Group that lazy loads commands to improve startup time."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        return sorted(_LAZY_COMMANDS.keys())

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name not in _LAZY_COMMANDS:
            return None
        mod_name, func_name = _LAZY_COMMANDS[cmd_name]
        import importlib
        
        mod = importlib.import_module(mod_name)
        return getattr(mod, func_name)


@click.group(cls=_LazyGroup, add_help_option=False)
@click.option(
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    hidden=True,
    callback=lambda ctx, param, value: (
        (click.echo(ctx.get_help(), color=ctx.color) or ctx.exit()) if value else None
    ),
)
@click.option(
    "--version",
    is_flag=True,
    callback=print_version,
    expose_value=False,
    is_eager=True,
    help="Check DockerBrain version.",
)
def cli() -> None:
    pass

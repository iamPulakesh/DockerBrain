"""template list + template use commands."""

import click


class _NoHelpOptGroup(click.Group):
    """Group that hides the --help option from the help output."""

    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        opt = super().get_help_option(ctx)
        if opt:
            opt.hidden = True
        return opt


@click.group(cls=_NoHelpOptGroup)
def template() -> None:
    """Browse and use curated Dockerfile templates."""


@template.command("list")
def template_list() -> None:
    """Show all available Dockerfile templates."""
    from rich.table import Table

    from dockerbrain.templates.registry import TEMPLATES_META
    from dockerbrain.ui.cli.console import get_console

    console = get_console()
    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        expand=False,
    )
    table.add_column("#", style="dim", width=3)
    table.add_column("Template", style="bold green", no_wrap=True)
    table.add_column("Stack")
    table.add_column("Description")

    for i, (key, tpl) in enumerate(sorted(TEMPLATES_META.items()), 1):
        table.add_row(str(i), key, tpl["name"], tpl["description"])

    console.print()
    console.print(table)
    console.print("\n[dim]Use a template:[/] [cyan]dockerb template use <name>[/]\n")


@template.command("use")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Overwrite existing Dockerfile.")
def template_use(name: str, force: bool) -> None:
    """Generate a Dockerfile from a template.

    \b
    Examples:
      dockerb template use fastapi
      dockerb template use nextjs --force
      dockerb template use go
    """
    from pathlib import Path

    from rich.prompt import Confirm
    from rich.syntax import Syntax

    from dockerbrain.templates.registry import get_template, get_template_names
    from dockerbrain.ui.cli.console import get_console

    console = get_console()
    tpl = get_template(name)

    if tpl is None:
        console.print(f"[red]Unknown template:[/] [bold]{name}[/]")
        console.print(f"[dim]Available: {', '.join(get_template_names())}[/]")
        return

    dockerfile_path = Path("Dockerfile")

    if dockerfile_path.exists() and not force:
        if not Confirm.ask(
            "[yellow]Dockerfile already exists.[/] Overwrite?",
            default=False,
        ):
            console.print("[dim]Skipped. No changes made.[/]")
            return

    dockerfile_path.write_text(tpl["dockerfile"], encoding="utf-8")
    console.print(f"[green]Created Dockerfile[/] [dim]({tpl['name']})[/]")

    dockerignore_path = Path(".dockerignore")
    if not dockerignore_path.exists():
        dockerignore_content = """\
.git
.gitignore
node_modules
__pycache__
*.pyc
.env
.venv
.dockerignore
Dockerfile
README.md
.idea
.vscode
"""
        dockerignore_path.write_text(dockerignore_content, encoding="utf-8")
        console.print("[green]Created .dockerignore[/]")

    console.print()
    console.print(
        Syntax(tpl["dockerfile"], "dockerfile", theme="monokai", line_numbers=True)
    )

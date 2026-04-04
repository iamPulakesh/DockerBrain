import platform
import click
from core import __version__

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


@click.group(cls=_HiddenHelpGroup, add_help_option=False)
@click.option(
    "--help",
    is_flag=True,
    is_eager=True,
    expose_value=False,
    hidden=True,
    callback=lambda ctx, param, value: (click.echo(ctx.get_help(), color=ctx.color) or ctx.exit()) if value else None,
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

# Commands
@cli.command()
@click.option("--interval", "-i", default=1, show_default=True, help="Polling interval in seconds.")
@click.option("--duration", "-d", default=None, type=int, help="Total seconds to monitor (default: unlimited).")
def monitor(interval: int, duration: int | None) -> None:
    """Display containers' stats."""
    from core.monitor import run_monitor
    run_monitor(interval=interval, duration=duration)

@cli.command("suggest")
@click.option("--container", "-c", default=None, help="Target a specific container (default: all).")
@click.option("--window", "-w", default=30, show_default=True, help="Minutes of metric history to include.")
@click.option("--dockerfile", "-f", default=None, type=click.Path(exists=True), help="Analyze a Dockerfile instead of containers.")
@click.option("--no-rules", is_flag=True, default=False, help="Skip rule-based suggestions, send raw metrics only.")
def ai_suggest(container: str | None, window: int, dockerfile: str | None, no_rules: bool) -> None:
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
    from core.ai_advisor import run_ai_suggest

    run_ai_suggest(
        container_name=container,
        window_minutes=window,
        dockerfile_path=dockerfile,
        no_rules=no_rules,
    )

@cli.command()
@click.option("--dockerfile", "-f", default=None, type=click.Path(exists=True),
              help="Path to a Dockerfile to auto-fix.")
@click.option("--container", "-c", default=None,
              help="Target a specific container (default: all).")
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
    from core.fixer import run_fix

    run_fix(dockerfile_path=dockerfile, container_name=container)

@cli.command()
@click.option("--force", is_flag=True, default=False,
              help="Overwrite existing Dockerfile and .dockerignore forcefully.")
def dockerize(force: bool) -> None:
    """Generate a Dockerfile and .dockerignore for your project.

    \b
    Examples:
      dockerb dockerize                  # Generate a Dockerfile and .dockerignore for your project
      dockerb dockerize --force          # Overwrite existing Dockerfile forcefully

    Requires an API key set in .dockerbrainrc.
    """
    from core.dockerizer import run_dockerize

    run_dockerize(project_path=".", force=force)

class _NoHelpOptGroup(click.Group):
    """Group that hides the --help option from the help output."""
    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        opt = super().get_help_option(ctx)
        if opt:
            opt.hidden = True
        return opt

@cli.group(cls=_NoHelpOptGroup)
def template() -> None:
    """Browse and use curated Dockerfile templates."""

@template.command("list")
def template_list() -> None:
    """Show all available Dockerfile templates."""
    from rich.console import Console
    from rich.table import Table

    from core.templates import TEMPLATES

    console = Console()
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

    for i, (key, tpl) in enumerate(sorted(TEMPLATES.items()), 1):
        table.add_row(str(i), key, tpl["name"], tpl["description"])

    console.print()
    console.print(table)
    console.print(
        "\n[dim]Use a template:[/] [cyan]dockerb template use <name>[/]\n"
    )

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

    from rich.console import Console
    from rich.syntax import Syntax

    from core.templates import get_template, get_template_names

    console = Console()
    tpl = get_template(name)

    if tpl is None:
        console.print(f"[red]Unknown template:[/] [bold]{name}[/]")
        console.print(
            f"[dim]Available: {', '.join(get_template_names())}[/]"
        )
        return

    dockerfile_path = Path("Dockerfile")

    if dockerfile_path.exists() and not force:
        from rich.prompt import Confirm
        if not Confirm.ask(
            "[yellow]Dockerfile already exists.[/] Overwrite?",
            default=False,
        ):
            console.print("[dim]Skipped. No changes made.[/]")
            return

    dockerfile_path.write_text(tpl["dockerfile"], encoding="utf-8")
    console.print(
        f"[green]Created Dockerfile[/] [dim]({tpl['name']})[/]"
    )

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
    console.print(Syntax(tpl["dockerfile"], "dockerfile", theme="monokai", line_numbers=True))


@cli.command()
def init() -> None:
    """Create a .dockerbrainrc config file in the current directory.

    Creates a TOML config with defaults for monitoring thresholds,
    LLM model selection, and other settings. Edit it as per your requirements.
    """
    from pathlib import Path

    from rich.console import Console

    console = Console()
    config_path = Path(".dockerbrainrc")

    if config_path.exists():
        console.print(f"[yellow] {config_path} already exists.[/]")
        return

    config_content = '''\
# DockerBrain Configuration

# LLM Provider & Models, To switch provider or model, edit below.

# GEMINI (Overall Best)
#   provider = "gemini"
#   model = "gemini-3.1-flash-lite-preview", "gemini-flash-latest"

# GROQ (Fast)
#   provider = "groq"
#   model = "openai/gpt-oss-120b", "llama-3.3-70b-versatile"   

# OLLAMA (Local and Free)
#   provider = "ollama"
#   model = "llama3.1", "codestral", "qwen2.5-coder" (Or any other model)
#   base_url = "http://localhost:11434/v1"   # change if not default

[llm]
provider = "gemini"
model    = "gemini-3.1-flash-lite-preview"
api_key  = ""              # Paste your LLM API key here
# base_url = ""            # Only for Ollama

[monitor]
interval             = 5    # Polling interval in seconds
alert_memory_pct     = 80   # Memory % threshold for warnings
alert_cpu_idle       = 0.5  # CPU % below which a container is "idle"
idle_consecutive_polls = 10 # Consecutive idle polls before flagging


[optimize]
check_secrets         = true  # Scan for hardcoded secrets in ENV
check_base_image      = true  # Flag large base images
check_apt_recommends  = true  # Flag apt-get without --no-install-recommends
check_cache_busting   = true  # Flag COPY . . before dependency install
check_dockerignore    = true  # Warn if .dockerignore is missing
'''

    config_path.write_text(config_content, encoding="utf-8")
    console.print(f"[green]Created [bold]{config_path}[/bold][/]")

@cli.command()
def env() -> None:
    """Check your environment and configs."""
    import sqlite3
    from pathlib import Path

    import docker
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()
    lines = Text()
    all_ok = True

    def _ok(label: str, detail: str) -> None:
        lines.append(f"  {label:<20}", style="bold")
        lines.append(f"{detail}\n")

    def _fail(label: str, detail: str) -> None:
        nonlocal all_ok
        all_ok = False
        lines.append(f"  {label:<20}", style="bold red")
        lines.append(f"{detail}\n")

    try:
        client = docker.from_env()
        info = client.version()
        _ok("Docker daemon", f"running (v{info.get('Version', '?')})")
    except Exception :
        _fail("Docker daemon", f"not reachable")

    try:
        _ok("Docker SDK", f"docker-py {docker.__version__}")
    except ImportError:
        _fail("Docker SDK", "not installed → run: pip install docker")

    try:
        from core.llm import load_llm_config
        cfg = load_llm_config()
        _ok("LLM Provider", cfg.provider)
        _ok("LLM Model", cfg.model)
        masked = cfg.api_key[:4] + "…" + cfg.api_key[-4:] if len(cfg.api_key) > 8 else "set ✓"
        _ok("API Key", f"{masked}")
    except SystemExit:
        _fail("API Key", "not set in .dockerbrainrc")

    db_path = Path.home() / ".dockerbrain" / "metrics.db"
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        try:
            conn = sqlite3.connect(str(db_path))
            row_count = conn.execute("SELECT COUNT(*) FROM container_metrics").fetchone()[0]
            conn.close()
            _ok("SQLite DB", f"{db_path} ({size_kb:.0f} KB, {row_count:,} rows)")
        except Exception:
            _ok("SQLite DB", f"{db_path} ({size_kb:.0f} KB)")
    else:
        _fail("SQLite DB", f"not found at {db_path} — run: dockerb monitor")

    status = "[bold green]All checks passed!" if all_ok else "[bold yellow]Some checks failed"
    console.print(
        Panel(
            lines,
            title="[bold cyan] Environment Check[/]",
            subtitle=status,
            border_style="cyan",
            expand=False,
            padding=(1, 2),
        )
    )
    raise SystemExit(0 if all_ok else 1)

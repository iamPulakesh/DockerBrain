"""init, config, and env commands."""

import click


@click.command()
def init() -> None:
    """Create a .dockerbrainrc config file in ~/.dockerbrain/.

    Creates a TOML config with defaults for monitoring thresholds,
    LLM model selection, and other settings. Edit it as per your requirements.
    """
    from pathlib import Path

    from rich.prompt import Confirm

    from dockerbrain.ui.cli.console import get_console

    console = get_console()
    config_dir = Path.home() / ".dockerbrain"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / ".dockerbrainrc"

    if config_path.exists():
        if not Confirm.ask(
            f"[yellow]{config_path} already exists.[/] Overwrite?",
            default=False,
        ):
            console.print("[dim]Skipped. No changes made.[/]")
            return

    config_content = """\
# DockerBrain Configuration

# LLM Provider & Models, To switch provider or model, edit below.

# CHATGPT 
#   provider = "chatgpt"
#   model examples = "gpt-6-omni", "gpt-5.5-turbo", "gpt-5.4-mini"

# ANTHROPIC
#   provider = "anthropic"
#   model examples = "claude-5-opus", "claude-5-sonnet", "claude-sonnet-4-6"

[llm]
provider = "# choose provider"
model    = "# choose model code"
api_key  = "# Paste your LLM API key here"              

[monitor]
interval             = 5    # Polling interval in seconds
alert_memory_pct     = 70   # Memory % threshold for warnings
alert_cpu_idle       = 0.1  # CPU % below which a container is "idle"
idle_consecutive_polls = 5  # Consecutive idle polls before flagging
"""

    config_path.write_text(config_content, encoding="utf-8")
    console.print(f"[green]Created [bold]{config_path}[/bold][/]")


@click.command()
def config() -> None:
    """Open the .dockerbrainrc config file in your default editor."""
    import subprocess
    import sys
    from pathlib import Path

    from dockerbrain.ui.cli.console import get_console

    console = get_console()
    config_path = Path.home() / ".dockerbrain" / ".dockerbrainrc"

    if not config_path.exists():
        console.print("[yellow]Config not found.[/] Run [cyan]dockerb init[/] first.")
        return

    if sys.platform == "win32":
        subprocess.run(["notepad", str(config_path)])
    elif sys.platform == "darwin":
        subprocess.run(["open", str(config_path)])
    else:
        editor = __import__("os").environ.get("EDITOR", "nano")
        subprocess.run([editor, str(config_path)])


@click.command()
def env() -> None:
    """Check your environment and configs."""
    import sqlite3
    from pathlib import Path

    import docker
    from rich.panel import Panel
    from rich.text import Text

    from dockerbrain.ui.cli.console import get_console

    console = get_console()
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
    except Exception:
        _fail("Docker daemon", f"not reachable")

    try:
        _ok("Docker SDK", f"docker-py {docker.__version__}")
    except ImportError:
        _fail("Docker SDK", "not installed -- run: pip install docker")

    from dockerbrain.config.rc_file import read_rc_section
    
    rc = read_rc_section("llm")
    
    provider = rc.get("provider")
    if provider:
        _ok("LLM Provider", provider)
    else:
        _fail("LLM Provider", "missing in ~/.dockerbrain/.dockerbrainrc")
        
    model = rc.get("model")
    if model:
        _ok("LLM Model", model)
    else:
        _fail("LLM Model", "missing in ~/.dockerbrain/.dockerbrainrc")
        
    api_key = rc.get("api_key")
    if api_key:
        masked = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else "set"
        _ok("API Key", masked)
    else:
        _fail("API Key", "missing in ~/.dockerbrain/.dockerbrainrc")

    db_path = Path.home() / ".dockerbrain" / "metrics.db"
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        try:
            conn = sqlite3.connect(str(db_path))
            row_count = conn.execute(
                "SELECT COUNT(*) FROM container_metrics"
            ).fetchone()[0]
            conn.close()
            _ok("SQLite DB", f"{db_path} ({size_kb:.0f} KB, {row_count:,} rows)")
        except Exception:
            _ok("SQLite DB", f"{db_path} ({size_kb:.0f} KB)")
    else:
        _fail("SQLite DB", f"not found at {db_path} — run: dockerb monitor")

    status = (
        "[bold green]ALL OK"
        if all_ok
        else "[bold yellow]Config Missing!"
    )
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

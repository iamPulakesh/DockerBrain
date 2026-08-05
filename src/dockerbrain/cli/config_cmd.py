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

# GEMINI  
#   provider = "gemini"
#   model = "gemini-3.1-flash-lite-preview", "gemini-flash-latest"

# CHATGPT 
#   provider = "chatgpt"
#   model = "gpt-5.4-mini", "gpt-5.4-nano"

# CLAUDE 
#   provider = "claude"
#   model = "claude-sonnet-4-6", "claude-haiku-4-6"

# GROQ (Fast)
#   provider = "groq"
#   model = "openai/gpt-oss-120b", "llama-3.3-70b-versatile"   

# OLLAMA (Local and Free)
#   provider = "ollama"
#   model = "llama3.1", "codestral", "qwen2.5-coder" (Or any other model)
#   base_url = "http://localhost:11434/v1"   # change if not default

[llm]
provider = "groq"
model    = "openai/gpt-oss-120b"
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
        _fail("Docker SDK", "not installed → run: pip install docker")

    try:
        from dockerbrain.config.settings import load_llm_config

        cfg = load_llm_config()
        _ok("LLM Provider", cfg.provider)
        _ok("LLM Model", cfg.model)
        masked = (
            cfg.api_key[:4] + "…" + cfg.api_key[-4:]
            if len(cfg.api_key) > 8
            else "set ✓"
        )
        _ok("API Key", f"{masked}")
    except SystemExit:
        _fail("API Key", "not set in ~/.dockerbrain/.dockerbrainrc")

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
        "[bold green]All checks passed!"
        if all_ok
        else "[bold yellow]Some checks failed"
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

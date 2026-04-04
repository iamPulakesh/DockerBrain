from __future__ import annotations

import json
from pathlib import Path

from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.syntax import Syntax
from rich.table import Table

from core.llm import load_llm_config, generate, LLMConfig

console = Console()

_LANGUAGE_SIGNATURES: dict[str, list[str]] = {
    "Python":       ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "setup.cfg", "poetry.lock"],
    "Node.js":      ["package.json", "yarn.lock", "pnpm-lock.yaml", "package-lock.json"],
    "TypeScript":   ["tsconfig.json"],
    "Deno":         ["deno.json", "deno.jsonc"],
    "Go":           ["go.mod", "go.sum"],
    "Rust":         ["Cargo.toml", "Cargo.lock"],
    "Java/Kotlin":  ["pom.xml", "build.gradle", "build.gradle.kts", "gradlew"],
    "Scala":        ["build.sbt"],
    "Ruby":         ["Gemfile", "Gemfile.lock"],
    "PHP":          ["composer.json", "composer.lock"],
    "C#/.NET":      ["*.csproj", "*.sln", "Program.cs"],
    "F#":           ["*.fsproj"],
    "C/C++":        ["CMakeLists.txt", "*.c", "*.cpp", "configure.ac", "meson.build"],
    "Swift":        ["Package.swift"],
    "Dart/Flutter": ["pubspec.yaml"],
    "Elixir":       ["mix.exs"],
    "Erlang":       ["rebar.config", "rebar.lock"],
    "Haskell":      ["stack.yaml", "*.cabal"],
    "Clojure":      ["project.clj", "deps.edn"],
    "Perl":         ["cpanfile", "Makefile.PL"],
    "R":            ["DESCRIPTION", "*.Rproj"],
    "Lua":          ["*.rockspec"],
    "Crystal":      ["shard.yml"],
    "Static/HTML":  ["index.html"],
}

_SKIP_DIRS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__", ".tox",
    ".pytest_cache", ".mypy_cache", ".egg-info", "dist", "build",
    ".idea", ".vscode", "target", "bin", "obj", ".next", ".nuxt",
    ".dart_tool", ".pub-cache", "_build", "deps", "vendor",
    ".stack-work", "elm-stuff", "zig-cache",
}

_SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".o",
    ".class", ".jar", ".war", ".db", ".sqlite", ".sqlite3",
    ".lock", ".log", ".bak", ".swp", ".swo",
}

_DOCKERIZE_SYSTEM = (
    "You are a world-class Docker expert. Given a project's directory structure and key config "
    "file contents, generate a production-ready Dockerfile.\n\n"
    "CRITICAL RULES:\n"
    "1. Return ONLY a valid JSON object with exactly two keys:\n"
    '   - "dockerfile": the full Dockerfile content as a string\n'
    '   - "dockerignore": the full .dockerignore content as a string\n'
    "2. No markdown, no code fences, no explanation — ONLY the raw JSON object.\n"
    "3. Use multi-stage builds where appropriate (especially for compiled languages).\n"
    "4. Always use slim or alpine base images.\n"
    "5. Install dependencies BEFORE copying source code (layer caching).\n"
    "6. Chain RUN commands with && to minimize layers.\n"
    "7. Clean up package manager caches (apt, apk, pip, npm).\n"
    "8. Add a non-root USER for security.\n"
    "9. Add a HEALTHCHECK if a web server or API is detected.\n"
    "10. Use exec-form CMD (JSON array).\n"
    "11. Pin base image versions (e.g., python:3.12-slim, not python:latest).\n"
    "12. Add brief comments in the Dockerfile explaining each stage/step.\n"
    "13. The .dockerignore should exclude: .git, .venv, venv, node_modules, __pycache__, "
    "*.pyc, .env, .idea, .vscode, *.md, dist, build, tests, .pytest_cache, .mypy_cache, "
    "and any other development-only files detected in the project.\n"
)

def _scan_project(project_dir: Path) -> dict:
    """Scan the project directory and return structured info for the AI prompt."""

    tree_lines: list[str] = []

    def _walk(current: Path, prefix: str, depth: int) -> None:
        if depth > 3:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        except PermissionError:
            return

        dirs = [e for e in entries if e.is_dir() and e.name not in _SKIP_DIRS and not e.name.startswith(".")]
        files = [e for e in entries if e.is_file() and e.suffix not in _SKIP_EXTENSIONS]

        for f in files:
            tree_lines.append(f"{prefix}{f.name}")
        for d in dirs:
            tree_lines.append(f"{prefix}{d.name}/")
            _walk(d, prefix + "  ", depth + 1)

    _walk(project_dir, "", 0)

    # Detect language
    detected_languages: list[str] = []
    for language, signatures in _LANGUAGE_SIGNATURES.items():
        for sig in signatures:
            if "*" in sig:
                # Glob pattern
                if list(project_dir.glob(sig)):
                    detected_languages.append(language)
                    break
            elif (project_dir / sig).exists():
                detected_languages.append(language)
                break

    # Read key config files 
    key_files_content: dict[str, str] = {}
    priority_files = [
        "requirements.txt", "pyproject.toml", "setup.py", "Pipfile",
        "package.json", "tsconfig.json", "deno.json",
        "go.mod", "Cargo.toml", "pom.xml",
        "build.gradle", "build.sbt",
        "Gemfile", "composer.json", "mix.exs",
        "CMakeLists.txt", "Package.swift", "pubspec.yaml",
        "stack.yaml", "project.clj", "deps.edn",
        "rebar.config", "shard.yml", "cpanfile",
        "Makefile", "Procfile", "app.json", "runtime.txt",
    ]

    collected = 0
    for fname in priority_files:
        fpath = project_dir / fname
        if fpath.exists() and collected < 5:
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").splitlines()[:200]
                key_files_content[fname] = "\n".join(lines)
                collected += 1
            except Exception:
                pass

    has_dockerfile = (project_dir / "Dockerfile").exists()
    has_dockerignore = (project_dir / ".dockerignore").exists()

    return {
        "tree": "\n".join(tree_lines[:150]), 
        "detected_languages": detected_languages,
        "key_files": key_files_content,
        "has_dockerfile": has_dockerfile,
        "has_dockerignore": has_dockerignore,
    }


def _display_scan_results(scan: dict) -> None:
    """Show the user what was detected before generating."""

    table = Table(
        show_header=True,
        header_style="bold cyan",
        border_style="bright_blue",
        expand=False,
    )
    table.add_column("Property", style="bold", no_wrap=True)
    table.add_column("Value", style="white")

    languages = ", ".join(scan["detected_languages"]) if scan["detected_languages"] else "Unknown"
    table.add_row("Detected Language", f"[green]{languages}[/]")
    table.add_row("Configs", ", ".join(scan["key_files"].keys()) or "None")
    table.add_row("Dockerfile", "[yellow]Yes[/]" if scan["has_dockerfile"] else "[dim]No[/]")
    table.add_row(".dockerignore", "[yellow]Yes[/]" if scan["has_dockerignore"] else "[dim]No[/]")

    console.print()
    console.print(table)
    console.print()


def _generate_via_ai(scan: dict, config: LLMConfig) -> dict:
    """Send project info to the configured LLM and get back Dockerfile + .dockerignore."""

    # Build the prompt
    parts = ["## Project Analysis\n"]

    if scan["detected_languages"]:
        parts.append(f"**Detected language(s):** {', '.join(scan['detected_languages'])}\n")

    parts.append(f"### Directory Structure\n```\n{scan['tree']}\n```\n")

    for fname, content in scan["key_files"].items():
        parts.append(f"### {fname}\n```\n{content}\n```\n")

    parts.append("\nGenerate an optimized Dockerfile and .dockerignore for this project.")

    prompt = "\n".join(parts)

    with console.status("[bold green]Generating Dockerfile...[/]", spinner="dots"):
        raw = generate(
            prompt=prompt,
            system_instruction=_DOCKERIZE_SYSTEM,
            config=config,
        )

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        console.print(
            Panel(
                f"[red]Could not parse LLM response as JSON.[/]\n\n[dim]{raw[:500]}[/]",
                title="[bold red]Parse Error[/]",
                border_style="red",
                expand=False,
            )
        )
        return {}

def _preview_files(dockerfile: str, dockerignore: str) -> None:
    """Show side-by-side preview of the generated files."""

    left = Panel(
        Syntax(dockerfile, "dockerfile", theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold cyan]Dockerfile[/]",
        border_style="cyan",
        expand=True,
    )
    right = Panel(
        Syntax(dockerignore, "ini", theme="monokai", line_numbers=True, word_wrap=True),
        title="[bold cyan].dockerignore[/]",
        border_style="cyan",
        expand=True,
    )
    console.print()
    console.print(Columns([left, right], equal=True, expand=True))

def run_dockerize(project_path: str, force: bool = False) -> None:
    """Scan a project directory and generate a Dockerfile + .dockerignore via AI."""

    project_dir = Path(project_path).resolve()

    if not project_dir.is_dir():
        console.print(f"[red]Not a directory: {project_dir}[/]")
        raise SystemExit(1)

    console.print(
        Panel(
            f"[bold]Scanning:[/] [cyan]{project_dir}[/]",
            border_style="cyan",
            expand=False,
        )
    )

    scan = _scan_project(project_dir)

    if not scan["detected_languages"]:
        console.print(
            "[yellow]Could not auto-detect the project language. "
            "Attempt to generate a Dockerfile based on the directory structure.[/]\n"
        )

    _display_scan_results(scan)

    # Check for existing files
    dockerfile_path = project_dir / "Dockerfile"
    dockerignore_path = project_dir / ".dockerignore"

    if not force:
        if dockerfile_path.exists():
            if not Confirm.ask(
                f"[yellow]Dockerfile already exists at [cyan]{dockerfile_path}[/cyan]. Overwrite?[/]",
                default=False,
            ):
                console.print("[dim]Aborted.[/]")
                return

    config = load_llm_config()
    result = _generate_via_ai(scan, config)

    if not result:
        return

    dockerfile_content = result.get("dockerfile", "")
    dockerignore_content = result.get("dockerignore", "")

    if not dockerfile_content:
        console.print("[red]Returned an empty Dockerfile.[/]")
        return

    # Preview
    _preview_files(dockerfile_content, dockerignore_content)

    console.print()
    if not Confirm.ask("[bold]Write these files?[/]", default=True):
        console.print("[dim]Aborted. No files written.[/]")
        return

    dockerfile_path.write_text(dockerfile_content + "\n", encoding="utf-8")
    console.print(f"[green bold]Created:[/] [cyan]{dockerfile_path}[/]")

    if dockerignore_content:
        if dockerignore_path.exists() and not force:
            if Confirm.ask(
                f"[yellow].dockerignore already exists. Overwrite?[/]",
                default=False,
            ):
                dockerignore_path.write_text(dockerignore_content + "\n", encoding="utf-8")
                console.print(f"[green bold]Created:[/] [cyan]{dockerignore_path}[/]")
            else:
                console.print("[dim]Skipped .dockerignore.[/]")
        else:
            dockerignore_path.write_text(dockerignore_content + "\n", encoding="utf-8")
            console.print(f"[green bold]Created:[/] [cyan]{dockerignore_path}[/]")

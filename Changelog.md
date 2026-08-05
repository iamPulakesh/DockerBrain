# Changelog

## v1.3.1 — Minor UI Performance Overhaul (2026-08-06)

- **UI performance Improvement:** Completely rewrote the `dockerb monitor` table rendering logic to use in-place cell updates instead of full DOM rebuilds. The UI performance is now better than before.
- **Log Jitter Fix:** Fixed a severe bug where background stat polling would reset the cursor position and trigger aggressive layout jumping while reading logs.


## v1.3.0 — TUI Refactoring & UX Improvements (2026-08-05)

- **UX Overhaul:** Added the `e` (Expand) hotkey to toggle fullscreen container logs.
- **Scroll Fix:** Resolved a UI bug where the log pane would constantly snap to the bottom during background polling.
- **TUI Cleaner Footer:** Disabled dynamic footer resizing and prevented the `q` (Quit) intercept popup for a much stabler layout.
- **New Templates:** Added 5 new `dockerb template` options: `php`, `python`, `cpp`, `swift`, and `ktor` (Now 30 total).
- **Optimizer Rules:** Replaced outdated rules with a critical `running_as_root` security rule to catch unsafe privileged containers.
- **Architecture Refactor:** Massive internal refactoring. Decoupled frontend presentation from backend Docker mutations via Mixins, and extracted pure metrics logic for better testing.

## v1.2.1 — Expanded Models Support & Log Scanning (2026-04-09)

- **New Providers:** Added support for **ChatGPT** and **Claude** models.
- **Container Issue Scanning:** Added the `i` (Scan Issues) hotkey in the Logs tab of `dockerb monitor`. Instantly scans root-cause analysis for any crashed, stopped, or dead container directly into the UI.
- **Log Improvements:** Docker logs inside the TUI are now cleanly parsed and automatically translated to your local system timezone (`HH:MM:SS`) for easier readability.
- **Minor Bug Fixes:** Fixed some issues in the TUI.

## v1.1.0 — Monitor UX Overhaul (2026-04-06)

- **Interactive TUI monitor** (`dockerb monitor`) with full keyboard-driven workflow

## v1.0 — Initial Release (2026-04-04)

- Real-time container monitoring with live Rich dashboard
- Rule-based optimizer with 5 built-in rules (idle, memory hog, no limit, high restart, stale image)
- LLM based suggestions for containers and Dockerfiles via `suggest`
- LLM based auto-fix for containers and Dockerfiles via `fix`
- 25+ curated Dockerfile templates via `template`
- Multi-provider LLM support: Gemini, Groq, Ollama
- Single-file configuration via `.dockerbrainrc`
- SQLite-backed metrics and LLM based suggestion history
- `pre-commit` hook support

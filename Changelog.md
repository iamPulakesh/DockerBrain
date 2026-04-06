# Changelog

## v1.1.0 — Monitor UX Overhaul (2026-04-06)

- **Interactive TUI monitor** (`dockerb monitor`) with full keyboard-driven workflow

## v1.0 — Initial Release (2026-04-04)

- Real-time container monitoring with live Rich dashboard
- Rule-based optimizer with 5 built-in rules (idle, memory hog, no limit, high restart, stale image)
- LLM based suggestions for containers and Dockerfiles via `suggest`
- LLM based auto-fix for containers and Dockerfiles via `fix`
- LLM based Dockerfile + `.dockerignore` generation from any project via `dockerize`
- 25+ curated Dockerfile templates via `template`
- Multi-provider LLM support: Gemini, Groq, Ollama
- Single-file configuration via `.dockerbrainrc`
- SQLite-backed metrics and LLM based suggestion history
- `pre-commit` hook support

# Changelog

## v1.0 — Initial Release (2026-04-04)

- Real-time container monitoring with live Rich dashboard
- Rule-based optimizer with 5 built-in rules (idle, memory hog, no limit, high restart, stale image)
- AI-powered suggestions for containers and Dockerfiles via `suggest`
- AI auto-fix for containers and Dockerfiles via `fix` (with safety guardrails)
- AI Dockerfile + `.dockerignore` generation from any project via `dockerize`
- 20+ curated Dockerfile templates via `template` (no API key required)
- Multi-provider LLM support: Gemini, Groq, Ollama
- Single-file configuration via `.dockerbrainrc`
- SQLite-backed metrics and AI suggestion history
- `pre-commit` hook support

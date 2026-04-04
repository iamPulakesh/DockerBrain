# DockerBrain

**AI-powered Docker container monitoring, optimization, and Dockerfile generation CLI.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/dockerbrain)](https://pypi.org/project/dockerbrain/)

DockerBrain monitors your Docker containers in real time, detects resource issues, and uses LLMs to generate actionable optimizations for running containers and Dockerfiles. Supports **Gemini**, **Groq**, and **Ollama**. All configuration lives in a single `.dockerbrainrc` file.

---

## Features

| Feature | Command | LLM Required |
|---|---|:---:|
| Real-time container monitoring | `dockerb monitor` | No |
| AI optimization suggestions | `dockerb suggest` | Yes |
| Auto-fix containers & Dockerfiles | `dockerb fix` | Yes |
| AI Dockerfile generation from project | `dockerb dockerize` | Yes |
| Curated Dockerfile templates | `dockerb template` | No |
| Environment & config diagnostics | `dockerb env` | No |

---

## Installation

**Requirements:** Python 3.10+ and a running Docker daemon.

```bash
pip install dockerbrain
```

Verify:

```bash
dockerb --version
```

### Configure an LLM Provider

```bash
dockerb init
```

This creates `.dockerbrainrc` in your project directory. Open it and set your provider and key:

```ini
[llm]
provider = "gemini"
model    = "gemini-3.1-flash-lite-preview"
api_key  = "your_key_here"
```

| Provider | API Key | Link |
|---|:---:|---|
| Gemini | Required | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Groq | Required | [console.groq.com/keys](https://console.groq.com/keys) |
| Ollama | Not Required | [ollama.com](https://ollama.com) |

> `monitor`, `template`, and `env` commands work without an API key.

---

## Usage

DockerBrain exposes all functionality through the `dockerb` CLI. Run the following to see all available commands and options:

```bash
dockerb --help
```

Each command also has its own help page, for example `dockerb suggest --help`, `dockerb fix --help`, etc.

---

## Pre-commit Hook

DockerBrain can run as a [pre-commit](https://pre-commit.com/) hook to lint Dockerfiles on every commit:

```yaml
# .pre-commit-config.yaml 
repos:
  - repo: https://github.com/iamPulakesh/DockerBrain
    rev: v1.0
    hooks:
      - id: dockerbrain-fix
```

---

## Development

```bash
git clone https://github.com/iamPulakesh/DockerBrain.git
cd DockerBrain
pip install -e ".[dev]"

make test                              
make lint                              
make clean                    
```

---

See [Changelog.md](Changelog.md) for the full release history.

---

## Contributing

1. Fork the repository
2. Contribute
3. Open a Pull Request

---

## License

Apache-2.0 — see [LICENSE](LICENSE) for details.

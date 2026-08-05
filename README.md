<div align="center">

# DockerBrain

**An intelligent terminal dashboard for Docker monitoring, automated debugging, and optimization.**

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/dockerbrain?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=RED&left_text=PyPI+downloads)](https://pepy.tech/projects/dockerbrain)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/dockerbrain)](https://pypi.org/project/dockerbrain/)

<p align="center">
  DockerBrain monitors your Docker containers in real time, detects resource issues, and uses LLMs to generate actionable optimizations for running containers and Dockerfiles.
</p>

---

</div>

## Features

| Feature | Command | LLM Required |
|---|---|:---:|
| Real-time container monitoring | `dockerb monitor` | No |
| AI optimization suggestions | `dockerb suggest` | Yes |
| Auto-fix containers & Dockerfiles | `dockerb fix` | Yes |
| Curated Dockerfile templates | `dockerb template` | No |
| Environment & config diagnostics | `dockerb env` | No |

---

## Usage

DockerBrain exposes all functionality through the `dockerb` CLI. Run the following to see all available commands and options:

```bash
dockerb --help
```

Each command also has its own help page, for example `dockerb suggest --help`, `dockerb fix --help`, etc.

---


## Installation

**Requirements:** Python 3.10+ and a running Docker daemon.

**Recommended**:

```bash
uv tool install dockerbrain
```

**Or with pip:**

```bash
pip install dockerbrain           # Fast install (Monitor & Templates only)
pip install "dockerbrain[all]"    # Install all LLM SDKs
pip install "dockerbrain[openai]" # If you only use OpenAI/Ollama
```

Verify:

```bash
dockerb --version
```

### Configure an LLM Provider

```bash
dockerb init
```

This creates `.dockerbrainrc` in `~/.dockerbrain/`. Open it with `dockerb config` and set your key:

```ini
[llm]
provider = "choose_provider"
model    = "choose_model"
api_key  = "your_key_here"
```

| Provider | API Key | Link |
|---|:---:|---|
| Gemini | Required | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| ChatGPT | Required | [platform.openai.com](https://platform.openai.com/api-keys) |
| Claude | Required | [console.anthropic.com](https://console.anthropic.com/settings/keys) |
| Groq | Required | [console.groq.com/keys](https://console.groq.com/keys) |
| Ollama | Not Required | [ollama.com](https://ollama.com) |

> `monitor`, `template`, and `env` commands work without an API key.

---

## Pre-commit Hook

DockerBrain can run as a [pre-commit](https://pre-commit.com/) hook to lint Dockerfiles on every commit:

```yaml
# .pre-commit-config.yaml 
repos:
  - repo: https://github.com/iamPulakesh/DockerBrain
    rev: v1.3.0
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

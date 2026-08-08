<div align="center">

# DockerBrain

**A CLI tool for real-time container monitoring, log analysis, and optimization.**

[![PyPI Downloads](https://static.pepy.tech/personalized-badge/dockerbrain?period=total&units=INTERNATIONAL_SYSTEM&left_color=GRAY&right_color=RED&left_text=PyPI+downloads)](https://pepy.tech/projects/dockerbrain)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/dockerbrain)](https://pypi.org/project/dockerbrain/)

<p align="center">
  DockerBrain monitors your Docker containers in real time, detects resource issues, and uses LLMs to generate actionable optimizations for running containers and Dockerfiles all in one place.
</p>

---

</div>

## Features

| Feature | Command | LLM Required |
|---|---|:---:|
| Real-time container monitoring | `dockerb monitor` | No |
| AI optimization suggestions | `dockerb suggest` | Yes |
| Curated Dockerfile templates | `dockerb template` | No |
| Environment & config diagnostics | `dockerb env` | No |

---

## Usage

DockerBrain exposes all functionality through the terminal. Run the following to see all available commands and options:

```bash
dockerb --help
```

Each command also has its own help page, for example `dockerb suggest --help`, `dockerb template --help`, etc.

---


## Installation

**Requirements:** Python 3.10+ and a running Docker daemon.

**Recommended**:

```bash
uv tool install dockerbrain
```

**Or with pip:**

```bash
pip install dockerbrain           # Fast install (Without LLM SDKs)
pip install "dockerbrain[all]"    # Install all LLM SDKs
pip install "dockerbrain[provider_name]" # If you only use specified provider (e.g. 'openai', 'anthropic')
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
| ChatGPT | Required | [platform.openai.com](https://platform.openai.com/api-keys) |
| Claude | Required | [console.anthropic.com](https://console.anthropic.com/settings/keys) |

> Only `suggest` command need an API key to scan issues and suggest optimizations.

---



## Development

```bash
git clone https://github.com/iamPulakesh/DockerBrain.git
cd DockerBrain
uv tool install -e .

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

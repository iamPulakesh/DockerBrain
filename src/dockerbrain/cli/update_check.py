"""CLI update checker — moved from utils.py, CLI-startup-only concern."""

from __future__ import annotations


def check_for_updates() -> str | None:
    """Check PyPI for a newer version. Returns latest version string or None."""

    import json
    import time
    from urllib import request
    from pathlib import Path
    from dockerbrain import __version__

    cache_file = Path.home() / ".dockerbrain" / ".update_check.json"
    now = time.time()

    def parse_version(v: str) -> tuple:
        return tuple(
            int(x) if x.isdigit() else 0 for x in (v.split(".") + ["0", "0"])[:3]
        )

    if cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            if now - cache_data.get("last_check", 0) < 86400:
                latest_cached = cache_data.get("latest_version")
                if latest_cached and parse_version(latest_cached) > parse_version(
                    __version__
                ):
                    return latest_cached
                return None
        except Exception:
            pass

    try:
        req = request.Request("https://pypi.org/pypi/dockerbrain/json")
        with request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            latest = data["info"]["version"]

        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps({"last_check": now, "latest_version": latest}))

        if parse_version(latest) > parse_version(__version__):
            return latest
    except Exception:
        pass

    return None

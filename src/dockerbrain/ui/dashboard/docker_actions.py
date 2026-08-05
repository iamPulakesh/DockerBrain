from __future__ import annotations
import docker

class DockerActionService:
    """Service to handle Docker actions for the TUI."""
    def __init__(self, client: docker.DockerClient):
        self.client = client

    def stop_container(self, name: str) -> None:
        ctr = self.client.containers.get(name)
        ctr.stop()

    def pause_container(self, name: str, status: str) -> str:
        ctr = self.client.containers.get(name)
        if status == "running":
            ctr.pause()
            return f"Paused {name}"
        elif status == "paused":
            ctr.unpause()
            return f"Resumed {name}"
        elif status in ("exited", "created"):
            ctr.start()
            return f"Started {name}"
        return ""

    def restart_container(self, name: str) -> None:
        ctr = self.client.containers.get(name)
        ctr.restart()

    def remove_container(self, name: str) -> None:
        ctr = self.client.containers.get(name)
        ctr.remove(force=True)

    def fetch_logs(self, name: str, tail: int = 200) -> str:
        ctr = self.client.containers.get(name)
        return ctr.logs(tail=tail, timestamps=True).decode("utf-8", errors="replace")

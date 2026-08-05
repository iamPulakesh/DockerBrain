from __future__ import annotations

from dockerbrain.monitor.snapshot import ContainerSnapshot

def sort_snapshots(
    snaps: list[ContainerSnapshot], 
    sort_key: str, 
    sort_reverse: bool
) -> list[ContainerSnapshot]:
    """Sort a list of ContainerSnapshots based on a given key."""
    sort_map = {
        "name": lambda s: s.name.lower(),
        "cpu": lambda s: s.cpu_percent,
        "mem": lambda s: s.mem_usage_mb,
    }
    key_fn = sort_map.get(sort_key, sort_map["name"])
    return sorted(snaps, key=key_fn, reverse=sort_reverse)

from datetime import datetime, timezone, timedelta
from dockerbrain.docker_client.metrics import parse_container_stats


def test_parse_container_stats():
    raw = {
        "memory_stats": {
            "usage": 200 * 1024 * 1024,
            "limit": 500 * 1024 * 1024,
            "stats": {"cache": 50 * 1024 * 1024},
        },
        "networks": {
            "eth0": {
                "rx_bytes": 1000,
                "tx_bytes": 2000,
                "rx_packets": 10,
                "tx_packets": 20,
                "rx_errors": 1,
                "tx_errors": 2,
                "rx_dropped": 3,
                "tx_dropped": 4,
            },
            "eth1": {
                "rx_bytes": 500,
                "tx_bytes": 600,
                "rx_packets": 5,
                "tx_packets": 6,
                "rx_errors": 0,
                "tx_errors": 0,
                "rx_dropped": 0,
                "tx_dropped": 0,
            },
        },
    }

    started_dt = datetime.now(timezone.utc) - timedelta(seconds=100)
    started_at = started_dt.isoformat()

    parsed = parse_container_stats(raw, status="running", started_at=started_at)

    # Memory assertions
    # usage = 200MB, cache = 50MB, real_usage = 150MB
    assert parsed["mem_usage_mb"] == 150.0
    assert parsed["mem_limit_mb"] == 500.0
    assert parsed["mem_cache_mb"] == 50.0
    assert parsed["mem_percent"] == 30.0

    # Network assertions
    assert parsed["net_rx_bytes"] == 1500
    assert parsed["net_tx_bytes"] == 2600
    assert parsed["net_rx_packets"] == 15
    assert parsed["net_tx_packets"] == 26
    assert parsed["net_rx_errors"] == 1
    assert parsed["net_tx_errors"] == 2
    assert parsed["net_rx_dropped"] == 3
    assert parsed["net_tx_dropped"] == 4

    # Uptime assertions
    assert 99.0 <= parsed["uptime_seconds"] <= 101.0

def test_parse_container_stats_paused():
    parsed = parse_container_stats({}, status="paused", previous_paused_uptime=42.5)
    assert parsed["uptime_seconds"] == 42.5

def test_parse_container_stats_stopped():
    parsed = parse_container_stats({}, status="exited", started_at="invalid-date")
    assert parsed["uptime_seconds"] == 0.0

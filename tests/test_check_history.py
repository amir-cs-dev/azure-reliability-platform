from datetime import datetime, timezone

from monitor.storage import IncidentStore


def test_check_history_survives_store_recreation(tmp_path):
    path = tmp_path / "monitor.sqlite3"
    store = IncidentStore(path)
    check = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "healthy": True,
        "status_code": 200,
        "latency_ms": 9.75,
        "error": None,
    }
    store.record(check, threshold=2)
    fresh = IncidentStore(path)
    history = fresh.recent_checks()
    assert len(history) == 1
    assert history[0]["checked_at"] == check["timestamp"]
    assert history[0]["healthy"] == 1
    assert history[0]["latency_ms"] == 9.75

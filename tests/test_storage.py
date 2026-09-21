import pytest

from monitor.storage import IncidentStore


def result(healthy, timestamp):
    return {
        "healthy": healthy,
        "timestamp": timestamp,
        "status_code": 200 if healthy else None,
        "latency_ms": 10,
        "error": None,
    }


T0 = "2026-09-21T12:00:00+00:00"
T1 = "2026-09-21T12:00:03+00:00"
T2 = "2026-09-21T12:00:13+00:00"


def test_incident_survives_restart(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)

    store.record(result(False, T0))
    store.record(result(False, T1))

    restarted = IncidentStore(db)

    assert restarted.load_state()["incident_open"] is True
    assert len(restarted.list_incidents()) == 1


def test_failure_counter_survives_restart(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    first = IncidentStore(db)
    first.record(result(False, T0))

    restarted = IncidentStore(db)

    assert (
        restarted.load_state()["consecutive_failures"]
        == 1
    )

    state, event = restarted.record(result(False, T1))

    assert event == "INCIDENT_OPENED"
    assert state["consecutive_failures"] == 2


def test_duplicate_incident_prevention(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)

    store.record(result(False, T0))
    store.record(result(False, T1))

    restarted = IncidentStore(db)

    _, event = restarted.record(result(False, T2))

    assert event is None
    assert len(restarted.list_incidents()) == 1


def test_recovery_duration(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)

    store.record(result(False, T0))
    store.record(result(False, T1))

    restarted = IncidentStore(db)

    state, event = restarted.record(result(True, T2))

    incidents = restarted.list_incidents()

    assert event == "RECOVERED"
    assert state["incident_open"] is False
    assert len(incidents) == 1

    incident = incidents[0]

    assert incident["opened_at"] == T1
    assert incident["recovered_at"] == T2
    assert incident["duration_seconds"] == 10.0


def test_invalid_threshold_rolls_back(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)
    before = store.load_state()

    with pytest.raises(ValueError):
        store.record(result(False, T0), threshold=0)

    assert store.load_state() == before
    assert store.list_incidents() == []
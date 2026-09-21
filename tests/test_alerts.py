import json

import pytest

from monitor.storage import IncidentStore


T0 = "2026-09-21T12:00:00+00:00"
T1 = "2026-09-21T12:00:03+00:00"
T2 = "2026-09-21T12:00:13+00:00"


def result(healthy, timestamp):
    return {
        "healthy": healthy,
        "timestamp": timestamp,
        "status_code": 200 if healthy else None,
        "latency_ms": 10,
        "error": None,
    }


def open_incident(store):
    store.record(result(False, T0))
    store.record(result(False, T1))


def test_alert_survives_restart(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)
    open_incident(store)

    restarted = IncidentStore(db)
    alerts = restarted.pending_notifications()

    assert len(alerts) == 1
    assert alerts[0]["event"] == "INCIDENT_OPENED"
    assert alerts[0]["status"] == "pending"

    payload = json.loads(alerts[0]["payload"])

    assert payload["incident_id"] == 1
    assert payload["event"] == "INCIDENT_OPENED"


def test_recovery_and_no_duplicate_alerts(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)

    open_incident(store)

    # Additional failure must not generate a duplicate.
    store.record(result(False, T2))

    # Recovery generates the second notification.
    store.record(result(True, T2))

    alerts = store.pending_notifications()

    assert len(alerts) == 2
    assert alerts[0]["event"] == "INCIDENT_OPENED"
    assert alerts[1]["event"] == "RECOVERED"

    assert (
        alerts[0]["incident_id"]
        == alerts[1]["incident_id"]
    )

    recovery_payload = json.loads(alerts[1]["payload"])

    assert recovery_payload["duration_seconds"] == 10.0


def test_failed_delivery_survives_restart(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)
    open_incident(store)

    notification = store.pending_notifications()[0]

    success = store.mark_failed(
        notification["id"],
        "Webhook temporarily unavailable",
    )

    assert success is True

    restarted = IncidentStore(db)
    pending = restarted.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["status"] == "pending"
    assert pending[0]["attempts"] == 1

    assert (
        pending[0]["last_error"]
        == "Webhook temporarily unavailable"
    )


def test_successful_delivery_is_idempotent(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)
    open_incident(store)

    notification = store.pending_notifications()[0]
    notification_id = notification["id"]

    first = store.mark_delivered(notification_id)
    second = store.mark_delivered(notification_id)

    assert first is True
    assert second is False

    assert store.pending_notifications() == []

    with store.connect() as conn:
        delivered = conn.execute("""
            SELECT status, attempts, delivered_at
            FROM notifications
            WHERE id = ?
        """, (notification_id,)).fetchone()

    assert delivered["status"] == "delivered"
    assert delivered["attempts"] == 1
    assert delivered["delivered_at"] is not None


def test_failed_recovery_rolls_back(tmp_path):
    db = tmp_path / "incidents.sqlite3"

    store = IncidentStore(db)
    open_incident(store)

    before = store.load_state()

    # Invalid recovery timestamp must cause rollback.
    with pytest.raises(ValueError):
        store.record(
            result(True, "invalid-timestamp")
        )

    assert store.load_state() == before

    incidents = store.list_incidents()
    alerts = store.pending_notifications()

    assert len(incidents) == 1
    assert incidents[0]["recovered_at"] is None

    assert len(alerts) == 1
    assert alerts[0]["event"] == "INCIDENT_OPENED"
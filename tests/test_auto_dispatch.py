import json

from monitor import alerts, runner
from monitor.alerts import reset_exhausted
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


class FakeResponse:
    def getcode(self):
        return 200

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_monitor_dispatches_open_and_recovery(
    tmp_path,
    monkeypatch,
):
    db = tmp_path / "auto.sqlite3"

    results = iter([
        result(False, T0),
        result(False, T1),
        result(True, T2),
    ])

    received = []

    def fake_opener(request, timeout):
        received.append(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(
        runner,
        "check_health",
        lambda: next(results),
    )

    monkeypatch.setattr(
        alerts,
        "urlopen",
        fake_opener,
    )

    monkeypatch.setattr(
        runner.time,
        "sleep",
        lambda seconds: None,
    )

    runner.run_monitor(
        interval=0.01,
        count=3,
        db_path=db,
        webhook_url="http://127.0.0.1:8765/webhook",
    )

    assert [item["event"] for item in received] == [
        "INCIDENT_OPENED",
        "RECOVERED",
    ]

    assert received[0]["incident_id"] == (
        received[1]["incident_id"]
    )

    store = IncidentStore(db)

    assert store.pending_notifications() == []

    with store.connect() as conn:
        rows = conn.execute("""
            SELECT status, attempts
            FROM notifications
            ORDER BY id
        """).fetchall()

    assert len(rows) == 2
    assert all(row["status"] == "delivered" for row in rows)
    assert all(row["attempts"] == 1 for row in rows)


def test_monitor_dispatches_pending_on_restart(
    tmp_path,
    monkeypatch,
):
    db = tmp_path / "restart.sqlite3"

    store = IncidentStore(db)

    store.record(result(False, T0))
    store.record(result(False, T1))

    received = []

    def fake_opener(request, timeout):
        received.append(json.loads(request.data))
        return FakeResponse()

    monkeypatch.setattr(
        alerts,
        "urlopen",
        fake_opener,
    )

    monkeypatch.setattr(
        runner,
        "check_health",
        lambda: result(True, T2),
    )

    runner.run_monitor(
        interval=0.01,
        count=1,
        db_path=db,
        webhook_url="http://127.0.0.1:8765/webhook",
    )

    assert [item["event"] for item in received] == [
        "INCIDENT_OPENED",
        "RECOVERED",
    ]

    assert IncidentStore(db).pending_notifications() == []


def test_exhausted_notification_can_be_reset(
    tmp_path,
):
    db = tmp_path / "recovery.sqlite3"

    store = IncidentStore(db)

    store.record(result(False, T0))
    store.record(result(False, T1))

    notification = store.pending_notifications()[0]

    for _ in range(3):
        store.mark_failed(
            notification["id"],
            "Receiver unavailable",
        )

    restarted = IncidentStore(db)

    restored = reset_exhausted(restarted)

    assert restored == 1

    pending = restarted.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["attempts"] == 0
    assert pending[0]["last_error"] is None

    # Incident history was preserved.
    assert len(restarted.list_incidents()) == 1
    assert restarted.load_state()["incident_open"] is True
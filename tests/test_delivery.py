import json
from urllib.error import URLError

import pytest

from monitor.alerts import deliver_pending
from monitor.storage import IncidentStore


URL = "https://alerts.example.test/webhook"

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


class FakeResponse:
    def __init__(self, status=200):
        self.status = status

    def getcode(self):
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_successful_webhook_delivery(tmp_path):
    store = IncidentStore(tmp_path / "test.sqlite3")
    open_incident(store)

    requests = []

    def fake_opener(request, timeout):
        requests.append(request)
        assert timeout == 5
        return FakeResponse(200)

    summary = deliver_pending(
        store,
        URL,
        opener=fake_opener,
        sleeper=lambda seconds: None,
    )

    assert summary["delivered"] == 1
    assert store.pending_notifications() == []
    assert len(requests) == 1

    request = requests[0]

    assert request.get_method() == "POST"

    payload = json.loads(request.data)

    assert payload["event"] == "INCIDENT_OPENED"

    headers = {
        key.lower(): value
        for key, value in request.header_items()
    }

    assert headers["x-idempotency-key"] == (
        "incident-1-INCIDENT_OPENED"
    )


def test_retry_after_temporary_failure(tmp_path):
    store = IncidentStore(tmp_path / "test.sqlite3")
    open_incident(store)

    attempts = []
    delays = []

    def fake_opener(request, timeout):
        attempts.append(request)

        if len(attempts) == 1:
            raise URLError("Temporary outage")

        return FakeResponse(200)

    summary = deliver_pending(
        store,
        URL,
        opener=fake_opener,
        sleeper=delays.append,
    )

    assert len(attempts) == 2
    assert delays == [1]
    assert summary["delivered"] == 1
    assert store.pending_notifications() == []

    with store.connect() as conn:
        row = conn.execute("""
            SELECT status, attempts
            FROM notifications
        """).fetchone()

    assert row["status"] == "delivered"
    assert row["attempts"] == 2


def test_exhausted_delivery_survives_restart(tmp_path):
    db = tmp_path / "test.sqlite3"

    store = IncidentStore(db)
    open_incident(store)

    calls = []

    def failing_opener(request, timeout):
        calls.append(request)
        raise URLError("Receiver unavailable")

    summary = deliver_pending(
        store,
        URL,
        opener=failing_opener,
        sleeper=lambda seconds: None,
    )

    assert summary["exhausted"] == 1
    assert len(calls) == 3

    restarted = IncidentStore(db)

    second = deliver_pending(
        restarted,
        URL,
        opener=failing_opener,
        sleeper=lambda seconds: None,
    )

    assert second["exhausted"] == 1
    assert len(calls) == 3

    pending = restarted.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["attempts"] == 3


def test_opening_and_recovery_delivery(tmp_path):
    store = IncidentStore(tmp_path / "test.sqlite3")

    open_incident(store)
    store.record(result(True, T2))

    payloads = []

    def fake_opener(request, timeout):
        payloads.append(json.loads(request.data))
        return FakeResponse(204)

    summary = deliver_pending(
        store,
        URL,
        opener=fake_opener,
        sleeper=lambda seconds: None,
    )

    assert summary["delivered"] == 2

    assert [item["event"] for item in payloads] == [
        "INCIDENT_OPENED",
        "RECOVERED",
    ]

    assert store.pending_notifications() == []


def test_rejects_insecure_external_webhook(tmp_path):
    store = IncidentStore(tmp_path / "test.sqlite3")
    open_incident(store)

    with pytest.raises(ValueError):
        deliver_pending(
            store,
            "http://example.com/webhook",
        )

    assert len(store.pending_notifications()) == 1
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from psycopg.conninfo import make_conninfo

from monitor.postgres_storage import PostgresIncidentStore
from monitor.state import evaluate as evaluate_state


@pytest.fixture
def store():
    database_url = os.environ.get("PG_TEST_DATABASE_URL")

    if not database_url:
        pytest.fail("PG_TEST_DATABASE_URL is required")

    instance = PostgresIncidentStore(database_url)

    # This test is exclusively for the disposable local database.
    with instance.connect() as conn:
        database_name = conn.execute(
            "SELECT current_database() AS name"
        ).fetchone()["name"]

        assert database_name == "arp_test", (
            "Refusing to reset a non-test database"
        )

        conn.execute("""
            TRUNCATE TABLE check_results, notifications, incidents
            RESTART IDENTITY CASCADE
        """)

        conn.execute("""
            UPDATE monitor_state
            SET consecutive_failures = 0,
                incident_open = 0
            WHERE id = 1
        """)

    return instance


def test_postgres_incident_lifecycle(store):
    start = datetime(
        2026, 9, 21, 12, 0,
        tzinfo=timezone.utc,
    )

    def result(healthy, seconds):
        return {
            "timestamp": (
                start + timedelta(seconds=seconds)
            ).isoformat(),
            "healthy": healthy,
            "status_code": 200 if healthy else 500,
            "latency_ms": 25.0,
            "error": None if healthy else "HTTP 500",
        }

    # 1. Initial state.
    assert store.load_state() == {
        "consecutive_failures": 0,
        "incident_open": False,
    }

    # 2. First failure: threshold not reached.
    state, event = store.record(
        result(False, 0),
        threshold=2,
    )

    assert event is None
    assert state["consecutive_failures"] == 1
    assert store.list_incidents() == []

    # 3. Force failure AFTER incident insertion.
    # The transaction must roll back completely.
    with patch(
        "monitor.postgres_storage.json.dumps",
        side_effect=RuntimeError("Injected failure"),
    ):
        with pytest.raises(
            RuntimeError,
            match="Injected failure",
        ):
            store.record(
                result(False, 10),
                threshold=2,
            )

    assert store.load_state() == {
        "consecutive_failures": 1,
        "incident_open": False,
    }

    assert store.list_incidents() == []
    assert store.pending_notifications() == []

    print("PASS: Transaction rollback")

    # 4. Second failure: incident opens.
    state, event = store.record(
        result(False, 10),
        threshold=2,
    )

    assert event == "INCIDENT_OPENED"
    assert state["incident_open"] is True

    incidents = store.list_incidents()

    assert len(incidents) == 1
    assert incidents[0]["recovered_at"] is None

    pending = store.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["event"] == "INCIDENT_OPENED"

    print("PASS: Incident creation and outbox")

    # 5. Simulate monitor process replacement.
    restored = PostgresIncidentStore(
        os.environ["PG_TEST_DATABASE_URL"]
    )

    assert restored.load_state()["incident_open"] is True
    assert len(restored.list_incidents()) == 1
    assert len(restored.pending_notifications()) == 1

    print("PASS: State restored from new connection")

    # 6. Failed notification delivery is recorded.
    notification_id = pending[0]["id"]

    assert restored.mark_failed(
        notification_id,
        "Simulated webhook outage",
    )

    pending = restored.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["attempts"] == 1
    assert "Simulated webhook outage" in (
        pending[0]["last_error"]
    )

    print("PASS: Failed-delivery tracking")

    # 7. Simulate successful retry.
    assert restored.mark_delivered(notification_id)

    assert restored.pending_notifications() == []

    with restored.connect() as conn:
        delivered = conn.execute("""
            SELECT status, attempts, delivered_at
            FROM notifications
            WHERE id = %s
        """, (notification_id,)).fetchone()

    assert delivered["status"] == "delivered"
    assert delivered["attempts"] == 2
    assert delivered["delivered_at"] is not None

    print("PASS: Notification retry and delivery state")

    # 8. Recover the application.
    state, event = restored.record(
        result(True, 70),
        threshold=2,
    )

    assert event == "RECOVERED"
    assert state == {
        "consecutive_failures": 0,
        "incident_open": False,
    }

    incidents = restored.list_incidents()

    assert len(incidents) == 1
    assert incidents[0]["recovered_at"] is not None
    assert incidents[0]["duration_seconds"] == pytest.approx(
        60.0
    )

    pending = restored.pending_notifications()

    assert len(pending) == 1
    assert pending[0]["event"] == "RECOVERED"

    print("PASS: Incident recovery and notification")

    # 9. Verify persisted state from another connection.
    final_store = PostgresIncidentStore(
        os.environ["PG_TEST_DATABASE_URL"]
    )

    assert final_store.load_state() == {
        "consecutive_failures": 0,
        "incident_open": False,
    }

    assert len(final_store.list_incidents()) == 1
    assert len(final_store.pending_notifications()) == 1

    print("PASS: Persistence across connections")


def test_overlapping_checks_open_one_incident(store):
    start = datetime(
        2026, 9, 21, 12, 0,
        tzinfo=timezone.utc,
    )

    def failure(seconds):
        return {
            "timestamp": (
                start + timedelta(seconds=seconds)
            ).isoformat(),
            "healthy": False,
            "status_code": 500,
            "latency_ms": 25.0,
            "error": "HTTP 500",
        }

    # Put both overlapping calls at the incident-opening boundary.
    store.record(failure(0), threshold=2)

    database_url = os.environ["PG_TEST_DATABASE_URL"]
    first_store = PostgresIncidentStore(make_conninfo(
        database_url,
        application_name="phase5_first_check",
    ))
    second_store = PostgresIncidentStore(make_conninfo(
        database_url,
        application_name="phase5_second_check",
    ))

    first_evaluation_started = threading.Event()
    release_first_evaluation = threading.Event()
    first_timestamp = failure(10)["timestamp"]

    def hold_first_transaction(state, result, threshold):
        if result["timestamp"] == first_timestamp:
            first_evaluation_started.set()
            if not release_first_evaluation.wait(timeout=5):
                raise AssertionError(
                    "Timed out holding the first transaction"
                )

        return evaluate_state(state, result, threshold)

    def wait_until_second_is_blocked():
        deadline = time.monotonic() + 5

        while time.monotonic() < deadline:
            with store.connect() as conn:
                waiting = conn.execute("""
                    SELECT wait_event
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND application_name =
                          'phase5_second_check'
                      AND wait_event_type = 'Lock'
                """).fetchone()

            if waiting is not None:
                return waiting["wait_event"]

            time.sleep(0.01)

        raise AssertionError(
            "Second check never overlapped on the state lock"
        )

    with patch(
        "monitor.postgres_storage.evaluate",
        side_effect=hold_first_transaction,
    ):
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(
                first_store.record,
                failure(10),
                2,
            )

            assert first_evaluation_started.wait(timeout=5)

            second = executor.submit(
                second_store.record,
                failure(11),
                2,
            )

            try:
                blocked_on = wait_until_second_is_blocked()
            finally:
                release_first_evaluation.set()

            first_result = first.result(timeout=5)
            second_result = second.result(timeout=5)

    assert blocked_on is not None
    assert [first_result[1], second_result[1]] == [
        "INCIDENT_OPENED",
        None,
    ]
    assert store.load_state() == {
        "consecutive_failures": 3,
        "incident_open": True,
    }

    incidents = store.list_incidents()
    notifications = store.pending_notifications()

    assert len(incidents) == 1
    assert incidents[0]["opened_at"] == first_timestamp
    assert len(notifications) == 1
    assert notifications[0]["incident_id"] == incidents[0]["id"]
    assert notifications[0]["event"] == "INCIDENT_OPENED"


def test_check_history_is_persistent(store):
    result = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "healthy": True,
        "status_code": 200,
        "latency_ms": 12.5,
        "error": None,
    }
    store.record(result, threshold=2)
    fresh = PostgresIncidentStore(os.environ["PG_TEST_DATABASE_URL"])
    checks = fresh.recent_checks()
    assert len(checks) == 1
    assert checks[0]["checked_at"] == result["timestamp"]
    assert checks[0]["healthy"] == 1
    assert checks[0]["latency_ms"] == 12.5

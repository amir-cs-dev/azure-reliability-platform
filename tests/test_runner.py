from unittest.mock import Mock

from monitor import runner
from monitor.runner import evaluate


def initial_state():
    return {
        "consecutive_failures": 0,
        "incident_open": False,
    }


def health(healthy):
    return {"healthy": healthy}


def test_transient_failure():
    state, event = evaluate(initial_state(), health(False))

    assert state["consecutive_failures"] == 1
    assert state["incident_open"] is False
    assert event is None


def test_incident_opens_after_two_failures():
    state, _ = evaluate(initial_state(), health(False))
    state, event = evaluate(state, health(False))

    assert state["incident_open"] is True
    assert event == "INCIDENT_OPENED"


def test_no_duplicate_incidents():
    state, _ = evaluate(initial_state(), health(False))
    state, _ = evaluate(state, health(False))
    state, event = evaluate(state, health(False))

    assert state["incident_open"] is True
    assert event is None


def test_recovery():
    state, _ = evaluate(initial_state(), health(False))
    state, _ = evaluate(state, health(False))
    state, event = evaluate(state, health(True))

    assert event == "RECOVERED"
    assert state == initial_state()


def test_transient_failure_resets():
    state, _ = evaluate(initial_state(), health(False))
    state, event = evaluate(state, health(True))

    assert state == initial_state()
    assert event is None


def test_new_incident_after_recovery():
    state = initial_state()

    for value in [False, False, True, False]:
        state, _ = evaluate(state, health(value))

    state, event = evaluate(state, health(False))

    assert event == "INCIDENT_OPENED"


def test_invalid_threshold():
    import pytest

    with pytest.raises(ValueError):
        evaluate(initial_state(), health(False), threshold=0)


def test_run_monitor_once_uses_checker_store_and_delivery(monkeypatch):
    result = {
        "timestamp": "2026-10-04T12:00:00+00:00",
        "healthy": True,
        "status_code": 200,
        "latency_ms": 4.5,
        "error": None,
    }
    store = Mock()
    store.record.return_value = (initial_state(), None)
    checker = Mock(return_value=result)
    dispatch = Mock(return_value={"delivered": 0})

    monkeypatch.setattr(runner, "check_health", checker)
    monkeypatch.setattr(runner, "dispatch_alerts", dispatch)

    cycle = runner.run_monitor_once(
        store=store,
        threshold=3,
        target_url="https://api.example.invalid/health",
        webhook_url="https://hooks.example.invalid/notify",
    )

    checker.assert_called_once_with(
        "https://api.example.invalid/health",
    )
    store.record.assert_called_once_with(result, 3)
    dispatch.assert_called_once_with(
        store,
        "https://hooks.example.invalid/notify",
    )
    assert cycle["result"] == result
    assert cycle["state"] == initial_state()

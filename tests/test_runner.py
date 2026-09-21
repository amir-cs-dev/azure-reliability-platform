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
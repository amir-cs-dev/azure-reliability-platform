import json
from unittest.mock import Mock

import pytest

from azure_function import function_app
from monitor import runner


SETTINGS = {
    "TARGET_URL": "https://api.example.invalid/health",
    "DATABASE_URL": "postgresql://example.invalid/database",
    "WEBHOOK_URL": "https://hooks.example.invalid/notify",
    "FAILURE_THRESHOLD": "3",
}


def successful_cycle():
    return {
        "result": {
            "timestamp": "2026-10-04T12:00:00+00:00",
            "healthy": True,
            "status_code": 200,
            "latency_ms": 12.5,
            "error": None,
        },
        "state": {
            "consecutive_failures": 0,
            "incident_open": False,
        },
        "event": None,
        "delivery": None,
    }


def test_timer_invocation_uses_shared_monitor_path():
    timer = Mock(past_due=False)
    store = object()
    store_factory = Mock(return_value=store)
    monitor_once = Mock(return_value=successful_cycle())
    event_logger = Mock()

    cycle = function_app.execute_timer(
        timer,
        settings=SETTINGS,
        store_factory=store_factory,
        monitor_once=monitor_once,
        event_logger=event_logger,
    )

    store_factory.assert_called_once_with(
        database_url=SETTINGS["DATABASE_URL"],
    )
    monitor_once.assert_called_once_with(
        store=store,
        threshold=3,
        target_url=SETTINGS["TARGET_URL"],
        webhook_url=SETTINGS["WEBHOOK_URL"],
    )
    assert cycle == successful_cycle()

    events = [
        json.loads(call.args[0])["event"]
        for call in event_logger.info.call_args_list
    ]
    assert events == [
        "scheduled_monitor_started",
        "scheduled_monitor_completed",
    ]


def test_function_imports_reusable_monitor_logic():
    assert function_app.run_monitor_once is runner.run_monitor_once
    assert "check_health" not in function_app.__dict__


def test_timer_trigger_has_authoritative_schedule_settings():
    functions = function_app.app.get_functions()

    assert len(functions) == 1
    assert functions[0].get_function_name() == "scheduled_monitor"

    binding = functions[0].get_bindings()[0]
    assert binding.type == "timerTrigger"
    assert binding.schedule == "%MONITOR_SCHEDULE%"
    assert binding.run_on_startup is False
    assert binding.use_monitor is True


@pytest.mark.parametrize(
    "settings",
    [
        {**SETTINGS, "TARGET_URL": ""},
        {**SETTINGS, "DATABASE_URL": ""},
        {**SETTINGS, "FAILURE_THRESHOLD": "invalid"},
        {**SETTINGS, "FAILURE_THRESHOLD": "0"},
    ],
)
def test_invalid_configuration_fails_without_running(settings):
    monitor_once = Mock()
    event_logger = Mock()

    with pytest.raises(
        RuntimeError,
        match="scheduled monitor execution failed",
    ):
        function_app.execute_timer(
            Mock(past_due=False),
            settings=settings,
            monitor_once=monitor_once,
            event_logger=event_logger,
        )

    monitor_once.assert_not_called()
    failure = json.loads(event_logger.error.call_args.args[0])
    assert failure["event"] == "scheduled_monitor_failed"
    assert failure["error_type"] == "ValueError"


def test_execution_error_is_logged_without_secret_values():
    event_logger = Mock()

    with pytest.raises(
        RuntimeError,
        match="scheduled monitor execution failed",
    ):
        function_app.execute_timer(
            Mock(past_due=True),
            settings=SETTINGS,
            store_factory=Mock(
                side_effect=ConnectionError("sensitive detail"),
            ),
            event_logger=event_logger,
        )

    failure_text = event_logger.error.call_args.args[0]
    failure = json.loads(failure_text)
    assert failure["error_type"] == "ConnectionError"
    assert "sensitive detail" not in failure_text
    assert SETTINGS["DATABASE_URL"] not in failure_text
    assert SETTINGS["WEBHOOK_URL"] not in failure_text

import json
import logging
import os
from datetime import datetime, timezone
from urllib.parse import urlsplit

import azure.functions as func

from monitor.runner import create_store, run_monitor_once


SCHEDULE_SETTING = "%MONITOR_SCHEDULE%"
app = func.FunctionApp()
logger = logging.getLogger("arp.scheduled_monitor")


def _required_setting(settings, name):
    value = settings.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def _threshold(settings):
    try:
        value = int(settings.get("FAILURE_THRESHOLD", "2"))
    except ValueError as exc:
        raise ValueError(
            "FAILURE_THRESHOLD must be an integer"
        ) from exc

    if value < 1:
        raise ValueError(
            "FAILURE_THRESHOLD must be at least 1"
        )

    return value


def _safe_target(url):
    parsed = urlsplit(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def execute_timer(
    timer,
    *,
    settings=None,
    store_factory=create_store,
    monitor_once=run_monitor_once,
    event_logger=logger,
):
    """Execute one scheduled monitor cycle using shared monitor modules."""

    settings = os.environ if settings is None else settings

    try:
        target_url = _required_setting(settings, "TARGET_URL")
        database_url = _required_setting(settings, "DATABASE_URL")
        threshold = _threshold(settings)
        webhook_url = settings.get("WEBHOOK_URL") or None

        event_logger.info(json.dumps({
            "event": "scheduled_monitor_started",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "past_due": bool(getattr(timer, "past_due", False)),
            "target": _safe_target(target_url),
        }, sort_keys=True))

        store = store_factory(database_url=database_url)
        cycle = monitor_once(
            store=store,
            threshold=threshold,
            target_url=target_url,
            webhook_url=webhook_url,
        )

        result = cycle["result"]
        state = cycle["state"]

        event_logger.info(json.dumps({
            "event": "scheduled_monitor_completed",
            "timestamp": result["timestamp"],
            "healthy": result["healthy"],
            "status_code": result["status_code"],
            "latency_ms": result["latency_ms"],
            "consecutive_failures": state[
                "consecutive_failures"
            ],
            "lifecycle_event": cycle["event"],
            "persistence": "succeeded",
        }, sort_keys=True))

        return cycle

    except Exception as exc:
        event_logger.error(json.dumps({
            "event": "scheduled_monitor_failed",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": type(exc).__name__,
        }, sort_keys=True))
        raise RuntimeError(
            "scheduled monitor execution failed"
        ) from None


@app.timer_trigger(
    schedule=SCHEDULE_SETTING,
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def scheduled_monitor(timer: func.TimerRequest) -> None:
    execute_timer(timer)

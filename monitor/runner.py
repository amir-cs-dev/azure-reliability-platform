import argparse
import os
import time

from monitor.alerts import deliver_pending
from monitor.checker import check_health
from monitor.state import evaluate
from monitor.storage import IncidentStore


def create_store(db_path="data/incidents.sqlite3", database_url=None):
    """
    Select the persistence backend.

    PostgreSQL is used when DATABASE_URL is configured.
    SQLite remains the default for local development and tests.
    """
    if database_url is None:
        database_url = os.environ.get("DATABASE_URL")

    if database_url:
        from monitor.postgres_storage import PostgresIncidentStore

        return PostgresIncidentStore(database_url)

    return IncidentStore(db_path)


def dispatch_alerts(store, webhook_url):
    """Attempt delivery without stopping health monitoring."""

    if not webhook_url:
        return None

    try:
        summary = deliver_pending(store, webhook_url)

        if any(summary.values()):
            print(
                f"ALERT DELIVERY: {summary}",
                flush=True,
            )

        return summary

    except Exception as exc:
        print(
            f"ALERT DELIVERY ERROR: {exc}",
            flush=True,
        )
        return None


def run_monitor_once(
    store,
    threshold=2,
    target_url=None,
    webhook_url=None,
):
    """Run one check through the shared persistence and alert path."""

    if threshold < 1:
        raise ValueError("threshold must be at least 1")

    if target_url is None:
        result = check_health()
    else:
        result = check_health(target_url)

    state, event = store.record(
        result,
        threshold,
    )

    delivery = dispatch_alerts(store, webhook_url)

    return {
        "result": result,
        "state": state,
        "event": event,
        "delivery": delivery,
    }


def run_monitor(
    interval=10,
    threshold=2,
    count=None,
    db_path="data/incidents.sqlite3",
    webhook_url=None,
    database_url=None,
):
    """
    Execute health monitoring with persistent incident tracking.

    Storage:
        DATABASE_URL configured -> PostgreSQL
        Otherwise               -> SQLite

    Monitoring continues when webhook delivery fails.
    """

    if interval <= 0:
        raise ValueError("interval must be positive")

    if threshold < 1:
        raise ValueError("threshold must be at least 1")

    if count is not None and count < 1:
        raise ValueError("count must be positive")

    # Initialize storage before attempting to restore state.
    store = create_store(
        db_path=db_path,
        database_url=database_url,
    )

    if webhook_url is None:
        webhook_url = os.environ.get("WEBHOOK_URL")

    state = store.load_state()

    print(
        f"Restored state: {state}",
        flush=True,
    )

    if webhook_url:
        print(
            "Automatic alert delivery enabled.",
            flush=True,
        )
    else:
        print(
            "No WEBHOOK_URL configured. "
            "Notifications will remain queued.",
            flush=True,
        )

    # Recover eligible notifications from previous runs.
    dispatch_alerts(store, webhook_url)

    checks = 0

    try:
        while count is None or checks < count:
            cycle = run_monitor_once(
                store=store,
                threshold=threshold,
                webhook_url=webhook_url,
            )

            result = cycle["result"]
            state = cycle["state"]
            event = cycle["event"]

            checks += 1

            print(
                f"{result['timestamp']} | "
                f"healthy={result['healthy']} | "
                f"latency={result['latency_ms']}ms | "
                f"failures={state['consecutive_failures']}",
                flush=True,
            )

            if event:
                print(
                    f"EVENT: {event}",
                    flush=True,
                )

            if count is None or checks < count:
                time.sleep(interval)

    except KeyboardInterrupt:
        print(
            "\nMonitoring stopped.",
            flush=True,
        )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="Persistent health monitoring"
    )

    parser.add_argument(
        "--interval",
        type=float,
        default=10,
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=2,
    )

    parser.add_argument(
        "--count",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--db",
        default="data/incidents.sqlite3",
        help="SQLite database path when DATABASE_URL is not set.",
    )

    args = parser.parse_args()

    if args.interval <= 0 or args.threshold < 1:
        parser.error(
            "interval must be positive and threshold >= 1"
        )

    if args.count is not None and args.count < 1:
        parser.error("count must be positive")

    run_monitor(
        interval=args.interval,
        threshold=args.threshold,
        count=args.count,
        db_path=args.db,
    )

import argparse
import time

from monitor.checker import check_health
from monitor.state import evaluate


def run_monitor(
    interval=10,
    threshold=2,
    count=None,
    db_path="data/incidents.sqlite3",
):
    # Import here so existing state-machine tests remain compatible.
    from monitor.storage import IncidentStore

    store = IncidentStore(db_path)
    state = store.load_state()

    print(
        f"Restored state: {state}",
        flush=True,
    )

    checks = 0

    try:
        while count is None or checks < count:
            result = check_health()

            state, event = store.record(
                result,
                threshold,
            )

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
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

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
import argparse
import time

from monitor.checker import check_health


def evaluate(state, result, threshold=2):
    """Evaluate one health result and update incident state."""
    if threshold < 1:
        raise ValueError("threshold must be at least 1")

    new_state = state.copy()

    if result["healthy"]:
        new_state["consecutive_failures"] = 0

        if new_state["incident_open"]:
            new_state["incident_open"] = False
            return new_state, "RECOVERED"

        return new_state, None

    new_state["consecutive_failures"] += 1

    if (
        new_state["consecutive_failures"] >= threshold
        and not new_state["incident_open"]
    ):
        new_state["incident_open"] = True
        return new_state, "INCIDENT_OPENED"

    return new_state, None


def run_monitor(interval=10, threshold=2, count=None):
    state = {
        "consecutive_failures": 0,
        "incident_open": False,
    }

    checks = 0

    try:
        while count is None or checks < count:
            result = check_health()
            state, event = evaluate(state, result, threshold)
            checks += 1

            print(
                f"{result['timestamp']} | "
                f"healthy={result['healthy']} | "
                f"latency={result['latency_ms']}ms | "
                f"failures={state['consecutive_failures']}",
                flush=True,
            )

            if event:
                print(f"EVENT: {event}", flush=True)

            if count is None or checks < count:
                time.sleep(interval)

    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--threshold", type=int, default=2)
    parser.add_argument("--count", type=int, default=None)

    args = parser.parse_args()

    if args.interval <= 0 or args.threshold < 1:
        parser.error("interval must be positive and threshold >= 1")

    if args.count is not None and args.count < 1:
        parser.error("count must be positive")

    run_monitor(args.interval, args.threshold, args.count)
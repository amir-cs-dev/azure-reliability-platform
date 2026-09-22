import argparse
import json
import os
import time

from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from monitor.storage import IncidentStore


def validate_webhook_url(url):
    parsed = urlsplit(url)

    if parsed.scheme == "https" and parsed.hostname:
        return

    if (
        parsed.scheme == "http"
        and parsed.hostname in (
            "localhost",
            "127.0.0.1",
            "::1",
        )
    ):
        return

    raise ValueError(
        "Webhook must use HTTPS, except for local testing."
    )


def deliver_pending(
    store,
    webhook_url,
    max_attempts=3,
    timeout=5,
    opener=None,
    sleeper=None,
):
    validate_webhook_url(webhook_url)

    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    if timeout <= 0:
        raise ValueError("timeout must be positive")

    if opener is None:
        opener = urlopen

    if sleeper is None:
        sleeper = time.sleep

    summary = {
        "delivered": 0,
        "failed": 0,
        "exhausted": 0,
    }

    for notification in store.pending_notifications():

        notification_id = notification["id"]
        attempts = notification["attempts"]

        if attempts >= max_attempts:
            summary["exhausted"] += 1
            continue

        idempotency_key = (
            f"incident-{notification['incident_id']}-"
            f"{notification['event']}"
        )

        payload = notification["payload"].encode("utf-8")

        parsed_url = urlsplit(webhook_url)
        if (
            parsed_url.hostname in ("discord.com", "discordapp.com")
            and parsed_url.path.startswith("/api/webhooks/")
        ):
            message = (
                "Azure Reliability Platform alert\n"
                + notification["payload"][:1800]
            )
            payload = json.dumps(
                {"content": message},
                ensure_ascii=False,
            ).encode("utf-8")

        request = Request(
            webhook_url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "X-Idempotency-Key": idempotency_key,
            },
            method="POST",
        )

        while attempts < max_attempts:

            try:
                with opener(
                    request,
                    timeout=timeout,
                ) as response:

                    status = response.getcode()

                    if not 200 <= status < 300:
                        raise OSError(
                            f"Webhook returned HTTP {status}"
                        )

                if store.mark_delivered(notification_id):
                    summary["delivered"] += 1

                break

            except (
                URLError,
                OSError,
                TimeoutError,
            ) as exc:

                store.mark_failed(
                    notification_id,
                    exc,
                )

                attempts += 1

                if attempts >= max_attempts:
                    summary["exhausted"] += 1
                    break

                sleeper(2 ** (attempts - 1))

    return summary


def reset_exhausted(store, max_attempts=3):
    """
    Explicit operator recovery.

    Resets the attempt counters of exhausted pending
    notifications. Does not delete notifications or
    change incident history.
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")

    with store.connect() as conn:
        cursor = conn.execute("""
            UPDATE notifications
            SET attempts = 0,
                last_error = NULL
            WHERE status = 'pending'
              AND attempts >= ?
        """, (max_attempts,))

        return cursor.rowcount


def main():
    parser = argparse.ArgumentParser(
        description="Deliver queued incident notifications"
    )

    parser.add_argument(
        "--db",
        default="data/incidents.sqlite3",
    )

    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
    )

    parser.add_argument(
        "--retry-exhausted",
        action="store_true",
        help="Reset exhausted pending notifications and retry",
    )

    args = parser.parse_args()

    webhook_url = os.environ.get("WEBHOOK_URL")

    if not webhook_url:
        parser.error(
            "Set WEBHOOK_URL before running the delivery worker."
        )

    if args.max_attempts < 1:
        parser.error("--max-attempts must be positive")

    try:
        validate_webhook_url(webhook_url)
    except ValueError as exc:
        parser.error(str(exc))

    store = IncidentStore(args.db)

    if args.retry_exhausted:
        restored = reset_exhausted(
            store,
            max_attempts=args.max_attempts,
        )

        print(
            f"Reset exhausted notifications: {restored}",
            flush=True,
        )

    summary = deliver_pending(
        store,
        webhook_url,
        max_attempts=args.max_attempts,
    )

    print(
        "Delivery summary:",
        summary,
        flush=True,
    )

    if summary["exhausted"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
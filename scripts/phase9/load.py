#!/usr/bin/env python3
"""Small bounded HTTP load generator for the Phase 9 reliability experiment."""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime, timezone
from urllib.parse import urlsplit

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--duration", type=float, default=180)
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()

    parsed = urlsplit(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        parser.error("--url must be an absolute HTTP or HTTPS URL")
    if not 1 <= args.duration <= 900:
        parser.error("--duration must be between 1 and 900 seconds")
    if not 0.05 <= args.interval <= 60:
        parser.error("--interval must be between 0.05 and 60 seconds")

    started_at = datetime.now(timezone.utc)
    deadline = time.monotonic() + args.duration
    statuses: Counter[str] = Counter()
    latencies = []

    while time.monotonic() < deadline:
        started = time.perf_counter()
        try:
            response = requests.get(args.url, timeout=5)
            statuses[str(response.status_code)] += 1
        except requests.RequestException:
            statuses["request_error"] += 1
        latencies.append((time.perf_counter() - started) * 1000)
        time.sleep(args.interval)

    result = {
        "started_at": started_at.isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "target": f"{parsed.scheme}://{parsed.netloc}{parsed.path}",
        "requests": sum(statuses.values()),
        "status_counts": dict(sorted(statuses.items())),
        "latency_ms": {
            "minimum": round(min(latencies), 2),
            "maximum": round(max(latencies), 2),
            "average": round(sum(latencies) / len(latencies), 2),
        },
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

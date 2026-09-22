import time
import os
from datetime import datetime, timezone

import requests

TARGET_URL = os.environ.get(
    "TARGET_URL",
    "http://127.0.0.1:8000/health",
)


def check_health(url=TARGET_URL):
    start = time.perf_counter()

    try:
        response = requests.get(url, timeout=5)
        latency_ms = round(
            (time.perf_counter() - start) * 1000, 2
        )

        data = response.json()

        healthy = (
            response.status_code == 200
            and data.get("status") == "healthy"
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy": healthy,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error": None if healthy else "Unhealthy response",
        }

    except (requests.RequestException, ValueError) as exc:
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "healthy": False,
            "status_code": None,
            "latency_ms": round(
                (time.perf_counter() - start) * 1000, 2
            ),
            "error": str(exc),
        }


if __name__ == "__main__":
    print(check_health())
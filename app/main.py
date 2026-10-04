import json
import os
import time
from datetime import datetime, timezone

if os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING"):
    from azure.monitor.opentelemetry import configure_azure_monitor

    configure_azure_monitor(
        connection_string=os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"],
        instrumentation_options={"fastapi": {"enabled": True}},
    )

from fastapi import FastAPI, HTTPException, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

app = FastAPI(title="Azure Reliability Platform")

HTTP_REQUESTS = Counter(
    "arp_http_requests_total",
    "Completed HTTP requests handled by the application.",
    ("method", "path", "status_code"),
)
HTTP_REQUEST_DURATION = Histogram(
    "arp_http_request_duration_seconds",
    "Application HTTP request duration in seconds.",
    ("method", "path"),
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
HEALTH_STATUS = Gauge(
    "arp_health_status",
    "Current semantic health status: 1 healthy, 0 controlled fault.",
)
APPLICATION_INFO = Gauge(
    "arp_application_info",
    "Immutable application revision information.",
    ("version",),
)
APPLICATION_INFO.labels(
    version=os.environ.get("APP_VERSION", "local"),
).set(1)

BOUNDED_METRIC_PATHS = {"/", "/health", "/ready", "/metrics"}


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    path = (
        request.url.path
        if request.url.path in BOUNDED_METRIC_PATHS
        else "other"
    )
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        elapsed = time.perf_counter() - started
        if path != "/metrics":
            HTTP_REQUESTS.labels(
                method=request.method,
                path=path,
                status_code=str(status),
            ).inc()
            HTTP_REQUEST_DURATION.labels(
                method=request.method,
                path=path,
            ).observe(elapsed)

        print(json.dumps({
            "event": "http_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "latency_ms": round(elapsed * 1000, 2),
            "deployment": os.environ.get("APP_VERSION", "local"),
        }), flush=True)


@app.get("/")
def root():
    return {"message": "Azure Reliability Platform is running"}


@app.get("/health")
def health():
    fault = os.environ.get("ARP_PHASE8_FAULT")

    if fault == "invalid_health":
        HEALTH_STATUS.set(0)
        return {"status": "degraded"}

    if fault == "http_500":
        HEALTH_STATUS.set(0)
        raise HTTPException(
            status_code=500,
            detail="Controlled health failure",
        )

    HEALTH_STATUS.set(1)
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

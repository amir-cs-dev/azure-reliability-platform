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

from fastapi import FastAPI, Request

app = FastAPI(title="Azure Reliability Platform")


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        print(json.dumps({
            "event": "http_request",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "deployment": os.environ.get("APP_VERSION", "local"),
        }), flush=True)


@app.get("/")
def root():
    return {"message": "Azure Reliability Platform is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/ready")
def ready():
    return {"status": "ready"}

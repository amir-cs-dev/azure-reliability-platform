from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_metrics_exposes_request_count_latency_and_revision(monkeypatch):
    monkeypatch.delenv("ARP_PHASE8_FAULT", raising=False)

    response = client.get("/health")
    metrics = client.get("/metrics")

    assert response.status_code == 200
    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain;")
    assert "arp_http_requests_total" in metrics.text
    assert 'path="/health",status_code="200"' in metrics.text
    assert "arp_http_request_duration_seconds_bucket" in metrics.text
    assert "arp_application_info" in metrics.text
    assert "arp_health_status 1.0" in metrics.text


def test_controlled_http_fault_is_visible_in_metrics(monkeypatch):
    monkeypatch.setenv("ARP_PHASE8_FAULT", "http_500")

    response = client.get("/health")
    metrics = client.get("/metrics")

    assert response.status_code == 500
    assert 'path="/health",status_code="500"' in metrics.text
    assert "arp_health_status 0.0" in metrics.text


def test_unknown_paths_use_bounded_metric_label():
    response = client.get("/one-off-path")
    metrics = client.get("/metrics")

    assert response.status_code == 404
    assert 'path="other",status_code="404"' in metrics.text
    assert 'path="/one-off-path"' not in metrics.text

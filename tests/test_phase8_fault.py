from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_normal(monkeypatch):
    monkeypatch.delenv("ARP_PHASE8_FAULT", raising=False)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_invalid_content(monkeypatch):
    monkeypatch.setenv("ARP_PHASE8_FAULT", "invalid_health")
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "degraded"}


def test_health_http_500(monkeypatch):
    monkeypatch.setenv("ARP_PHASE8_FAULT", "http_500")
    response = client.get("/health")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Controlled health failure"
    }


def test_controlled_faults_are_protocol_distinct(monkeypatch):
    monkeypatch.setenv("ARP_PHASE8_FAULT", "invalid_health")
    semantic_failure = client.get("/health")

    monkeypatch.setenv("ARP_PHASE8_FAULT", "http_500")
    http_failure = client.get("/health")

    assert semantic_failure.status_code == 200
    assert http_failure.status_code == 500
    assert semantic_failure.json() != http_failure.json()

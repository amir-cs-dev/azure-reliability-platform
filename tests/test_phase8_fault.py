from app.main import health


def test_health_normal(monkeypatch):
    monkeypatch.delenv("ARP_PHASE8_FAULT", raising=False)
    assert health() == {"status": "healthy"}


def test_health_invalid_content(monkeypatch):
    monkeypatch.setenv("ARP_PHASE8_FAULT", "invalid_health")
    assert health() == {"status": "degraded"}

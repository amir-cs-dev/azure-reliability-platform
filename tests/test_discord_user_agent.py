import json

from monitor.alerts import deliver_pending


def test_discord_delivery_uses_verified_user_agent():
    notification = {
        "id": 1,
        "incident_id": 42,
        "event": "INCIDENT_OPENED",
        "attempts": 0,
        "payload": json.dumps({
            "event": "INCIDENT_OPENED",
            "incident_id": 42,
        }),
    }

    class Store:
        def pending_notifications(self):
            return [notification]

        def mark_delivered(self, notification_id):
            assert notification_id == 1
            return True

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def getcode(self):
            return 204

    def fake_opener(request, timeout):
        assert timeout == 5
        assert request.get_header("User-agent") == (
            "ARP-Reliability-Platform/1.0"
        )
        assert request.get_header("X-idempotency-key") == (
            "incident-42-INCIDENT_OPENED"
        )

        body = json.loads(request.data)
        assert "INCIDENT_OPENED" in body["content"]
        return Response()

    result = deliver_pending(
        Store(),
        "https://discord.com/api/webhooks/123/test-token",
        opener=fake_opener,
        sleeper=lambda _: None,
    )

    assert result == {
        "delivered": 1,
        "failed": 0,
        "exhausted": 0,
    }

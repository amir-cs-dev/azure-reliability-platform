from unittest.mock import patch, Mock

import requests

from monitor.checker import check_health


def make_response(status_code, data):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data
    return response


def test_healthy_response():
    response = make_response(200, {"status": "healthy"})

    with patch("monitor.checker.requests.get", return_value=response):
        result = check_health()

    assert result["healthy"] is True
    assert result["status_code"] == 200
    assert result["error"] is None
    assert result["latency_ms"] >= 0
    assert result["timestamp"]


def test_http_500_failure():
    response = make_response(500, {"status": "error"})

    with patch("monitor.checker.requests.get", return_value=response):
        result = check_health()

    assert result["healthy"] is False
    assert result["status_code"] == 500


def test_incorrect_health_content():
    response = make_response(200, {"status": "unhealthy"})

    with patch("monitor.checker.requests.get", return_value=response):
        result = check_health()

    assert result["healthy"] is False
    assert result["status_code"] == 200


def test_connection_failure():
    with patch(
        "monitor.checker.requests.get",
        side_effect=requests.ConnectionError("Connection refused"),
    ):
        result = check_health()

    assert result["healthy"] is False
    assert result["status_code"] is None
    assert "Connection refused" in result["error"]


def test_request_timeout():
    with patch(
        "monitor.checker.requests.get",
        side_effect=requests.Timeout("Request timed out"),
    ):
        result = check_health()

    assert result["healthy"] is False
    assert result["status_code"] is None
    assert "Request timed out" in result["error"]


def test_invalid_json():
    response = Mock()
    response.status_code = 200
    response.json.side_effect = ValueError("Invalid JSON")

    with patch("monitor.checker.requests.get", return_value=response):
        result = check_health()

    assert result["healthy"] is False
    assert "Invalid JSON" in result["error"]
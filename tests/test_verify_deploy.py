import io
import json
import runpy
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest


VERIFIER = (
    Path(__file__).resolve().parents[1]
    / "scripts/verify_deploy.py"
)


def configure(monkeypatch, bad_sample=None, never_cutover=False):
    registry = "test-registry.azurecr.io"
    sha = "test-commit-sha"

    monkeypatch.setenv("REGISTRY", registry)
    monkeypatch.setenv("GITHUB_SHA", sha)

    state = {
        "requests": [],
        "health_checks": 0,
        "revision_checks": 0,
        "sleeps": [],
    }

    def fake_azure(command, text=True):
        if command[1:3] == ["containerapp", "show"]:
            name = command[command.index("-n") + 1]

            if name != "ca-arp-api-wus3":
                raise AssertionError(f"Unexpected app: {name}")

            return json.dumps({
                "properties": {
                    "template": {
                        "containers": [{
                            "image": f"{registry}/reliability-api:{sha}"
                        }]
                    },
                    "latestRevisionName": "api-new",
                    "configuration": {
                        "ingress": {
                            "fqdn": "api.example.invalid"
                        }
                    },
                }
            })

        if command[1:4] == [
            "containerapp", "revision", "list"
        ]:
            state["revision_checks"] += 1

            return json.dumps([{
                "name": (
                    "api-old" if never_cutover else "api-new"
                ),
                "properties": {
                    "active": True,
                    "trafficWeight": 100,
                },
            }])

        raise AssertionError(f"Unexpected Azure command: {command}")

    def fake_urlopen(request, timeout=10):
        path = request.full_url.rsplit("/", 1)[-1]
        state["requests"].append(path)

        if path == "health":
            state["health_checks"] += 1

            status = (
                "degraded"
                if state["health_checks"] == bad_sample
                else "healthy"
            )
            body = {"status": status}

        elif path == "ready":
            body = {"status": "ready"}

        else:
            raise AssertionError(f"Unexpected endpoint: {path}")

        response = io.BytesIO(json.dumps(body).encode())
        response.status = 200
        return response

    monkeypatch.setattr(
        subprocess, "check_output", fake_azure
    )
    monkeypatch.setattr(
        urllib.request, "urlopen", fake_urlopen
    )
    monkeypatch.setattr(
        time,
        "sleep",
        lambda seconds: state["sleeps"].append(seconds),
    )

    return state


def run_verifier():
    runpy.run_path(str(VERIFIER), run_name="__main__")


def test_healthy_deployment_passes_all_six_samples(
    monkeypatch,
):
    state = configure(monkeypatch)

    run_verifier()

    assert state["health_checks"] == 6
    assert state["requests"] == [
        "health", "ready"
    ] * 6


@pytest.mark.parametrize("bad_sample", [1, 6])
def test_degraded_health_rejects_deployment(
    monkeypatch, bad_sample
):
    state = configure(
        monkeypatch,
        bad_sample=bad_sample,
    )

    with pytest.raises(
        SystemExit,
        match=rf"FAIL: /health sample {bad_sample}",
    ):
        run_verifier()

    assert state["health_checks"] == bad_sample
    assert state["requests"][-1] == "health"


def test_deployment_without_cutover_fails(
    monkeypatch,
):
    state = configure(
        monkeypatch,
        never_cutover=True,
    )

    with pytest.raises(
        SystemExit,
        match="never completed cutover",
    ):
        run_verifier()

    assert state["revision_checks"] == 36
    assert state["requests"] == []

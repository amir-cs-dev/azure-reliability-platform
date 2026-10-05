import json
import os
import subprocess
import time
import urllib.request

GROUP = "rg-arp-app-wus3"
API = "ca-arp-api-wus3"
EXPECTED_API = f"{os.environ['REGISTRY']}/reliability-api:{os.environ['GITHUB_SHA']}"


def azure_json(*args):
    return json.loads(subprocess.check_output(
        ["az", *args, "-o", "json"], text=True
    ))


def app(name):
    return azure_json("containerapp", "show", "-g", GROUP, "-n", name)


api = app(API)

assert api["properties"]["template"]["containers"][0]["image"] == EXPECTED_API, (
    "API image does not match this workflow commit"
)

target = api["properties"]["latestRevisionName"]
fqdn = api["properties"]["configuration"]["ingress"]["fqdn"]
print(f"Target API revision: {target}", flush=True)

for attempt in range(36):
    revisions = azure_json(
        "containerapp", "revision", "list",
        "-g", GROUP, "-n", API
    )

    serving = [
        revision["name"]
        for revision in revisions
        if revision["properties"].get("active")
        and revision["properties"].get("trafficWeight") == 100
    ]

    if serving == [target]:
        print("PASS: Exact deployed revision has 100% traffic.", flush=True)
        break

    time.sleep(5)
else:
    raise SystemExit("FAIL: Deployment revision never completed cutover.")

# Check repeatedly after cutover, not just once while the old
# revision might still be answering ingress requests.
time.sleep(10)

for sample in range(1, 7):
    revisions = azure_json(
        "containerapp", "revision", "list",
        "-g", GROUP, "-n", API
    )
    serving = [
        revision["name"]
        for revision in revisions
        if revision["properties"].get("active")
        and revision["properties"].get("trafficWeight") == 100
    ]
    if serving != [target]:
        raise SystemExit("FAIL: Serving revision changed during verification.")

    for path, expected in (
        ("/health", {"status": "healthy"}),
        ("/ready", {"status": "ready"}),
    ):
        request = urllib.request.Request(
            f"https://{fqdn}{path}",
            headers={"Cache-Control": "no-cache"},
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            body = json.load(response)
            if response.status != 200 or body != expected:
                raise SystemExit(
                    f"FAIL: {path} sample {sample}: "
                    f"HTTP {response.status}, body={body!r}"
                )

    print(f"PASS: Health/readiness sample {sample}/6", flush=True)
    if sample < 6:
        time.sleep(10)

print("PASS: Deployment verified after cutover.", flush=True)

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHART = ROOT / "deploy" / "helm" / "arp-phase9"
PHASE9_TF = ROOT / "infra" / "phase9"


def read(path):
    return path.read_text()


def test_aks_is_minimal_isolated_and_reuses_existing_acr():
    aks = read(PHASE9_TF / "aks.tf")
    backend = read(PHASE9_TF / "backend.tf")
    main = read(PHASE9_TF / "main.tf")
    variables = read(PHASE9_TF / "variables.tf")

    assert 'sku_tier                  = "Free"' in aks
    assert 'node_count           = 1' in aks
    assert 'auto_scaling_enabled = false' in aks
    assert 'os_disk_size_gb              = 30' in aks
    assert 'network_plugin_mode = "overlay"' in aks
    assert 'resource "azurerm_role_assignment" "aks_acr_pull"' in aks
    assert 'role_definition_name = "AcrPull"' in aks
    assert 'key              = "phase9.terraform.tfstate"' in backend
    assert 'data "azurerm_container_registry" "app"' in main
    assert "azurerm_log_analytics_workspace" not in aks
    assert 'default     = "Standard_D2as_v4"' in variables
    assert "Standard_D2as_v5" not in variables


def test_application_uses_digest_probes_limits_and_rolling_update():
    deployment = read(CHART / "templates" / "application.yaml")

    assert "{{ .Values.image.repository }}@{{ .Values.image.digest }}" in deployment
    assert "maxUnavailable: 0" in deployment
    assert "maxSurge: 1" in deployment
    assert "readinessProbe:" in deployment
    assert "path: /ready" in deployment
    assert "livenessProbe:" in deployment
    assert "path: /health" in deployment
    assert "toYaml .Values.application.resources" in deployment
    assert "ARP_PHASE8_FAULT" in deployment
    assert "runAsUser: 1000" in deployment


def test_named_non_root_observability_images_use_numeric_uids():
    observability = read(CHART / "templates" / "observability.yaml")
    kube_state_metrics = read(CHART / "templates" / "kube-state-metrics.yaml")

    assert observability.count("runAsUser: 65534") == 2
    assert "runAsUser: 472" in observability
    assert "runAsUser: 65534" in kube_state_metrics


def test_prometheus_alertmanager_and_external_secret_flow_are_real():
    prometheus = read(CHART / "files" / "prometheus.yml")
    rules = read(CHART / "files" / "arp-rules.yml")
    alertmanager = read(CHART / "files" / "alertmanager.yml")

    assert "kubernetes_sd_configs:" in prometheus
    assert "job_name: arp-api" in prometheus
    assert "job_name: kube-state-metrics" in prometheus
    assert "ArpApplicationTargetDown" in rules
    assert "ArpApplicationHealthEndpointFailing" in rules
    assert "arp_http_requests_total" in rules
    assert "webhook_url_file:" in alertmanager
    assert "webhook_url:" not in alertmanager


def test_grafana_dashboard_queries_real_reliability_metrics():
    dashboard = json.loads(
        read(CHART / "files" / "grafana-dashboard.json")
    )
    expressions = [
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel["targets"]
    ]

    assert dashboard["uid"] == "arp-phase9-reliability"
    assert len(dashboard["panels"]) == 5
    assert any("arp_http_requests_total" in query for query in expressions)
    assert any("arp_http_request_duration_seconds" in query for query in expressions)
    assert any("kube_deployment_status" in query for query in expressions)


def test_experiment_has_real_fault_rollout_rollback_and_external_checker():
    experiment = read(ROOT / "scripts" / "phase9" / "experiment.sh")
    load = read(ROOT / "scripts" / "phase9" / "load.py")

    assert "deployment.faultMode=http_500" in experiment
    assert "rollout status deployment/arp-api" in experiment
    assert "helm rollback" in experiment
    assert "TARGET_URL=$application_url/health" in experiment
    assert "prometheus-alert-firing.json" in experiment
    assert "grafana-live-query.json" in experiment
    assert "external-checker-baseline.json" in experiment
    assert "target_switched_at" in experiment
    assert "external-checker-recovery.json" in experiment
    assert "from urllib.request import urlopen" in load
    assert "import requests" not in load


def test_deploy_digest_lookup_ignores_untagged_acr_manifests():
    deploy = read(ROOT / "scripts" / "phase9" / "deploy.sh")

    assert "tags != null && contains(tags, '$image_tag')" in deploy

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def workflow(name):
    return (ROOT / ".github" / "workflows" / name).read_text()


def test_ci_has_read_only_permissions_and_terraform_validation():
    ci = workflow("ci.yml")
    assert "permissions:\n  contents: read" in ci
    assert "terraform fmt -check -recursive infra/app" in ci
    assert "terraform -chdir=infra/app init -backend=false" in ci
    assert "terraform -chdir=infra/app validate" in ci


def test_plan_is_separate_from_apply_and_retains_review_artifact():
    plan = workflow("terraform-plan.yml")
    assert "pull_request:" not in plan
    assert "push:\n    branches: [main]" in plan
    assert "needs: validate" in plan
    assert "id-token: write" in plan
    assert "plan_args=(" in plan
    assert "terraform apply" not in plan
    assert "plan.tfplan" in plan
    assert "plan.txt" in plan
    assert "metadata.json" in plan
    assert "TF_VAR_monitor_target_url" in plan
    assert "TF_VAR_key_vault_operator_object_id" in plan
    assert '"$RUNNER_TEMP/plan.json"' in plan
    assert "retention-days: 7" in plan
    assert "Refuse public binary-plan publication" in plan
    assert "github.event.repository.private" in plan


def test_apply_is_manual_main_only_and_checks_exact_plan_identity():
    apply = workflow("terraform-apply.yml")
    assert "workflow_dispatch:" in apply
    assert "pull_request:" not in apply
    assert "confirmation:" in apply
    assert '== "APPLY"' in apply
    assert "refs/heads/main" in apply
    assert "actions: read" in apply
    assert "id-token: write" in apply
    assert "PLAN_RUN_ID" in apply
    assert "CURRENT_MAIN_SHA" in apply
    assert "terraform_plan_artifact.py validate" in apply
    assert 'apply -input=false -auto-approve "$PLAN_FILE"' in apply
    assert "Refuse public binary-plan consumption" in apply
    assert "github.event.repository.private" in apply


def test_application_deploy_remains_validation_gated_and_main_only():
    deploy = workflow("deploy.yml")
    assert "workflow_dispatch:" in deploy
    assert "needs: validate" in deploy
    assert "github.ref == 'refs/heads/main'" in deploy
    assert "id-token: write" in deploy
    assert "write-all" not in deploy
    assert "ca-arp-monitor-wus3" not in deploy
    assert "reliability-monitor" not in deploy


def test_phase9_plan_is_isolated_and_never_applies_automatically():
    plan = workflow("phase9-terraform-plan.yml")
    assert "needs: validate" in plan
    assert "phase9.terraform.tfstate" in plan
    assert "phase9-terraform-plan" in plan
    assert "-destroy" in plan
    assert "terraform apply" not in plan
    assert "infra/phase9" in plan
    assert "retention-days: 7" in plan
    assert "Refuse public binary-plan publication" in plan
    assert "github.event.repository.private" in plan


def test_phase9_apply_requires_exact_manual_current_main_plan():
    apply = workflow("phase9-terraform-apply.yml")
    assert "workflow_dispatch:" in apply
    assert '== "APPLY"' in apply
    assert "refs/heads/main" in apply
    assert "phase9-terraform-plan.yml" in apply
    assert "phase9.terraform.tfstate" in apply
    assert "terraform_plan_artifact.py validate" in apply
    assert "Apply exact reviewed Phase 9 binary plan" in apply
    assert "id-token: write" in apply
    assert "AZURE_PHASE9_TERRAFORM_APPLY_CLIENT_ID" in apply
    assert "AZURE_TERRAFORM_APPLY_CLIENT_ID" not in apply
    assert "Refuse public binary-plan consumption" in apply
    assert "github.event.repository.private" in apply

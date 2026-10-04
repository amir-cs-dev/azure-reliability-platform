import json
from datetime import datetime, timedelta, timezone

import pytest

from scripts import terraform_plan_artifact as artifact


SHA = "a" * 40
TREE = "b" * 40
RUN_ID = "123456"
REPOSITORY = "owner/repository"
VERSION = "1.16.3"


def make_bundle(tmp_path, *, created_at=None):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "plan.tfplan").write_bytes(b"binary-plan")
    (bundle / "plan.txt").write_text("Terraform will perform one update.\n")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(json.dumps({
        "terraform_version": VERSION,
        "resource_changes": [{
            "address": "azurerm_example.test",
            "change": {"actions": ["update"]},
        }],
    }))
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"lineage": "lineage-1", "serial": 9}))
    metadata = artifact.create_metadata(
        bundle_dir=bundle,
        plan_json_path=plan_json,
        state_path=state,
        operation="normal",
        plan_exit_code=2,
        repository=REPOSITORY,
        source_sha=SHA,
        source_ref="refs/heads/main",
        source_branch="main",
        event_name="workflow_dispatch",
        run_id=RUN_ID,
        run_attempt="1",
        workflow_ref=(
            f"{REPOSITORY}/.github/workflows/terraform-plan.yml@refs/heads/main"
        ),
        terraform_version=VERSION,
        infra_tree=TREE,
        image_tag=SHA,
        state_resource_group="state-rg",
        state_storage_account="stateaccount",
        created_at=created_at,
    )
    metadata_path = bundle / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))
    return bundle, plan_json, state, metadata_path


def validate(bundle, plan_json, state, metadata_path, **overrides):
    arguments = {
        "bundle_dir": bundle,
        "plan_json_path": plan_json,
        "metadata_path": metadata_path,
        "current_state_path": state,
        "expected_repository": REPOSITORY,
        "expected_run_id": RUN_ID,
        "expected_main_sha": SHA,
        "expected_terraform_version": VERSION,
        "expected_infra_tree": TREE,
        "max_age_seconds": 86400,
        "now": datetime.now(timezone.utc),
    }
    arguments.update(overrides)
    return artifact.validate_metadata(**arguments)


def test_exact_plan_bundle_is_accepted(tmp_path):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)

    metadata = validate(bundle, plan_json, state, metadata_path)

    assert metadata["plan"]["summary"]["counts"]["update"] == 1


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"expected_run_id": "999"}, "requested run"),
        ({"expected_main_sha": "c" * 40}, "current main"),
        ({"expected_infra_tree": "d" * 40}, "tree changed"),
        ({"expected_terraform_version": "1.17.0"}, "version mismatch"),
    ],
)
def test_expected_identity_mismatch_is_rejected(tmp_path, override, message):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)

    with pytest.raises(artifact.ControlError, match=message):
        validate(bundle, plan_json, state, metadata_path, **override)


def test_changed_remote_state_serial_is_rejected(tmp_path):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)
    state.write_text(json.dumps({"lineage": "lineage-1", "serial": 10}))

    with pytest.raises(artifact.ControlError, match="state serial changed"):
        validate(bundle, plan_json, state, metadata_path)


def test_changed_plan_file_is_rejected(tmp_path):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)
    (bundle / "plan.tfplan").write_bytes(b"tampered")

    with pytest.raises(artifact.ControlError, match="hash mismatch"):
        validate(bundle, plan_json, state, metadata_path)


def test_stale_plan_is_rejected(tmp_path):
    old = datetime.now(timezone.utc) - timedelta(days=2)
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path, created_at=old)

    with pytest.raises(artifact.ControlError, match="older than"):
        validate(bundle, plan_json, state, metadata_path)


def test_pull_request_plan_cannot_be_applied(tmp_path):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)
    metadata = json.loads(metadata_path.read_text())
    metadata["source"]["event"] = "pull_request"
    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(artifact.ControlError, match="not apply-eligible"):
        validate(bundle, plan_json, state, metadata_path)


def test_non_main_plan_cannot_be_applied(tmp_path):
    bundle, plan_json, state, metadata_path = make_bundle(tmp_path)
    metadata = json.loads(metadata_path.read_text())
    metadata["source"]["ref"] = "refs/heads/feature"
    metadata_path.write_text(json.dumps(metadata))

    with pytest.raises(artifact.ControlError, match="not refs/heads/main"):
        validate(bundle, plan_json, state, metadata_path)


def test_phase9_destroy_plan_uses_isolated_identity(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "plan.tfplan").write_bytes(b"phase9-binary-plan")
    (bundle / "plan.txt").write_text("Terraform will destroy the AKS lab.\n")
    plan_json = tmp_path / "plan.json"
    plan_json.write_text(json.dumps({
        "terraform_version": VERSION,
        "resource_changes": [{
            "address": "azurerm_kubernetes_cluster.phase9",
            "change": {"actions": ["delete"]},
        }],
    }))
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"lineage": "phase9-lineage", "serial": 3}))

    metadata = artifact.create_metadata(
        bundle_dir=bundle,
        plan_json_path=plan_json,
        state_path=state,
        operation="destroy",
        plan_exit_code=2,
        repository=REPOSITORY,
        source_sha=SHA,
        source_ref="refs/heads/main",
        source_branch="main",
        event_name="workflow_dispatch",
        run_id=RUN_ID,
        run_attempt="1",
        workflow_ref=(
            f"{REPOSITORY}/.github/workflows/"
            "phase9-terraform-plan.yml@refs/heads/main"
        ),
        terraform_version=VERSION,
        infra_tree=TREE,
        image_tag=SHA,
        state_resource_group="state-rg",
        state_storage_account="stateaccount",
        state_key="phase9.terraform.tfstate",
        artifact_prefix="phase9-terraform-plan",
    )
    metadata_path = bundle / "metadata.json"
    metadata_path.write_text(json.dumps(metadata))

    accepted = artifact.validate_metadata(
        bundle_dir=bundle,
        plan_json_path=plan_json,
        metadata_path=metadata_path,
        current_state_path=state,
        expected_repository=REPOSITORY,
        expected_run_id=RUN_ID,
        expected_main_sha=SHA,
        expected_terraform_version=VERSION,
        expected_infra_tree=TREE,
        max_age_seconds=86400,
        expected_state_key="phase9.terraform.tfstate",
        expected_artifact_prefix="phase9-terraform-plan",
        expected_workflow_file="phase9-terraform-plan.yml",
    )

    assert accepted["terraform"]["operation"] == "destroy"
    assert accepted["plan"]["summary"]["counts"]["delete"] == 1

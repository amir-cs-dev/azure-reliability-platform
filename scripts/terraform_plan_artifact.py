#!/usr/bin/env python3
"""Create and validate the evidence bundle for an approved Terraform apply."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 1
ALLOWED_OPERATIONS = {"destroy", "normal", "refresh-only"}
ALLOWED_APPLY_EVENTS = {"push", "workflow_dispatch"}
REQUIRED_PLAN_FILES = ("plan.tfplan", "plan.txt")
MAIN_REF = "refs/heads/main"


class ControlError(ValueError):
    """Raised when a plan bundle fails an integrity or freshness control."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _state_identity(path: Path) -> dict[str, object]:
    state = json.loads(path.read_text())
    lineage = state.get("lineage")
    serial = state.get("serial")
    if not isinstance(lineage, str) or not lineage:
        raise ControlError("Terraform state lineage is missing")
    if not isinstance(serial, int) or serial < 0:
        raise ControlError("Terraform state serial is invalid")
    return {"lineage": lineage, "serial": serial}


def _plan_summary(plan: dict[str, object]) -> dict[str, object]:
    counts = {
        "create": 0,
        "read": 0,
        "update": 0,
        "delete": 0,
        "replace": 0,
    }
    affected = []
    for resource in plan.get("resource_changes", []):
        actions = resource["change"]["actions"]
        if actions == ["no-op"]:
            continue
        if "delete" in actions and "create" in actions:
            category = "replace"
        elif len(actions) == 1 and actions[0] in counts:
            category = actions[0]
        else:
            raise ControlError(f"Unsupported Terraform action sequence: {actions!r}")
        counts[category] += 1
        affected.append({
            "address": resource["address"],
            "actions": actions,
        })
    return {
        "counts": counts,
        "affected_resources": affected,
    }


def create_metadata(
    *,
    bundle_dir: Path,
    plan_json_path: Path,
    state_path: Path,
    operation: str,
    plan_exit_code: int,
    repository: str,
    source_sha: str,
    source_ref: str,
    source_branch: str,
    event_name: str,
    run_id: str,
    run_attempt: str,
    workflow_ref: str,
    terraform_version: str,
    infra_tree: str,
    image_tag: str,
    state_resource_group: str,
    state_storage_account: str,
    created_at: datetime | None = None,
    state_key: str = "application.terraform.tfstate",
    artifact_prefix: str = "terraform-plan",
) -> dict[str, object]:
    if operation not in ALLOWED_OPERATIONS:
        raise ControlError(f"Unsupported plan operation: {operation}")
    if plan_exit_code not in (0, 2):
        raise ControlError(f"Terraform plan exit code was {plan_exit_code}, not 0 or 2")

    plan_files = {}
    for name in REQUIRED_PLAN_FILES:
        path = bundle_dir / name
        if not path.is_file() or path.stat().st_size == 0:
            raise ControlError(f"Required plan file is missing or empty: {name}")
        plan_files[name] = {
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        }

    plan_json = json.loads(plan_json_path.read_text())
    metadata = {
        "schema_version": SCHEMA_VERSION,
        "artifact_name": f"{artifact_prefix}-{run_id}",
        "repository": repository,
        "source": {
            "sha": source_sha,
            "ref": source_ref,
            "branch": source_branch,
            "event": event_name,
            "infra_tree": infra_tree,
        },
        "workflow": {
            "run_id": str(run_id),
            "run_attempt": str(run_attempt),
            "workflow_ref": workflow_ref,
        },
        "terraform": {
            "version": terraform_version,
            "operation": operation,
            "plan_exit_code": plan_exit_code,
        },
        "backend": {
            "type": "azurerm",
            "resource_group": state_resource_group,
            "storage_account": state_storage_account,
            "container": "tfstate",
            "key": state_key,
            **_state_identity(state_path),
        },
        "variables": {"image_tag": image_tag},
        "plan": {
            "files": plan_files,
            "summary": _plan_summary(plan_json),
        },
        "created_at": (created_at or datetime.now(timezone.utc)).isoformat(),
    }
    return metadata


def validate_metadata(
    *,
    bundle_dir: Path,
    plan_json_path: Path,
    metadata_path: Path,
    current_state_path: Path,
    expected_repository: str,
    expected_run_id: str,
    expected_main_sha: str,
    expected_terraform_version: str,
    expected_infra_tree: str,
    max_age_seconds: int,
    now: datetime | None = None,
    expected_state_key: str = "application.terraform.tfstate",
    expected_artifact_prefix: str = "terraform-plan",
    expected_workflow_file: str = "terraform-plan.yml",
) -> dict[str, object]:
    metadata = json.loads(metadata_path.read_text())
    errors = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(metadata.get("schema_version") == SCHEMA_VERSION, "schema mismatch")
    require(metadata.get("repository") == expected_repository, "repository mismatch")
    require(
        metadata.get("artifact_name")
        == f"{expected_artifact_prefix}-{expected_run_id}",
        "artifact name does not match the requested run",
    )

    source = metadata.get("source", {})
    require(source.get("sha") == expected_main_sha, "plan SHA is not current main")
    require(source.get("ref") == MAIN_REF, "plan ref is not refs/heads/main")
    require(source.get("branch") == "main", "plan branch is not main")
    require(source.get("event") in ALLOWED_APPLY_EVENTS, "plan event is not apply-eligible")
    require(source.get("infra_tree") == expected_infra_tree, "infrastructure tree changed")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", str(source.get("sha", "")))), "invalid source SHA")

    workflow = metadata.get("workflow", {})
    require(str(workflow.get("run_id")) == str(expected_run_id), "plan run ID mismatch")
    expected_workflow_ref = (
        f"{expected_repository}/.github/workflows/"
        f"{expected_workflow_file}@{MAIN_REF}"
    )
    require(workflow.get("workflow_ref") == expected_workflow_ref, "unexpected plan workflow ref")

    terraform = metadata.get("terraform", {})
    require(terraform.get("version") == expected_terraform_version, "Terraform version mismatch")
    require(terraform.get("operation") in ALLOWED_OPERATIONS, "unsupported operation")
    require(terraform.get("plan_exit_code") in (0, 2), "invalid plan exit code")

    try:
        created_at = datetime.fromisoformat(metadata["created_at"])
        if created_at.tzinfo is None:
            raise ValueError("timestamp lacks timezone")
        age = ((now or datetime.now(timezone.utc)) - created_at).total_seconds()
        require(age >= -300, "plan timestamp is in the future")
        require(age <= max_age_seconds, "plan is older than the allowed age")
    except (KeyError, TypeError, ValueError):
        errors.append("invalid plan creation timestamp")

    try:
        current_state = _state_identity(current_state_path)
        backend = metadata["backend"]
        require(backend.get("type") == "azurerm", "unexpected backend type")
        require(backend.get("container") == "tfstate", "unexpected state container")
        require(
            backend.get("key") == expected_state_key,
            "unexpected state key",
        )
        require(backend.get("lineage") == current_state["lineage"], "state lineage changed")
        require(backend.get("serial") == current_state["serial"], "state serial changed")
    except (ControlError, KeyError, TypeError) as exc:
        errors.append(f"invalid backend/state metadata: {exc}")

    files = metadata.get("plan", {}).get("files", {})
    for name in REQUIRED_PLAN_FILES:
        path = bundle_dir / name
        record = files.get(name, {})
        require(path.is_file(), f"missing artifact file: {name}")
        if path.is_file():
            require(record.get("sha256") == _sha256(path), f"hash mismatch: {name}")
            require(record.get("size_bytes") == path.stat().st_size, f"size mismatch: {name}")

    try:
        plan_json = json.loads(plan_json_path.read_text())
        require(
            metadata.get("plan", {}).get("summary") == _plan_summary(plan_json),
            "plan summary mismatch",
        )
        require(
            plan_json.get("terraform_version") == expected_terraform_version,
            "plan JSON Terraform version mismatch",
        )
    except (OSError, json.JSONDecodeError, ControlError) as exc:
        errors.append(f"invalid plan JSON: {exc}")

    if errors:
        raise ControlError("; ".join(errors))
    return metadata


def _create_command(args: argparse.Namespace) -> None:
    metadata = create_metadata(
        bundle_dir=args.bundle_dir,
        plan_json_path=args.plan_json,
        state_path=args.state,
        operation=args.operation,
        plan_exit_code=args.plan_exit_code,
        repository=args.repository,
        source_sha=args.source_sha,
        source_ref=args.source_ref,
        source_branch=args.source_branch,
        event_name=args.event_name,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        workflow_ref=args.workflow_ref,
        terraform_version=args.terraform_version,
        infra_tree=args.infra_tree,
        image_tag=args.image_tag,
        state_resource_group=args.state_resource_group,
        state_storage_account=args.state_storage_account,
        state_key=args.state_key,
        artifact_prefix=args.artifact_prefix,
    )
    args.output.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")


def _validate_command(args: argparse.Namespace) -> None:
    metadata = validate_metadata(
        bundle_dir=args.bundle_dir,
        plan_json_path=args.plan_json,
        metadata_path=args.metadata,
        current_state_path=args.current_state,
        expected_repository=args.repository,
        expected_run_id=args.run_id,
        expected_main_sha=args.main_sha,
        expected_terraform_version=args.terraform_version,
        expected_infra_tree=args.infra_tree,
        max_age_seconds=args.max_age_seconds,
        expected_state_key=args.state_key,
        expected_artifact_prefix=args.artifact_prefix,
        expected_workflow_file=args.workflow_file,
    )
    summary = metadata["plan"]["summary"]["counts"]
    print(
        "PASS: exact reviewed Terraform plan bundle verified "
        f"(operation={metadata['terraform']['operation']}, actions={summary})."
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--bundle-dir", type=Path, required=True)
    create.add_argument("--plan-json", type=Path, required=True)
    create.add_argument("--state", type=Path, required=True)
    create.add_argument("--operation", required=True, choices=sorted(ALLOWED_OPERATIONS))
    create.add_argument("--plan-exit-code", type=int, required=True)
    create.add_argument("--repository", required=True)
    create.add_argument("--source-sha", required=True)
    create.add_argument("--source-ref", required=True)
    create.add_argument("--source-branch", required=True)
    create.add_argument("--event-name", required=True)
    create.add_argument("--run-id", required=True)
    create.add_argument("--run-attempt", required=True)
    create.add_argument("--workflow-ref", required=True)
    create.add_argument("--terraform-version", required=True)
    create.add_argument("--infra-tree", required=True)
    create.add_argument("--image-tag", required=True)
    create.add_argument("--state-resource-group", required=True)
    create.add_argument("--state-storage-account", required=True)
    create.add_argument(
        "--state-key",
        default="application.terraform.tfstate",
    )
    create.add_argument("--artifact-prefix", default="terraform-plan")
    create.add_argument("--output", type=Path, required=True)
    create.set_defaults(func=_create_command)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--bundle-dir", type=Path, required=True)
    validate.add_argument("--plan-json", type=Path, required=True)
    validate.add_argument("--metadata", type=Path, required=True)
    validate.add_argument("--current-state", type=Path, required=True)
    validate.add_argument("--repository", required=True)
    validate.add_argument("--run-id", required=True)
    validate.add_argument("--main-sha", required=True)
    validate.add_argument("--terraform-version", required=True)
    validate.add_argument("--infra-tree", required=True)
    validate.add_argument("--max-age-seconds", type=int, default=86400)
    validate.add_argument(
        "--state-key",
        default="application.terraform.tfstate",
    )
    validate.add_argument("--artifact-prefix", default="terraform-plan")
    validate.add_argument("--workflow-file", default="terraform-plan.yml")
    validate.set_defaults(func=_validate_command)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        args.func(args)
    except (ControlError, OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from pathlib import Path


FUNCTION_TF = (
    Path(__file__).resolve().parents[1]
    / "infra"
    / "app"
    / "function.tf"
).read_text()


def test_flex_runtime_uses_resource_properties_not_legacy_setting():
    assert 'runtime_name    = "python"' in FUNCTION_TF
    assert 'runtime_version = "3.12"' in FUNCTION_TF
    assert "FUNCTIONS_WORKER_RUNTIME" not in FUNCTION_TF
    assert "WEBSITE_RUN_FROM_PACKAGE" not in FUNCTION_TF

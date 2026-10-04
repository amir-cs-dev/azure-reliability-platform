from zipfile import ZipFile

from scripts.build_function_package import build


def test_function_package_has_runtime_root_and_shared_monitor(tmp_path):
    output = build(tmp_path / "function.zip")

    with ZipFile(output) as archive:
        names = set(archive.namelist())

    assert {
        "function_app.py",
        "host.json",
        "requirements.txt",
        "monitor/checker.py",
        "monitor/runner.py",
        "monitor/postgres_storage.py",
    }.issubset(names)

    assert not any(
        "__pycache__" in name or name.endswith(".pem")
        for name in names
    )

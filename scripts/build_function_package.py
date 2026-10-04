import argparse
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FUNCTION_ROOT = ROOT / "azure_function"


def package_files():
    yield FUNCTION_ROOT / "function_app.py", Path("function_app.py")
    yield FUNCTION_ROOT / "host.json", Path("host.json")
    yield FUNCTION_ROOT / "requirements.txt", Path("requirements.txt")

    for source in sorted((ROOT / "monitor").glob("*.py")):
        yield source, Path("monitor") / source.name


def build(output):
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for source, destination in package_files():
            archive.write(source, destination.as_posix())

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build the Azure Function source package",
    )
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(build(args.output))

"""Require a clean installed dependency graph, including compatibility wheels."""
from importlib import metadata
import subprocess
import sys

class Refused(ValueError):
    pass


def validate(result, versions):
    """An unexpected pip result, missing dependency or second conflict refuses."""
    lines = result.stdout.strip().splitlines()
    if result.stderr.strip():
        raise Refused("pip-check-diagnostic")
    if result.returncode == 0 and lines == ["No broken requirements found."]:
        return "clean"
    raise Refused("unreviewed-dependency-conflict")


def main():
    # -I avoids local modules/environment overriding the installed pip checker.
    versions = {name: metadata.version(name) for name in ("ghunt", "pillow")}
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-m", "pip", "check"],
        capture_output=True, text=True, timeout=30, check=False,
    )
    disposition = validate(result, versions)
    print("GHunt dependency audit passed: " + disposition)


if __name__ == "__main__":
    try:
        main()
    except (Refused, metadata.PackageNotFoundError, subprocess.SubprocessError):
        raise SystemExit("GHunt dependency audit refused; run python -m pip check for details") from None

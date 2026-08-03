#!/usr/bin/env python3
"""Append missing example keys to private stack.env files without overwriting values."""

from __future__ import annotations

import argparse
import re
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / "stacks"
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
SECRET_KEY = re.compile(
    r"(?:PASSWORD|PASSWD|SECRET|TOKEN|API_KEY|ACCESS_KEY|PRIVATE_KEY)$"
)
PLACEHOLDER = re.compile(
    r"^(?:|change(?:me|-me)?|replace[-_].*|your[-_].*|generate[-_].*)$",
    re.IGNORECASE,
)


def assignments(path: Path) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ASSIGNMENT.match(line)
        if match:
            values.append((match.group(1), match.group(2)))
    return values


def runtime_value(key: str, value: str, domain: str | None) -> str:
    stripped = value.strip().strip("\"'")
    if SECRET_KEY.search(key) and PLACEHOLDER.match(stripped):
        return secrets.token_urlsafe(36)
    if domain:
        value = value.replace("yourdomain.com", domain)
        value = value.replace("example.com", domain)
    return value


def sync(directory: Path, apply: bool, domain: str | None) -> int:
    example = directory / "stack.env.example"
    runtime = directory / "stack.env"
    if not example.exists() or not runtime.exists():
        print(f"{directory.name}: skipped (requires both stack.env files)")
        return 0
    existing = {key for key, _ in assignments(runtime)}
    missing = [
        (key, runtime_value(key, value, domain))
        for key, value in assignments(example)
        if key not in existing
    ]
    if not missing:
        print(f"{directory.name}: current")
        return 0
    print(f"{directory.name}: {len(missing)} missing key(s): {', '.join(key for key, _ in missing)}")
    if apply:
        text = runtime.read_text(encoding="utf-8")
        separator = "" if not text or text.endswith("\n\n") else ("\n" if text.endswith("\n") else "\n\n")
        additions = "\n".join(f"{key}={value}" for key, value in missing)
        runtime.write_text(
            f"{text}{separator}# Added from stack.env.example by sync-stack-env.py\n{additions}\n",
            encoding="utf-8",
        )
    return len(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stacks", nargs="+", help="stack directory names")
    parser.add_argument("--apply", action="store_true", help="append missing keys")
    parser.add_argument("--domain", help="replace example domains in appended runtime values")
    args = parser.parse_args()
    total = 0
    for name in args.stacks:
        directory = STACKS / name
        if not directory.is_dir():
            parser.error(f"unknown stack: {name}")
        total += sync(directory, args.apply, args.domain)
    if total and not args.apply:
        print("Preview only; re-run with --apply after review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

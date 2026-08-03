#!/usr/bin/env python3
"""Audit and optionally repair top-level stack preparation wrappers."""

from __future__ import annotations

import argparse
import os
import stat
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[1]
STACKS = REPO / "stacks"
STANDARD = """#!/usr/bin/env bash
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/../../scripts/prepare-stack-lib.sh"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
prepare_stack_copy_caddy
prepare_stack_end
"""


def load_compose(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(value, dict):
        raise ValueError("Compose root is not a mapping")
    return value


def literal_externals(section: Any) -> list[str]:
    results: list[str] = []
    if not isinstance(section, dict):
        return results
    for key, value in section.items():
        if not isinstance(value, dict) or value.get("external") is not True:
            continue
        name = value.get("name", key)
        if isinstance(name, str) and "${" not in name:
            results.append(name)
    return sorted(set(results))


def insert_prerequisites(text: str, networks: list[str], volumes: list[str]) -> str:
    additions: list[str] = []
    for name in networks:
        call = f'prepare_stack_ensure_docker_network "{name}"'
        if call not in text:
            additions.append(call)
    for name in volumes:
        call = f'prepare_stack_ensure_docker_volume "{name}"'
        if call not in text:
            additions.append(call)
    if not additions:
        return text
    marker = "prepare_stack_end"
    if marker not in text:
        return text
    block = "\n".join(additions) + "\n"
    return text.replace(marker, block + marker, 1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit verbose stack preparation scripts and Compose prerequisites."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="create missing wrappers and add literal external network/volume prerequisites",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    changed: list[str] = []
    stack_dirs = sorted(path for path in STACKS.iterdir() if path.is_dir())
    compose_count = 0

    for stack_dir in stack_dirs:
        compose_path = stack_dir / "docker-compose.yml"
        relative = stack_dir.relative_to(REPO)
        prepare = stack_dir / "prepare-stack.sh"
        compose: dict[str, Any] = {}
        if compose_path.exists():
            compose_count += 1
            try:
                compose = load_compose(compose_path)
            except (OSError, yaml.YAMLError, ValueError) as exc:
                errors.append(f"{relative}: cannot inspect Compose YAML: {exc}")
                continue

        networks = literal_externals(compose.get("networks"))
        volumes = literal_externals(compose.get("volumes"))

        if not prepare.exists() and args.fix:
            prepare.write_text(STANDARD, encoding="utf-8")
            prepare.chmod(prepare.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            changed.append(f"{relative}: created prepare-stack.sh")

        if not prepare.exists():
            errors.append(f"{relative}: missing prepare-stack.sh")
            continue

        text = prepare.read_text(encoding="utf-8")
        repaired = insert_prerequisites(text, networks, volumes)
        if args.fix and repaired != text:
            prepare.write_text(repaired, encoding="utf-8")
            changed.append(f"{relative}: added external Docker prerequisites")
            text = repaired

        if not os.access(prepare, os.X_OK):
            if args.fix:
                prepare.chmod(
                    prepare.stat().st_mode
                    | stat.S_IXUSR
                    | stat.S_IXGRP
                    | stat.S_IXOTH
                )
                changed.append(f"{relative}: made prepare-stack.sh executable")
            else:
                errors.append(f"{relative}: prepare-stack.sh is not executable")

        required_tokens = (
            "prepare-stack-lib.sh",
            "prepare_stack_begin",
            "prepare_stack_end",
        )
        for token in required_tokens:
            if token not in text:
                errors.append(f"{relative}: missing verbose lifecycle token {token}")

        if (
            (stack_dir / "stack.env.example").exists()
            and "prepare_stack_copy_env" not in text
            and "stack.env.example" not in text
            and "stack.env.template" not in text
        ):
            errors.append(f"{relative}: stack.env.example is not prepared")
        if (
            (stack_dir / "caddy_snippet.conf.example").exists()
            and "prepare_stack_copy_caddy" not in text
            and "caddy_snippet.conf.example" not in text
            and "caddy_snippet.conf.template" not in text
        ):
            errors.append(f"{relative}: Caddy snippet example is not prepared")

        for name in networks:
            call = f'prepare_stack_ensure_docker_network "{name}"'
            if call not in text:
                errors.append(f"{relative}: external network '{name}' is not prepared")
        for name in volumes:
            call = f'prepare_stack_ensure_docker_volume "{name}"'
            if call not in text:
                errors.append(f"{relative}: external volume '{name}' is not prepared")

        known = {"stack.env.example", "caddy_snippet.conf.example"}
        extras = sorted(
            path.name
            for path in stack_dir.iterdir()
            if path.is_file()
            and (path.name.endswith(".example") or ".example." in path.name)
            and path.name not in known
            and path.name not in text
        )
        if extras:
            warnings.append(
                f"{relative}: review unmentioned optional example(s): {', '.join(extras)}"
            )

    for message in changed:
        print(f"FIX   {message}")
    for message in warnings:
        print(f"WARN  {message}")
    for message in errors:
        print(f"FAIL  {message}")
    print(
        f"Audited {len(stack_dirs)} stack directories ({compose_count} Compose): "
        f"{len(errors)} failure(s), {len(warnings)} warning(s), {len(changed)} change(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

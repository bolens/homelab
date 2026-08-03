#!/usr/bin/env python3
"""Validate portable examples, documentation links, and cross-file stack basics."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
import json

import yaml

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / "stacks"
PERSONAL_MARKERS = (
    re.compile(r"bolens\.dev", re.I),
    re.compile(r"/home/panda(?:/|$)", re.I),
    re.compile(r"/mnt/unraid(?:/|$)", re.I),
    re.compile(r"taild8bba", re.I),
    re.compile(r"America/Denver", re.I),
)
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MARKDOWN_LINK = re.compile(r"\[[^]]*]\(([^)]+)\)")
REVERSE_PROXY = re.compile(
    r"^\s*reverse_proxy\s+(?:https?://)?([A-Za-z0-9_.-]+)(?::\d+)?",
    re.MULTILINE,
)


def tracked(pathspec: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", pathspec],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def audit_markdown(errors: list[str]) -> None:
    docs = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "SECURITY.md"]
    docs.extend((ROOT / "documents").glob("*.md"))
    docs.extend((ROOT / "scripts").glob("*.md"))
    docs.append(ROOT / "portainer" / "README.md")
    for directory in sorted(path for path in STACKS.iterdir() if path.is_dir()):
        ignored = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(directory.relative_to(ROOT))],
            check=False,
        ).returncode == 0
        if not ignored:
            docs.append(directory / "README.md")
    for path in docs:
        if not path.exists():
            continue
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8", errors="replace")):
            local = target.split("#", 1)[0]
            if not local or "://" in local or local.startswith("mailto:"):
                continue
            if not (path.parent / local).resolve().exists():
                errors.append(f"{path.relative_to(ROOT)}: broken link {target}")


def audit_stack(directory: Path, errors: list[str], warnings: list[str]) -> None:
    name = directory.name
    readme = directory / "README.md"
    example = directory / "stack.env.example"
    metadata = directory / "stack.yaml"
    for required in (readme, example, metadata):
        if not required.exists():
            errors.append(f"{name}: missing {required.name}")
    if example.exists():
        for number, line in enumerate(example.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if line and not line.startswith("#") and not ENV_ASSIGNMENT.match(line):
                errors.append(f"{name}: stack.env.example:{number} is not a dotenv assignment")
            if ENV_ASSIGNMENT.match(line) and re.search(r"\s+#", line):
                errors.append(f"{name}: stack.env.example:{number} has an inline comment in its value")
            for marker in PERSONAL_MARKERS:
                if marker.search(line):
                    errors.append(f"{name}: stack.env.example:{number} contains a local marker")
    compose = directory / "docker-compose.yml"
    caddy = directory / "caddy_snippet.conf.example"
    if compose.exists() and caddy.exists():
        document = yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
        if document.get("include"):
            return
        service_map = document.get("services") or {}
        services = set(service_map.keys())
        services.update(
            value.get("container_name")
            for value in service_map.values()
            if isinstance(value, dict) and value.get("container_name")
        )
        for upstream in sorted(set(REVERSE_PROXY.findall(caddy.read_text(encoding="utf-8", errors="replace")))):
            if upstream not in services and upstream not in {"host.docker.internal", "localhost"}:
                warnings.append(f"{name}: Caddy upstream {upstream!r} is not a Compose service")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    private = tracked("**/stack.env") + tracked("**/.env")
    if private:
        errors.extend(f"tracked private environment file: {path}" for path in private)
    directories = []
    for path in sorted(path for path in STACKS.iterdir() if path.is_dir()):
        ignored = subprocess.run(
            ["git", "-C", str(ROOT), "check-ignore", "-q", str(path.relative_to(ROOT))],
            check=False,
        ).returncode == 0
        if not ignored:
            directories.append(path)
    for directory in directories:
        audit_stack(directory, errors, warnings)
    audit_markdown(errors)
    config_files = [
        ROOT / ".woodpecker.yml",
        ROOT / ".pre-commit-config.yaml",
        ROOT / ".yamllint.yml",
        *sorted((ROOT / ".github" / "workflows").glob("*.yml")),
        *sorted((ROOT / ".github" / "workflows").glob("*.yaml")),
    ]
    for path in config_files:
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid YAML: {exc}")
    renovate = ROOT / "renovate.json"
    try:
        json.loads(renovate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"renovate.json: invalid JSON: {exc}")
    for warning in warnings:
        print(f"WARN  {warning}")
    for error in errors:
        print(f"FAIL  {error}")
    print(
        f"Audited {len(directories)} stacks: "
        f"{len(errors)} failure(s), {len(warnings)} advisory warning(s)"
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

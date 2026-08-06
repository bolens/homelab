#!/usr/bin/env python3
"""Validate portable examples, documentation links, and cross-file stack basics."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
import json
from urllib.parse import unquote

import yaml

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / "stacks"
ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
ABSOLUTE_HOME = re.compile(r"/home/([^/$\s]+)/")
CONCRETE_MNT = re.compile(r"(?:^|[=:])(/mnt/[^,\s]+)")
TAILSCALE_HOST = re.compile(r"\b[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net\b", re.I)
DOMAIN_VALUE = re.compile(r"(?<!@)\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.I)
HOST_VARIABLE = re.compile(r"(?:URL|URI|DOMAIN|HOST|HOSTNAME|ORIGIN)$", re.I)
PLACEHOLDER_DOMAINS = ("example.com", "yourdomain.com", "host.docker.internal")
PLACEHOLDER_USERS = {"user", "you", "youruser", "example"}
MARKDOWN_LINK = re.compile(r"\[[^]]*]\(([^)]+)\)")
MARKDOWN_HEADING = re.compile(r"^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$")
MARKDOWN_EXPLICIT_ANCHOR = re.compile(
    r"""<(?:a|[A-Za-z][A-Za-z0-9-]*)\b[^>]*\b(?:id|name)=["']([^"']+)["']""",
    re.I,
)
REVERSE_PROXY = re.compile(
    r"^\s*reverse_proxy\s+(?:https?://)?([A-Za-z0-9_.-]+)(?::\d+)?",
    re.MULTILINE,
)
MAX_TRACKED_FILE_SIZE = 1024 * 1024
INTENTIONALLY_EMPTY = {
    "stacks/archisteamfarm/caddy_snippet.conf.example",
    "stacks/glance/assets/user.css",
    "stacks/grafana/provisioning_dashboards.example/json/.gitkeep",
    "stacks/node-red/caddy_snippet.conf.example",
}


def tracked(pathspec: str = ".") -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", pathspec],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def available_in_checkout(path: Path) -> bool:
    if not path.exists():
        return False
    return subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(path.relative_to(ROOT))],
        check=False,
    ).returncode != 0


def markdown_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    occurrences: dict[str, int] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    anchors.update(MARKDOWN_EXPLICIT_ANCHOR.findall(text))
    in_fence = False
    for line in text.splitlines():
        if re.match(r"^ {0,3}(```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = MARKDOWN_HEADING.match(line)
        if not match:
            continue
        heading = re.sub(r"<[^>]+>", "", match.group(1))
        heading = re.sub(r"[^\w\s-]", "", heading.lower(), flags=re.UNICODE)
        slug = re.sub(r"\s", "-", heading.strip())
        count = occurrences.get(slug, 0)
        occurrences[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def audit_markdown(errors: list[str]) -> None:
    docs = [ROOT / relative for relative in tracked("*.md")]
    for path in docs:
        if not path.exists():
            continue
        for target in MARKDOWN_LINK.findall(path.read_text(encoding="utf-8", errors="replace")):
            local, separator, fragment = target.partition("#")
            if not local or "://" in local or local.startswith("mailto:"):
                target_path = path if not local and separator else None
            else:
                target_path = (path.parent / unquote(local)).resolve()
            if target_path is None:
                continue
            if not available_in_checkout(target_path):
                errors.append(f"{path.relative_to(ROOT)}: broken link {target}")
                continue
            if fragment and target_path.suffix.lower() == ".md":
                anchor = unquote(fragment)
                if anchor not in markdown_anchors(target_path):
                    errors.append(f"{path.relative_to(ROOT)}: broken anchor {target}")


def audit_tracked_files(errors: list[str]) -> None:
    paths = tracked()
    case_paths: dict[str, str] = {}
    for relative in paths:
        path = ROOT / relative
        folded = relative.casefold()
        if folded in case_paths and case_paths[folded] != relative:
            errors.append(f"case-colliding paths: {case_paths[folded]} and {relative}")
        case_paths[folded] = relative
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_TRACKED_FILE_SIZE:
            errors.append(f"{relative}: tracked file exceeds 1 MiB ({size} bytes)")
        if size == 0 and relative not in INTENTIONALLY_EMPTY:
            errors.append(f"{relative}: unexpected empty tracked file")
        first_line = path.open("rb").readline(4096)
        executable = bool(path.stat().st_mode & 0o111)
        has_shebang = first_line.startswith(b"#!/")
        if has_shebang and not executable:
            errors.append(f"{relative}: has a shebang but is not executable")
        if executable and not has_shebang:
            errors.append(f"{relative}: is executable but has no shebang")


def local_assignment_reason(line: str) -> str | None:
    """Return why a dotenv assignment is machine-specific, if it is."""
    if not ENV_ASSIGNMENT.match(line):
        return None
    name, value = line.split("=", 1)
    value = value.strip().strip("\"'")
    home = ABSOLUTE_HOME.search(value)
    if home and home.group(1).lower() not in PLACEHOLDER_USERS:
        return "contains a concrete /home user path"
    if CONCRETE_MNT.search(value):
        return "contains a concrete /mnt path; use a root variable or /srv placeholder"
    if name == "TZ" and value and value not in {"UTC", "Etc/UTC"} and "${" not in value:
        return "uses a machine-specific timezone; examples should default to UTC"
    if TAILSCALE_HOST.search(value):
        return "contains a concrete Tailscale hostname"
    if HOST_VARIABLE.search(name) and DOMAIN_VALUE.search(value):
        lowered = value.lower()
        local_hostname = re.search(r"\b[a-z0-9-]+\.home(?::\d+)?(?:/|$)", lowered)
        if not local_hostname and not any(placeholder in lowered for placeholder in PLACEHOLDER_DOMAINS):
            return "contains a non-placeholder public domain"
    return None


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
            reason = local_assignment_reason(line)
            if reason:
                errors.append(f"{name}: stack.env.example:{number} {reason}")
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
    audit_tracked_files(errors)
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

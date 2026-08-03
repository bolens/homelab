#!/usr/bin/env python3
"""Render every public Compose stack with its portable example environment."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
STACKS = ROOT / "stacks"


def ignored(path: Path) -> bool:
    return subprocess.run(
        ["git", "-C", str(ROOT), "check-ignore", "-q", str(path.relative_to(ROOT))],
        check=False,
    ).returncode == 0


def main() -> int:
    if shutil.which("docker") is None:
        print("validate-compose-config.py: Docker CLI unavailable; skipped")
        return 0
    failures: list[str] = []
    skipped: list[str] = []
    checked = 0
    with tempfile.TemporaryDirectory(prefix="homelab-compose-validation-") as raw:
        temporary = Path(raw)
        shared = ROOT / "shared.env.example"
        if shared.exists():
            shutil.copy2(shared, temporary / "shared.env")
        for directory in sorted(path for path in STACKS.iterdir() if path.is_dir()):
            compose = directory / "docker-compose.yml"
            example = directory / "stack.env.example"
            if ignored(directory) or not compose.exists():
                continue
            metadata_path = directory / "stack.yaml"
            metadata = (
                yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
                if metadata_path.exists()
                else {}
            )
            if (metadata.get("lifecycle") or {}).get("status") == "external":
                skipped.append(f"{directory.name} (externally generated bundle)")
                continue
            document = yaml.safe_load(compose.read_text(encoding="utf-8")) or {}
            includes = document.get("include") or []
            missing_include = False
            for item in includes:
                include_path = item if isinstance(item, str) else item.get("path", "")
                if include_path and not (directory / include_path).exists():
                    missing_include = True
            if missing_include:
                skipped.append(f"{directory.name} (generated include bundle)")
                continue
            target = temporary / "stacks" / directory.name
            target.mkdir(parents=True)
            for service in (document.get("services") or {}).values():
                if not isinstance(service, dict) or not service.get("env_file"):
                    continue
                normalized = []
                for entry in service["env_file"]:
                    path = entry if isinstance(entry, str) else entry.get("path", "")
                    if str(path).endswith("shared.env"):
                        normalized.append(
                            {"path": "../../shared.env", "required": False}
                        )
                    else:
                        normalized.append("stack.env")
                service["env_file"] = normalized
            (target / compose.name).write_text(
                yaml.safe_dump(document, sort_keys=False),
                encoding="utf-8",
            )
            if example.exists():
                shutil.copy2(example, target / "stack.env")
                shutil.copy2(example, target / ".env")
            for item in includes:
                include_path = item if isinstance(item, str) else item.get("path", "")
                if include_path:
                    source = directory / include_path
                    destination = target / include_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "--env-file",
                    str(target / "stack.env"),
                    "-f",
                    str(target / compose.name),
                    "config",
                    "--quiet",
                ],
                cwd=target,
                capture_output=True,
                text=True,
                check=False,
            )
            checked += 1
            if result.returncode:
                detail = (result.stderr or result.stdout).strip().splitlines()
                failures.append(
                    f"{directory.name}: {detail[0] if detail else 'docker compose config failed'}"
                )
    for item in skipped:
        print(f"SKIP  {item}")
    for failure in failures:
        print(f"FAIL  {failure}")
    print(
        f"Rendered {checked} Compose stacks: "
        f"{len(failures)} failure(s), {len(skipped)} generated bundle(s) skipped"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

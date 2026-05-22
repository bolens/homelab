#!/usr/bin/env python3
"""
Parse docker-compose.yml files as YAML (syntax sanity check for CI).
Uses the same path rules as scripts/sync-compose-shared-env.py (no nested vendor trees).

Run from repo root:
  python3 scripts/ci-parse-composes.py
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError as e:
    print("ci-parse-composes.py: install PyYAML (e.g. apk add py3-pyyaml)", file=sys.stderr)
    raise SystemExit(1) from e

REPO = Path(__file__).resolve().parents[1]


def iter_compose_files() -> list[Path]:
    files: list[Path] = []
    stacks_root = REPO / "stacks"
    if stacks_root.is_dir():
        for child in sorted(stacks_root.iterdir()):
            if not child.is_dir():
                continue
            top = child / "docker-compose.yml"
            if top.is_file():
                files.append(top)
    portainer = REPO / "portainer" / "docker-compose.yml"
    if portainer.is_file():
        files.append(portainer)

    seen: set[Path] = set()
    out: list[Path] = []
    for p in files:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def main() -> int:
    paths = iter_compose_files()
    errors: list[tuple[Path, BaseException]] = []
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
            yaml.safe_load(text)
        except Exception as e:
            errors.append((path, e))
    if errors:
        for p, e in errors:
            print(f"ERROR {p.relative_to(REPO)}: {e}", file=sys.stderr)
        print(f"ci-parse-composes.py: {len(errors)} file(s) failed YAML parse", file=sys.stderr)
        return 1
    print(f"ci-parse-composes.py: OK ({len(paths)} compose files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Rewrite stacks/*/prepare-stack.sh to use scripts/prepare-stack-lib.sh with verbose output.
Safe to re-run: skips files that already source prepare-stack-lib.sh and call prepare_stack_begin.
"""
from __future__ import annotations

import re
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STACKS = REPO / "stacks"
LIB_PATH = "../../scripts/prepare-stack-lib.sh"

WRAPPER_TOP = f"""#!/usr/bin/env bash
# Prepare local files before first deploy. Safe to re-run: existing stack.env and caddy_snippet.conf are not overwritten.
# Verbose helpers: scripts/prepare-stack-lib.sh — see scripts/prepare-stack.examples/
set -euo pipefail

_PREPDIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
# shellcheck disable=SC1091
source "$_PREPDIR/{LIB_PATH}"

prepare_stack_begin "$_PREPDIR"
prepare_stack_copy_env
"""

WRAPPER_MID = """
prepare_stack_msg "stack-specific steps..."
"""

WRAPPER_BOTTOM = """
prepare_stack_copy_caddy
prepare_stack_end
"""


def _is_if_line(line: str) -> bool:
    s = line.lstrip()
    return s.startswith("if ") or s.startswith("if\t") or s.startswith("if[[")


def _if_depth_delta(line: str) -> int:
    s = line.strip()
    delta = 0
    if s.startswith("if ") or s.startswith("if[["):
        delta += 1
    if re.match(r"^fi(\s|$)", s):
        delta -= 1
    return delta


def find_fi_end(lines: list[str], start: int) -> int:
    depth = 0
    for j in range(start, len(lines)):
        depth += _if_depth_delta(lines[j])
        if depth == 0:
            return j
    return -1


def _chunk(lines: list[str], start: int, end: int) -> str:
    return "\n".join(lines[start : end + 1])


def is_stack_env_copy_block(lines: list[str], i: int) -> bool:
    if not _is_if_line(lines[i]):
        return False
    end = find_fi_end(lines, i)
    if end < 0:
        return False
    chunk = _chunk(lines, i, end)
    if "stack.env.example" in chunk:
        return True
    if re.search(r"cp\s+[\"']?stack\.env\.example", chunk):
        return True
    return False


def is_caddy_copy_block(lines: list[str], i: int) -> bool:
    if not _is_if_line(lines[i]):
        return False
    end = find_fi_end(lines, i)
    if end < 0:
        return False
    chunk = _chunk(lines, i, end)
    if "caddy_snippet" not in chunk:
        return False
    if "caddy_snippet.conf.example" in chunk or "cp " in chunk:
        return True
    return False


def strip_boilerplate(lines: list[str]) -> list[str]:
    """Remove shebang, set, cd, SCRIPT_DIR, env/caddy copy blocks, and related one-liners."""
    i = 0
    out: list[str] = []
    n = len(lines)

    while i < n:
        raw = lines[i]
        s = raw.strip()

        if s.startswith("#!"):
            i += 1
            continue
        if s.startswith("#") and any(
            x in s
            for x in (
                "Create stack.env",
                "Copy stack.env",
                "Prepare",
                "Prepare directories",
                "Copy Caddy",
                "Copy env example",
                "Run with:",
            )
        ):
            i += 1
            continue
        if s in ("set -e", "set -euo pipefail", "set -eu", "set -euo"):
            i += 1
            continue
        if s == "":
            i += 1
            continue

        if "SCRIPT_DIR=" in raw and "dirname" in raw:
            i += 1
            if i < n and lines[i].strip().startswith("cd "):
                i += 1
            continue
        if raw.strip().startswith("cd ") and "dirname" in raw:
            i += 1
            continue

        if is_stack_env_copy_block(lines, i):
            end = find_fi_end(lines, i)
            i = end + 1
            continue

        if is_caddy_copy_block(lines, i):
            end = find_fi_end(lines, i)
            i = end + 1
            continue

        # One-liners: [[ -f stack.env ]] || { cp stack.env.example ... }
        if "[[ -f stack.env" in s and "||" in s and "stack.env.example" in s:
            i += 1
            continue
        if "[[ -f caddy_snippet" in s and "||" in s and "caddy_snippet.conf.example" in s:
            i += 1
            continue

        # One-liners: [[ -f stack.env ]] || { cp ... }
        if re.match(r"^\[\[ -f stack\.env \]\] \|\| \{", s) and "stack.env.example" in s:
            i += 1
            continue
        if re.match(r"^\[\[ -f caddy_snippet\.conf \]\] \|\| \{", s):
            i += 1
            continue

        # One-liners: [[ -f stack.env ]] || { touch stack.env ... }  (keep — do not strip)

        out.append(raw.rstrip("\n"))
        i += 1

    while out and out[0].strip() == "":
        out.pop(0)
    while out and out[-1].strip() == "":
        out.pop()
    return out


def already_migrated(text: str) -> bool:
    return "prepare-stack-lib.sh" in text and "prepare_stack_begin" in text


def write_executable(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def main() -> None:
    seen: set[Path] = set()
    paths: list[Path] = []
    for p in sorted(STACKS.glob("*/prepare-stack.sh")):
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            paths.append(p)
    for p in sorted(STACKS.glob("**/prepare-stack.sh")):
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            paths.append(p)

    for path in paths:
        old = path.read_text(encoding="utf-8")
        if already_migrated(old):
            continue

        lines = old.splitlines()
        middle = strip_boilerplate(lines)

        if not middle:
            new_body = WRAPPER_TOP + WRAPPER_BOTTOM
        else:
            new_body = WRAPPER_TOP + WRAPPER_MID + "\n".join(middle) + "\n" + WRAPPER_BOTTOM

        write_executable(path, new_body)

    lib = REPO / "scripts" / "prepare-stack-lib.sh"
    write_executable(lib, lib.read_text(encoding="utf-8"))
    exdir = REPO / "scripts" / "prepare-stack.examples"
    if exdir.is_dir():
        for ex in sorted(exdir.glob("*.sh")):
            write_executable(ex, ex.read_text(encoding="utf-8"))

    subprocess.run(["bash", "-n", str(REPO / "scripts" / "prepare-stack-lib.sh")], check=True)
    subprocess.run(
        ["python3", str(REPO / "scripts" / "audit-prepare-scripts.py"), "--fix"],
        check=True,
    )


if __name__ == "__main__":
    main()

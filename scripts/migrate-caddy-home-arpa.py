#!/usr/bin/env python3
"""Add matching home.arpa labels beside .local Caddy site labels."""

from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path


LOCAL_SITE = re.compile(
    r"(?P<scheme>https?://)?(?P<name>[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]+)*)\.local(?P<port>:\d+)?$",
    re.IGNORECASE,
)


def migrate_line(raw_line: str) -> str:
    code, separator, comment = raw_line.partition("#")
    if "{" not in code:
        return raw_line
    labels, brace_and_body = code.split("{", 1)
    leading = labels[: len(labels) - len(labels.lstrip())]
    trailing = labels[len(labels.rstrip()) :]
    tokens = [token.strip() for token in labels.strip().split(",")]
    existing = {token.lower() for token in tokens}
    migrated: list[str] = []
    for token in tokens:
        migrated.append(token)
        match = LOCAL_SITE.fullmatch(token)
        if not match:
            continue
        home_arpa = (
            f"{match.group('scheme') or ''}{match.group('name')}.home.arpa"
            f"{match.group('port') or ''}"
        )
        if home_arpa.lower() not in existing:
            migrated.append(home_arpa)
            existing.add(home_arpa.lower())
    rebuilt = leading + ", ".join(migrated) + trailing + "{" + brace_and_body
    return rebuilt + (separator + comment if separator else "")


def migrate_text(text: str) -> str:
    return "".join(migrate_line(line) for line in text.splitlines(keepends=True))


def atomic_write(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write changes; default is a preview")
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="repository root",
    )
    args = parser.parse_args()
    paths = sorted((args.repo / "stacks").glob("*/caddy_snippet.conf"))
    changed: list[tuple[Path, str]] = []
    for path in paths:
        original = path.read_text()
        migrated = migrate_text(original)
        if migrated != original:
            changed.append((path, migrated))
    for path, content in changed:
        print(path.relative_to(args.repo))
        if args.apply:
            atomic_write(path, content)
    action = "updated" if args.apply else "would update"
    print(f"{action} {len(changed)} runtime Caddy snippets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

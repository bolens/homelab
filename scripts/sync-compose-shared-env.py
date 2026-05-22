#!/usr/bin/env python3
"""
Add optional repo-root shared.env to every service that uses stack.env in docker-compose.yml.
Normalize existing plain ../../shared.env entries to path + required: false.
Remove TZ/LANG/LC_ALL/LC_CTYPE from service environment (use shared.env + stack.env).

Run from docker/ repo root:
  python3 scripts/sync-compose-shared-env.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML

REPO = Path(__file__).resolve().parents[1]
LOCALE_KEYS = frozenset({"TZ", "LANG", "LC_ALL", "LC_CTYPE"})

yaml = YAML()
yaml.preserve_quotes = True
yaml.indent(mapping=2, sequence=4, offset=2)
yaml.width = 4096


def shared_env_relpath(compose_path: Path) -> str:
    rel = compose_path.parent.resolve().relative_to(REPO.resolve())
    return "/".join([".."] * len(rel.parts) + ["shared.env"])


def _as_list(env_file) -> list | None:
    if env_file is None:
        return None
    if isinstance(env_file, str):
        return [env_file]
    if isinstance(env_file, list):
        return env_file
    return None


def _entry_path(entry) -> str | None:
    if isinstance(entry, str):
        return entry
    if isinstance(entry, dict):
        return entry.get("path")
    return None


def _is_shared_entry(entry) -> bool:
    p = _entry_path(entry)
    return p is not None and p.endswith("shared.env")


def _is_stack_env_entry(entry) -> bool:
    p = _entry_path(entry)
    return p in ("stack.env", "./stack.env")


def _shared_optional_block(shared_rel: str) -> dict:
    return {"path": shared_rel, "required": False}


def normalize_env_file_list(raw: list, shared_rel: str) -> list | None:
    """Return new env_file list, or None if no stack.env (skip service)."""
    items = list(raw)
    has_stack = any(_is_stack_env_entry(x) for x in items)
    if not has_stack:
        return None

    # Drop plain or path-only shared entries; we'll prepend canonical optional block.
    filtered = [x for x in items if not _is_shared_entry(x)]

    # Re-find stack.env index
    out = []
    inserted = False
    for x in filtered:
        if not inserted and _is_stack_env_entry(x):
            out.append(_shared_optional_block(shared_rel))
            out.append("stack.env" if x == "./stack.env" else x)
            inserted = True
        else:
            out.append(x)
    if not inserted:
        return None
    return out


def strip_locale_from_environment(env) -> bool:
    if env is None:
        return False
    changed = False
    if isinstance(env, list):
        i = 0
        while i < len(env):
            item = env[i]
            if isinstance(item, str) and "=" in item:
                key = item.split("=", 1)[0].strip()
                if key in LOCALE_KEYS:
                    del env[i]
                    changed = True
                    continue
            i += 1
    elif isinstance(env, dict):
        for k in list(env.keys()):
            if str(k) in LOCALE_KEYS:
                del env[k]
                changed = True
    return changed


def _env_file_equal(a: list, b: list) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False
    return True


def process_compose(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    data = yaml.load(text)
    if not isinstance(data, dict) or "services" not in data:
        return False
    services = data["services"]
    if not isinstance(services, dict):
        return False

    shared_rel = shared_env_relpath(path)
    file_changed = False

    for _name, svc in services.items():
        if not isinstance(svc, dict):
            continue
        ef = svc.get("env_file")
        lst = _as_list(ef)
        if lst is None:
            continue
        new_lst = normalize_env_file_list(lst, shared_rel)
        if new_lst is None:
            continue
        if not _env_file_equal(new_lst, lst):
            svc["env_file"] = new_lst
            file_changed = True
        if strip_locale_from_environment(svc.get("environment")):
            file_changed = True

    if not file_changed:
        return False

    yaml.dump(data, path.open("w", encoding="utf-8"))
    return True


def main() -> int:
    """Only top-level stack compose files + portainer (no vendor trees)."""
    files: list[Path] = []
    stacks_root = REPO / "stacks"
    if stacks_root.is_dir():
        for child in sorted(stacks_root.iterdir()):
            if not child.is_dir():
                continue
            top = child / "docker-compose.yml"
            if top.is_file():
                files.append(top)
    portainer_compose = REPO / "portainer" / "docker-compose.yml"
    if portainer_compose.is_file():
        files.append(portainer_compose)

    seen: set[Path] = set()
    unique = []
    for p in files:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        unique.append(p)

    n = 0
    errors: list[tuple[Path, Exception]] = []
    for p in unique:
        try:
            if process_compose(p):
                n += 1
                print("updated", p.relative_to(REPO))
        except Exception as e:
            errors.append((p, e))
            print("ERROR", p.relative_to(REPO), e, file=sys.stderr)
    print("done,", n, "files modified")
    if errors:
        print(len(errors), "file(s) skipped due to YAML errors — fix compose syntax and re-run.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

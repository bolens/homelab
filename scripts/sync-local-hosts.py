#!/usr/bin/env python3
"""Reconcile active Caddy .local sites into Avahi and the host resolver."""

from __future__ import annotations

import argparse
import ipaddress
import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BEGIN = "# BEGIN docker-local (managed by sync-local-hosts)"
END = "# END docker-local"
LOCAL_RE = re.compile(
    r"(?i)(?:https?://)?([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9-]+)*\.local)(?::\d+)?$"
)


def run(command: list[str]) -> str:
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result.stdout


def active_stack_dirs(repo: Path | None) -> set[Path]:
    output = run(
        [
            "docker",
            "ps",
            "--filter",
            "label=com.docker.compose.project",
            "--format",
            '{{.Label "com.docker.compose.project.working_dir"}}',
        ]
    )
    directories: set[Path] = set()
    stacks = (repo / "stacks").resolve() if repo else None
    for value in output.splitlines():
        if not value.strip():
            continue
        path = Path(value.strip()).resolve()
        if stacks is None or path == stacks or stacks in path.parents:
            directories.add(path)
    return directories


def configured_stack_dirs(repo: Path) -> set[Path]:
    return {path.parent.resolve() for path in (repo / "stacks").glob("*/caddy_snippet.conf")}


def aliases_from_caddy(path: Path) -> set[str]:
    aliases: set[str] = set()
    for raw_line in path.read_text(errors="replace").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if "{" not in line:
            continue
        site_labels = line.split("{", 1)[0]
        for token in re.split(r"[\s,]+", site_labels):
            match = LOCAL_RE.fullmatch(token.strip())
            if match:
                aliases.add(match.group(1).lower())
    return aliases


def read_overrides(path: Path) -> tuple[set[str], set[str]]:
    includes: set[str] = set()
    excludes: set[str] = set()
    if not path.exists():
        return includes, excludes
    for number, raw_line in enumerate(path.read_text().splitlines(), 1):
        value = raw_line.split("#", 1)[0].strip().lower()
        if not value:
            continue
        exclude = value.startswith("-")
        value = value.lstrip("+-")
        if not value.endswith(".local"):
            value += ".local"
        if not LOCAL_RE.fullmatch(value):
            raise ValueError(f"{path}:{number}: invalid .local alias: {value}")
        (excludes if exclude else includes).add(value)
    return includes, excludes


def detect_ip(explicit: str | None, interface: str | None) -> str:
    if explicit:
        address = explicit
    elif interface:
        output = run(["ip", "-4", "-o", "addr", "show", "dev", interface, "scope", "global"])
        match = re.search(r"\binet\s+([0-9.]+)/", output)
        if not match:
            raise RuntimeError(f"no global IPv4 address found on {interface}")
        address = match.group(1)
    else:
        output = run(["ip", "-4", "route", "get", "1.1.1.1"])
        match = re.search(r"\bsrc\s+([0-9.]+)", output)
        if not match:
            raise RuntimeError("could not determine LAN IPv4; use --ip or --interface")
        address = match.group(1)
    parsed = ipaddress.ip_address(address)
    if parsed.version != 4 or parsed.is_loopback or parsed.is_link_local:
        raise ValueError(f"unsuitable advertisement address: {address}")
    return str(parsed)


def managed_content(original: str, entries: list[str]) -> str:
    block = "\n".join([BEGIN, *entries, END])
    # Accept the marker emitted by the old shell implementation during migration.
    pattern = re.compile(
        r"(?ms)^\s*# BEGIN docker-local(?: \(managed by sync-local-hosts\))?\n"
        r".*?^# END docker-local\s*\n?"
    )
    if pattern.search(original):
        updated = pattern.sub(block + "\n", original)
    else:
        separator = "" if not original or original.endswith("\n\n") else ("\n" if original.endswith("\n") else "\n\n")
        updated = original + separator + block + "\n"
    return updated


def atomic_write(path: Path, content: str) -> bool:
    old = path.read_text() if path.exists() else ""
    if old == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_stat = path.stat() if path.exists() else None
    mode = existing_stat.st_mode & 0o777 if existing_stat else 0o644
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if existing_stat and os.geteuid() == 0:
            os.chown(temporary, existing_stat.st_uid, existing_stat.st_gid)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return True


def desired_files(ip: str, aliases: set[str], avahi: Path, hosts: Path) -> dict[Path, str]:
    entries = [f"{ip}  {alias}" for alias in sorted(aliases)]
    avahi_original = avahi.read_text() if avahi.exists() else ""
    legacy_header = (
        "# Avahi static hosts - managed by scripts/sync-local-hosts.sh\n"
        "# Generated from local-hosts.conf. Do not edit by hand.\n"
    )
    if avahi_original.startswith(legacy_header):
        avahi_original = ""
    hosts_original = hosts.read_text() if hosts.exists() else ""
    legacy_footer_header = (
        "# .local entries from scripts/sync-local-hosts.sh (local-hosts.conf)\n"
        "# hblock appends this file when you run:"
    )
    if hosts_original.startswith(legacy_footer_header):
        hosts_original = ""
    return {
        avahi: managed_content(avahi_original, entries),
        hosts: managed_content(hosts_original, entries),
    }


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--print", action="store_true", dest="print_only", help="show desired entries (default)")
    mode.add_argument("--check", action="store_true", help="exit nonzero if files need reconciliation")
    mode.add_argument("--apply", action="store_true", help="atomically update Avahi and hosts files")
    result.add_argument("--all-configured", action="store_true", help="include every runtime Caddy snippet, not only running Compose projects")
    result.add_argument(
        "--repo",
        type=Path,
        default=Path(os.environ["MDNS_REPO_ROOT"]) if os.getenv("MDNS_REPO_ROOT") else None,
        help="optional repository root used to constrain discovery (env: MDNS_REPO_ROOT)",
    )
    result.add_argument("--ip", default=os.getenv("MDNS_IP"), help="IPv4 address to advertise (env: MDNS_IP)")
    result.add_argument("--interface", default=os.getenv("MDNS_INTERFACE"), help="interface whose IPv4 address to advertise (env: MDNS_INTERFACE)")
    result.add_argument("--overrides", type=Path, help="override file; +name includes and -name excludes")
    result.add_argument("--avahi-hosts", type=Path, default=Path("/etc/avahi/hosts"))
    result.add_argument("--system-hosts", type=Path, help="host target; default auto-detects hblock or uses /etc/hosts")
    result.add_argument("--hblock-config-dir", type=Path, help="hblock config directory (env: HBLOCK_CONFIG_DIR)")
    result.add_argument("--no-hblock", action="store_true", help="never auto-detect or run hblock")
    result.add_argument("--no-reload", action="store_true", help="do not reload Avahi after a change")
    return result


def find_hblock_config(explicit: Path | None) -> Path | None:
    configured = explicit or (
        Path(os.environ["HBLOCK_CONFIG_DIR"]) if os.getenv("HBLOCK_CONFIG_DIR") else None
    )
    if configured:
        candidates = [configured.expanduser()]
    else:
        candidates = [
            Path(account.pw_dir) / ".config/hblock"
            for account in pwd.getpwall()
            if account.pw_dir
        ]
    valid = sorted(
        {
            path.resolve()
            for path in candidates
            if (path / "sources.list").is_file()
            and (path / "allow.list").is_file()
            and (path / "footer.list").is_file()
        }
    )
    if configured and not valid:
        raise ValueError(f"incomplete hblock configuration: {configured}")
    if len(valid) > 1:
        raise ValueError(
            "multiple hblock configurations found; set HBLOCK_CONFIG_DIR or --hblock-config-dir"
        )
    return valid[0] if valid else None


def main() -> int:
    args = parser().parse_args()
    repo = args.repo.resolve() if args.repo else None
    try:
        if args.all_configured and repo is None:
            raise ValueError("--all-configured requires --repo or MDNS_REPO_ROOT")
        directories = configured_stack_dirs(repo) if args.all_configured else active_stack_dirs(repo)
        if repo is None:
            inferred = {
                directory.parent.parent
                for directory in directories
                if directory.parent.name == "stacks"
            }
            if len(inferred) == 1:
                repo = inferred.pop()
        overrides = args.overrides or (
            repo / "scripts/local-hosts.overrides"
            if repo
            else Path("/etc/sync-local-hosts.overrides")
        )
        aliases: set[str] = set()
        for directory in directories:
            snippet = directory / "caddy_snippet.conf"
            if snippet.is_file():
                aliases.update(aliases_from_caddy(snippet))
        includes, excludes = read_overrides(overrides)
        aliases = (aliases | includes) - excludes
        ip = detect_ip(args.ip, args.interface)
        hblock_config = None if args.no_hblock else find_hblock_config(args.hblock_config_dir)
        if (
            args.system_hosts
            and hblock_config
            and args.system_hosts.resolve() != (hblock_config / "footer.list").resolve()
        ):
            hblock_config = None
        system_hosts = args.system_hosts or (
            hblock_config / "footer.list" if hblock_config else Path("/etc/hosts")
        )
        files = desired_files(ip, aliases, args.avahi_hosts, system_hosts)
    except (OSError, RuntimeError, ValueError) as error:
        print(f"sync-local-hosts: {error}", file=sys.stderr)
        return 2

    entries = [f"{ip}  {alias}" for alias in sorted(aliases)]
    if args.print_only or not (args.check or args.apply):
        print(f"# {len(entries)} aliases from {len(directories)} stack directories; overrides: {overrides}")
        print("\n".join(entries))
        return 0

    different = [path for path, content in files.items() if not path.exists() or path.read_text() != content]
    if args.check:
        for path in different:
            print(f"needs update: {path}")
        return 1 if different else 0

    try:
        changed = [path for path, content in files.items() if atomic_write(path, content)]
    except OSError as error:
        print(f"sync-local-hosts: could not apply files: {error}", file=sys.stderr)
        return 2
    for path in changed:
        print(f"updated: {path}")
    if changed and not args.no_reload and shutil.which("systemctl"):
        result = subprocess.run(["systemctl", "reload-or-restart", "avahi-daemon.service"])
        if result.returncode:
            return result.returncode
    if system_hosts in changed and hblock_config:
        hblock = shutil.which("hblock")
        if not hblock:
            print("sync-local-hosts: hblock config found but hblock is not installed", file=sys.stderr)
            return 2
        result = subprocess.run(
            [
                hblock,
                "-S",
                str(hblock_config / "sources.list"),
                "-A",
                str(hblock_config / "allow.list"),
                "-O",
                "/etc/hosts",
                "-F",
                str(hblock_config / "footer.list"),
            ]
        )
        if result.returncode:
            return result.returncode
    if not changed:
        print("already current")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

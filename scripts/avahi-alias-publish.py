#!/usr/bin/env python3
"""Publish one mDNS alias for the IPv4 address of a LAN interface."""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} NAME.local INTERFACE", file=sys.stderr)
        return 2
    name, interface = sys.argv[1:]
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.local", name):
        print(f"invalid mDNS alias: {name}", file=sys.stderr)
        return 2
    result = subprocess.run(
        ["/usr/bin/ip", "-4", "-o", "addr", "show", "dev", interface, "scope", "global"],
        text=True,
        capture_output=True,
    )
    if result.returncode:
        print(result.stderr.strip(), file=sys.stderr)
        return result.returncode
    match = re.search(r"\binet\s+([0-9.]+)/", result.stdout)
    if not match:
        print(f"no global IPv4 address found on {interface}", file=sys.stderr)
        return 1
    address = str(ipaddress.ip_address(match.group(1)))
    os.execv(
        "/usr/bin/avahi-publish",
        ["avahi-publish", "-a", "-R", name, address],
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

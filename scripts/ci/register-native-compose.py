#!/usr/bin/env python3
"""CI-container-only registration of the verified Compose plugin for isolated configs."""
import argparse
import hashlib
import json
import os
from pathlib import Path

MANIFEST = Path(__file__).with_name('native-tools.json')


def register(tools, *, container_root=Path('/'), uid=None):
    """The root/uid seams are owned-directory fixtures; CLI has no target override."""
    uid = os.geteuid() if uid is None else uid
    marker = container_root / '.dockerenv'
    if (uid != 0 or not container_root.is_absolute() or container_root.resolve() != container_root
            or marker.is_symlink() or not marker.is_file()):
        raise ValueError('Compose registration requires a root Docker CI container')
    source = tools / 'docker-config/cli-plugins/docker-compose'
    if (not tools.is_absolute() or tools.resolve() != tools or source.is_symlink()
            or source.parent.resolve() != source.parent or not source.is_file()):
        raise ValueError('Compose source must be the regular verified scratch executable')
    expected = json.loads(MANIFEST.read_text())['tools']['compose']['sha256']
    digest = hashlib.sha256()
    with source.open('rb') as stream:
        while data := stream.read(1024 * 1024):
            digest.update(data)
    if digest.hexdigest() != expected or source.stat().st_mode & 0o7777 != 0o755:
        raise ValueError('Compose checksum or executable mode mismatch')
    target = container_root / 'usr/local/lib/docker/cli-plugins/docker-compose'
    parent = target.parent
    while parent != container_root:
        if parent.is_symlink() or parent.exists() and not parent.is_dir():
            raise ValueError('Compose system plugin directory is indirect or invalid')
        parent = parent.parent
    if target.exists() or target.is_symlink():
        if target.is_symlink() and os.readlink(target) == str(source):
            return
        raise ValueError('refuse to replace an existing system Compose plugin')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(source)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tools', type=Path, required=True)
    args = parser.parse_args()
    try:
        register(args.tools)
    except (OSError, ValueError) as error:
        parser.exit(1, f'CI Compose registration failed: {error}\n')


if __name__ == '__main__':
    main()

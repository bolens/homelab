#!/usr/bin/env python3
"""Install checksum-bound public CI tools into a new task-owned directory."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import tarfile
import time
import urllib.parse
import urllib.request
import zipfile

MANIFEST = Path(__file__).with_name('native-tools.json')
MAX_DOWNLOAD = 256 * 1024 * 1024
MAX_EXPANDED = 1024 * 1024 * 1024
HOSTS = {'github.com', 'nodejs.org', 'download.docker.com', 'storage.googleapis.com'}


def relative(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or '\0' in value:
        raise ValueError('unsafe tool archive path')
    return path


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        while data := source.read(1024 * 1024):
            result.update(data)
    return result.hexdigest()


def fetch(spec, target):
    url = urllib.parse.urlsplit(spec['url'])
    if (url.scheme != 'https' or url.hostname not in HOSTS or url.username is not None
            or url.password is not None or url.port not in (None, 443) or url.fragment
            or not re.fullmatch('[0-9a-f]{64}', spec['sha256'])):
        raise ValueError('invalid immutable tool source')
    request = urllib.request.Request(spec['url'], headers={'User-Agent': 'homelab-native-ci/1'})
    deadline = time.monotonic() + 180
    with urllib.request.urlopen(request, timeout=15) as response, target.open('xb') as output:
        final = urllib.parse.urlsplit(response.geturl())
        allowed = {url.hostname}
        if url.hostname == 'github.com':
            allowed.add('release-assets.githubusercontent.com')
        if final.scheme != 'https' or final.hostname not in allowed or final.username is not None:
            raise ValueError('tool redirect left the approved HTTPS origin')
        count = 0
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('tool download exceeded its time bound')
            data = response.read1(1024 * 1024)
            if not data:
                break
            count += len(data)
            if count > MAX_DOWNLOAD:
                raise ValueError('tool download exceeds its bound')
            output.write(data)
    if digest(target) != spec['sha256']:
        raise ValueError('tool checksum mismatch')


def install(archive, spec, destination):
    if digest(archive) != spec['sha256']:
        raise ValueError('tool checksum mismatch')
    if spec['format'] == 'zip':
        with zipfile.ZipFile(archive) as source:
            entries = source.infolist()
            if len(entries) > 2000 or sum(x.file_size for x in entries) > MAX_EXPANDED:
                raise ValueError('tool ZIP exceeds its expanded bound')
            names = [x.filename for x in entries]
            if len(names) != len(set(names)):
                raise ValueError('duplicate tool ZIP paths')
            for entry in entries:
                path = relative(entry.filename)
                if not path.parts or path.parts[0] != 'chrome-linux64':
                    raise ValueError('unexpected Chrome archive namespace')
                kind = stat.S_IFMT(entry.external_attr >> 16)
                if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
                    raise ValueError('tool ZIP links and devices are forbidden')
                target = destination / 'chrome' / path
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with source.open(entry) as data, target.open('xb') as output:
                        shutil.copyfileobj(data, output, 1024 * 1024)
                    # Never preserve setuid/ownership from a vendor archive.
                    target.chmod(0o755 if entry.external_attr >> 16 & 0o111 else 0o644)
        return
    target = destination / relative(spec['output'])
    target.parent.mkdir(parents=True, exist_ok=True)
    if spec['format'] == 'binary':
        with archive.open('rb') as data, target.open('xb') as output:
            shutil.copyfileobj(data, output, 1024 * 1024)
    elif spec['format'] == 'tar':
        with tarfile.open(archive, 'r:*') as source:
            members = []
            expanded = 0
            for count, entry in enumerate(source, 1):
                expanded += entry.size
                if count > 20000 or expanded > MAX_EXPANDED:
                    raise ValueError('tool TAR exceeds its expanded bound')
                if entry.name == spec['member']:
                    members.append(entry)
            if len(members) != 1 or not members[0].isfile() or members[0].size > MAX_DOWNLOAD:
                raise ValueError('tool TAR must contain one bounded regular executable')
            with source.extractfile(members[0]) as data, target.open('xb') as output:
                shutil.copyfileobj(data, output, 1024 * 1024)
    else:
        raise ValueError('unknown tool archive format')
    target.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, required=True)
    parser.add_argument('tools', nargs='+')
    args = parser.parse_args()
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('native tool pins support Linux amd64 only')
    specs = json.loads(MANIFEST.read_text())['tools']
    if len(args.tools) != len(set(args.tools)) or any(name not in specs for name in args.tools):
        parser.error('unknown or duplicate native tool')
    destination = args.destination
    if (not destination.is_absolute() or destination.exists() or destination.is_symlink()
            or destination.parent.resolve() != destination.parent):
        parser.error('use a new absolute tool directory in the task-owned scratch tree')
    destination.mkdir(mode=0o755)
    for name in args.tools:
        archive = destination / (name + '.download')
        fetch(specs[name], archive)
        install(archive, specs[name], destination)
        archive.unlink()
        print(f'verified {name} {specs[name]["version"]}', flush=True)


if __name__ == '__main__':
    main()

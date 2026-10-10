"""Test-only fixed comic gates: tracked public inputs, private disposable actors."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile

SCOPES = {'mylar': 'stacks/mylar3/config', 'worker': 'stacks/komga/normalizer'}
MOUNTS = {'mylar': Path('/fixes'), 'worker': Path('/app')}
MANIFEST = Path('/ci-source-map.json')
MAX_FILES = 4096
MAX_BYTES = 256 * 1024**2


def signature(path):
    s = path.lstat()
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns,
            s.st_mode, s.st_uid, s.st_gid, s.st_nlink)


def capture(source, names):
    files, nodes = {}, {}
    for name in names:
        rel = PurePosixPath(name)
        if (not name or rel.is_absolute() or '..' in rel.parts
                or str(rel) != name or '\\' in name or '\0' in name):
            raise ValueError('Unsafe public source path')
        p = source / name
        for q in (p.parent, *p.parent.parents):
            z = q.lstat()
            if not stat.S_ISDIR(z.st_mode) or q.is_symlink():
                raise ValueError('Public source ancestor is not a directory')
            fact = (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)
            if q in nodes and nodes[q] != fact:
                raise ValueError('Original public source ancestor changed during capture')
            nodes[q] = fact
        value = signature(p)
        if not stat.S_ISREG(value[5]) or value[8] != 1:
            raise ValueError('Public source is not a regular single-link file')
        files[p] = value
    if not 1 <= len(files) <= MAX_FILES or sum(v[2] for v in files.values()) > MAX_BYTES:
        raise ValueError('Public fixture size bound')
    return files, nodes


def close_originals(files, nodes):
    for p, v in nodes.items():
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != v:
            raise ValueError('Original public source ancestor changed')
    for p, v in files.items():
        z = os.lstat(p)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != v:
            raise ValueError('Original public source file changed')


def inventory(mode, output):
    root = Path(__file__).resolve().parents[1]
    scope = SCOPES[mode]
    names = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--', scope])
    paths = [Path(os.fsdecode(n)) for n in names.split(b'\0') if n]
    relative = [p.relative_to(scope).as_posix() for p in paths]
    source = root / scope
    files, nodes = capture(source, relative)
    rows = {}
    for name in relative:
        p = source / name
        rows[name] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                      'mode': stat.S_IMODE(files[p][5])}
    raw = json.dumps({'version': 1, 'mode': mode, 'files': rows}, sort_keys=True).encode()
    close_originals(files, nodes)
    with open(output, 'xb') as f:
        f.write(raw)


def copy_public(source, document, destination):
    if (set(document) != {'version', 'mode', 'files'} or type(document['version']) is not int
            or document['version'] != 1 or document['mode'] not in SCOPES
            or type(document['files']) is not dict):
        raise ValueError('Invalid public fixture inventory')
    rows = document['files']
    files, nodes = capture(source, rows)
    destination.mkdir(mode=0o700)
    for name, row in rows.items():
        if (type(row) is not dict or set(row) != {'sha256', 'mode'}
                or type(row['mode']) is not int or row['mode'] != stat.S_IMODE(files[source / name][5])):
            raise ValueError('Public fixture attributes differ')
        raw = (source / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row['sha256']:
            raise ValueError('Public fixture bytes differ')
        p = destination / name
        p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(p, 'xb') as f:
            f.write(raw)
        p.chmod(row['mode'])
        if p.read_bytes() != raw:
            raise ValueError('Private fixture readback differs')
    close_originals(files, nodes)
    return files, nodes


def command(mode, private):
    if mode == 'mylar':
        return [sys.executable, '-B', str(private / 'verify_image.py')]
    if mode == 'worker':
        return [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', str(private), '-p', 'test_*.py']
    raise ValueError('Unknown fixed control mode')


def run(mode):
    # The workflow/verifier owns this read-only inventory and fixed input mount.
    manifest = MANIFEST
    mf, mn = capture(manifest.parent, [manifest.name])
    raw = manifest.read_bytes()
    if len(raw) > MAX_BYTES:
        raise ValueError('Inventory size bound')
    document = json.loads(raw)
    if document.get('mode') != mode:
        raise ValueError('Wrong fixed source mode')
    with tempfile.TemporaryDirectory(prefix='comic-controls-private-') as temp:
        private = Path(temp) / 'source'
        files, nodes = copy_public(MOUNTS[mode], document, private)
        try:
            subprocess.run(command(mode, private), cwd=private, check=True,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
        finally:
            close_originals(files, nodes)
            close_originals(mf, mn)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('inventory', 'mylar', 'worker'))
    parser.add_argument('mode', nargs='?', choices=tuple(SCOPES))
    parser.add_argument('output', nargs='?')
    args = parser.parse_args()
    if args.action == 'inventory':
        if args.mode is None or args.output is None:
            parser.error('Inventory requires a fixed mode and an exclusive output file')
        inventory(args.mode, args.output)
    else:
        if args.mode is not None or args.output is not None:
            parser.error('Fixed control mode accepts no command or source arguments')
        run(args.action)


if __name__ == '__main__':
    main()

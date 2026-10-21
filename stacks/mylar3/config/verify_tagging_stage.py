"""Fixed build-only tagging gate; private copies confer no operational authority."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

SUITE = 'test_publication_tagging.py'
TESTS = 117
FILES = 90
MAX_BYTES = 16 * 1024**2
FLAGS = ('configured_acceptance', 'installed_factory_acceptance', 'NFS_acceptance', 'import_grant', 'ACK')
CHILD = """import importlib,json,sys,unittest
from pathlib import Path
root=Path(sys.argv[1]);suite=sys.argv[2]
sys.path.insert(0,str(root))
module=importlib.import_module(Path(suite).stem)
assert Path(module.__file__).absolute()==root/suite
result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromModule(module))
print('TAGGING_STAGE_RESULT='+json.dumps(dict(tests=result.testsRun,skips=len(result.skipped),failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful()),sort_keys=True),flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
"""


def need(value, code):
    if not value:
        raise ValueError(code)


def decode(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'duplicate-json-key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def nine(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def five(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


class Originals:
    def __init__(self):
        self.files = {}; self.nodes = {}

    def read(self, path):
        path = Path(path).absolute()
        need(path.resolve() == path, 'source-canonical')
        for parent in path.parents:
            z = parent.lstat()
            need(stat.S_ISDIR(z.st_mode), 'source-ancestor')
            need(self.nodes.setdefault(parent, five(z)) == five(z), 'source-ancestor-drift')
        z = path.lstat(); frame = nine(z)
        need(stat.S_ISREG(z.st_mode) and z.st_nlink == 1 and z.st_size <= 4 * 1024**2, 'source-regular-bound')
        need(self.files.setdefault(path, frame) == frame, 'source-drift')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            need(nine(os.fstat(fd)) == frame, 'source-open')
            with os.fdopen(os.dup(fd), 'rb') as stream:
                raw = stream.read(4 * 1024**2 + 1)
            need(len(raw) == frame[2] and nine(os.fstat(fd)) == frame == nine(path.lstat()), 'source-read-drift')
        finally:
            os.close(fd)
        return raw

    def close(self):
        for path, frame in self.files.items():
            need(nine(path.lstat()) == frame, 'source-final-drift')
        for path, frame in self.nodes.items():
            need(five(path.lstat()) == frame, 'source-ancestor-final-drift')


def manifest(document):
    need(type(document) is dict and set(document) == {'version', 'suite', 'tests', 'files'}
         and type(document['version']) is int and document['version'] == 1
         and document['suite'] == SUITE and type(document['tests']) is int and document['tests'] == TESTS,
         'fixed-manifest-schema')
    rows = document['files']
    need(type(rows) is list and len(rows) == FILES, 'fixed-source-census')
    for row in rows:
        need(type(row) is dict and set(row) == {'path', 'sha256'}
             and type(row['path']) is str and re.fullmatch('[A-Za-z_][A-Za-z0-9_]*[.]py', row['path'])
             and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}', row['sha256']), 'manifest-row')
    names = [row['path'] for row in rows]
    need(names == sorted(set(names)) and SUITE in names, 'manifest-unique-sorted')
    return rows


def inputs(sources, manifest_path, *, exact):
    sources = Path(sources).absolute(); witness = Originals()
    raw = witness.read(manifest_path); rows = manifest(decode(raw))
    need(sources.resolve() == sources and sources.is_dir(), 'source-directory')
    names = tuple(sorted(os.listdir(sources))) if exact else None
    if exact:
        need(names == tuple(row['path'] for row in rows), 'exact-source-namespace')
    payload = {row['path']: witness.read(sources / row['path']) for row in rows}
    need(sum(map(len, payload.values())) <= MAX_BYTES, 'source-total-bound')
    for row in rows:
        need(hashlib.sha256(payload[row['path']]).hexdigest() == row['sha256'], 'source-hash')
    witness.close()
    return witness, raw, rows, payload, names


def receipt(raw, rows):
    return dict(version=1, kind='mylar-tagging-build-only', suite=SUITE, tests=TESTS,
                skips=0, success=True, manifest_sha256=hashlib.sha256(raw).hexdigest(),
                files=rows, **{name: False for name in FLAGS})


def run_child(private, suite, expected):
    """Lower-level fixture seam; production always supplies fixed SUITE/TESTS."""
    need(Path(suite).name == suite and suite.endswith('.py') and type(expected) is int and expected > 0, 'child-selection')
    result = subprocess.run([sys.executable, '-I', '-B', '-c', CHILD, str(private), suite],
                            capture_output=True, text=True, timeout=1200,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    need(len(result.stdout.encode()) + len(result.stderr.encode()) <= 8 * 1024**2, 'child-output-bound')
    print(result.stdout, end='', flush=True); print(result.stderr, end='', file=sys.stderr, flush=True)
    lines = [line[len('TAGGING_STAGE_RESULT='):] for line in result.stdout.splitlines()
             if line.startswith('TAGGING_STAGE_RESULT=')]
    need(result.returncode == 0 and len(lines) == 1, 'tagging-child-failed')
    value = decode(lines[0])
    need(value == dict(tests=expected, skips=0, failures=0, errors=0, success=True)
         and all(type(value[k]) is int for k in ('tests', 'skips', 'failures', 'errors'))
         and value['success'] is True, 'tagging-child-count-or-skips')


def write_receipt(path, value):
    path = Path(path).absolute(); parent = path.parent
    need(parent.resolve() == parent and not os.path.lexists(path), 'receipt-output-absent')
    nodes = {p: five(p.lstat()) for p in (parent, *parent.parents)}
    need(all(stat.S_ISDIR(z[2]) for z in nodes.values()), 'receipt-output-ancestors')
    directory = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    try:
        need(five(os.fstat(directory)) == nodes[parent], 'receipt-parent-open')
        fd = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        try:
            with os.fdopen(os.dup(fd), 'wb') as stream:
                stream.write(raw); stream.flush()
            frame = nine(os.fstat(fd)); os.lseek(fd, 0, 0)
            need(os.read(fd, len(raw) + 1) == raw and frame == nine(os.fstat(fd)) == nine(path.lstat()), 'receipt-readback')
            need(stat.S_ISREG(frame[5]) and frame[8] == 1 and stat.S_IMODE(frame[5]) == 0o600, 'receipt-created-mode')
        finally:
            os.close(fd)
        need(five(os.fstat(directory)) == nodes[parent], 'receipt-parent-final')
        for p, original in nodes.items():
            need(five(p.lstat()) == original, 'receipt-output-closure')
    finally:
        os.close(directory)


def run_stage(sources, manifest_path, output):
    need(os.geteuid() == os.getegid() == 1000, 'tagging-fixture-uid')
    for name in ('/opt/archiving-utils/lib/archive_backend.py', '/opt/comictagger/bin/python', '/app/mylar3/comictagger.py'):
        need(Path(name).is_file(), 'genuine-tagging-runtime-required')
    need(os.environ.get('ARCHIVING_UTILS_ROOT') == '/opt/archiving-utils', 'genuine-sdk-path')
    witness, raw, rows, payload, names = inputs(sources, manifest_path, exact=True)
    primary = None
    try:
        with tempfile.TemporaryDirectory(prefix='mylar-tagging-private-') as directory:
            private = Path(directory)
            for name, content in payload.items():
                with (private / name).open('xb') as stream:
                    stream.write(content)
                (private / name).chmod(0o600)
                need((private / name).read_bytes() == content, 'private-copy-readback')
            witness.close()
            need(tuple(sorted(os.listdir(sources))) == names, 'source-prechild-namespace')
            run_child(private, SUITE, TESTS)
    except BaseException as error:
        primary = error
    try:
        witness.close()
        need(tuple(sorted(os.listdir(sources))) == names, 'source-final-namespace')
    except BaseException as closure:
        if primary is not None:
            raise primary from closure
        raise
    if primary is not None:
        raise primary
    write_receipt(output, receipt(raw, rows))
    witness.close()
    need(tuple(sorted(os.listdir(sources))) == names, 'source-postreceipt-namespace')


def verify_receipt(current_config_dir, receipt_path):
    root = Path(current_config_dir).absolute()
    witness, raw, rows, _, _ = inputs(root, root / 'tagging_stage_sources.json', exact=False)
    stored = decode(witness.read(receipt_path))
    need(stored == receipt(raw, rows) and type(stored.get('tests')) is int
         and type(stored.get('version')) is int and type(stored.get('skips')) is int
         and stored.get('success') is True and all(stored.get(name) is False for name in FLAGS), 'tagging-receipt-stale-or-malformed')
    witness.close()
    return stored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources')
    parser.add_argument('--manifest')
    parser.add_argument('--output')
    parser.add_argument('--verify-receipt', nargs=2, metavar=('CURRENT_CONFIG', 'RECEIPT'))
    args = parser.parse_args()
    if args.verify_receipt is not None:
        need(args.sources is None and args.manifest is None and args.output is None, 'exclusive-verification-mode')
        verify_receipt(*args.verify_receipt)
    else:
        need(all(value is not None for value in (args.sources, args.manifest, args.output)), 'stage-arguments-required')
        run_stage(args.sources, args.manifest, args.output)


if __name__ == '__main__':
    main()

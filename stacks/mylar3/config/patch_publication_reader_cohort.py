"""Copy pinned prospective helpers only; no parent pin or runtime initialization."""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

FIXES = Path(__file__).parent


def source_bytes(path, expected):
    vector = lambda z: (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns, z.st_mode, z.st_uid, z.st_gid, z.st_nlink)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError('Reader cohort requires regular single-link source')
    raw = path.read_bytes()
    if vector(path.lstat()) != vector(before) or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('Reader cohort source pin changed: ' + path.name)
    ast.parse(raw, feature_version=(3, 10))
    return raw


def main(directory):
    root = Path(directory)
    if not root.is_dir() or root.resolve() != root:
        raise ValueError('Reader cohort target must be an existing canonical package')
    manifest = json.loads((FIXES / 'publication_reader_cohort.json').read_text())
    if manifest['version'] != 1 or manifest['parent_sha256'] is not None:
        raise ValueError('Prospective reader cohort cannot claim a parent pin')
    checked = []
    for name, row in manifest['modules'].items():
        if row['filename'] != name + '.py':
            raise ValueError('Noncanonical reader cohort filename')
        raw = source_bytes(FIXES / row['filename'], row['sha256'])
        destination = root / row['filename']
        if destination.exists() or destination.is_symlink():
            source_bytes(destination, row['sha256'])
        elif row['already_installed']:
            raise ValueError('Existing owning adapter did not install ' + name)
        checked.append((destination, raw))
    # These helpers remain owned by their existing adapters. Some adapters
    # rewrite flat source imports, so source pins are provenance, not hashes
    # of their generated installed package bytes.
    for name in manifest['existing_sdk_closure']:
        installed = root / (name + '.py')
        info = installed.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError('Existing SDK dependency is unavailable: ' + name)
    for destination, raw in checked:
        if destination.exists():
            continue
        descriptor, temporary = tempfile.mkstemp(prefix='.reader-install-', dir=root)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
            os.chmod(temporary, 0o644)
            os.replace(temporary, destination)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)


if __name__ == '__main__':
    main(sys.argv[1])

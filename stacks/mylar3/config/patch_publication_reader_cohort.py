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
    if vector(path.lstat()) != vector(before):
        raise ValueError('Reader cohort source changed after parsing: ' + path.name)
    return raw


def main(directory):
    root = Path(directory)
    if not root.is_dir() or root.resolve() != root:
        raise ValueError('Reader cohort target must be an existing canonical package')
    manifest = json.loads((FIXES / 'publication_reader_cohort.json').read_text())
    if manifest['version'] != 1 or manifest['parent_sha256'] is not None:
        raise ValueError('Prospective reader cohort cannot claim a parent pin')
    checked = []
    replacements = {}
    for name, row in manifest['modules'].items():
        if row['filename'] != name + '.py':
            raise ValueError('Noncanonical reader cohort filename')
        raw = source_bytes(FIXES / row['filename'], row['sha256'])
        destination = root / row['filename']
        if destination.exists() or destination.is_symlink():
            original = destination.lstat()
            original9 = (original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns, original.st_ctime_ns, original.st_mode, original.st_uid, original.st_gid, original.st_nlink)
            try:
                source_bytes(destination, row['sha256'])
            except ValueError:
                predecessor = row.get('owned_predecessor_sha256')
                if name != 'publication_reader_admission' or predecessor != '01da4c355b804576e0a1b99a6e165cb47d607c511682945a9c47e3036064cfc7':
                    raise ValueError('Unknown installed reader predecessor: ' + name)
                source_bytes(destination, predecessor)
                info = destination.lstat()
                if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid, info.st_nlink) != original9:
                    raise ValueError('Owned predecessor changed during initial validation')
                replacements[destination] = (predecessor, original9)
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
        if destination.exists() and destination not in replacements:
            continue
        descriptor, temporary = tempfile.mkstemp(prefix='.reader-install-', dir=root)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(raw)
            os.chmod(temporary, 0o644)
            if destination in replacements:
                source_bytes(destination, replacements[destination][0])
                info = destination.lstat()
                if (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid, info.st_nlink) != replacements[destination][1]:
                    raise ValueError('Owned predecessor changed before replacement')
            elif destination.exists() or destination.is_symlink():
                raise ValueError('Reader target appeared during installation')
            os.replace(temporary, destination)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)


if __name__ == '__main__':
    main(sys.argv[1])

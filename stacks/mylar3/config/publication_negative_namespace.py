"""Load the fixed installed namespace mechanics from verified source bytes.

This module does not create a native publication capability or authorize a
filesystem transition. Owning phase and reader factories supply those checks.
"""
import hashlib
import os
from pathlib import Path
import stat
import types

KERNEL_PATH = Path('/app/mylar3/mylar/publication_negative_namespace_kernel.py')
KERNEL_SHA = 'f35887c5dad8985baf41fb5861423c18f556db1311f0e4fde202021f4cb59633'
MAX_SOURCE = 128 * 1024


class Held(ValueError):
    pass


def _check(value, reason):
    if not value:
        raise Held(reason)


def _signature(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def _node(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


def _load(path, digest):
    """Internal source reader, also exercised on explicit disposable fixtures."""
    path = Path(path)
    _check(path.is_absolute() and '..' not in path.parts, 'absolute-source')
    descriptors = []
    nodes = []
    try:
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        nodes.append((Path('/'), _node(os.fstat(fd))))
        parent = Path('/')
        for part in path.parts[1:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                         dir_fd=fd)
            descriptors.append(fd)
            parent = parent / part
            nodes.append((parent, _node(os.fstat(fd))))
        source = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        descriptors.append(source)
        original = _signature(os.fstat(source))
        _check(stat.S_ISREG(original[5]) and original[6] in (0, os.geteuid())
               and stat.S_IMODE(original[5]) in (0o600, 0o644)
               and original[8] == 1 and 0 < original[2] <= MAX_SOURCE,
               'source-attributes')
        raw = bytearray()
        while len(raw) <= MAX_SOURCE:
            block = os.read(source, min(65536, MAX_SOURCE + 1 - len(raw)))
            if not block:
                break
            raw.extend(block)
        _check(len(raw) == original[2]
               and hashlib.sha256(raw).hexdigest() == digest, 'source-pin')
        _check(_signature(os.fstat(source)) == original, 'source-descriptor')
        # Freeze expected vectors before executing the trusted pinned buffer.
        expected_nodes = tuple(nodes)
        module = types.ModuleType('mylar.publication_negative_namespace_kernel')
        module.__file__ = str(path)
        exec(compile(bytes(raw), str(path), 'exec'), module.__dict__)
        # These direct checks are last: imports or semantic helpers cannot
        # replace the admitted path after a successful terminal comparison.
        z = os.fstat(source)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != original:
            raise Held('terminal-source-descriptor')
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != original:
            raise Held('terminal-source-path')
        for parent, expected in expected_nodes:
            z = os.lstat(parent)
            if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != expected:
                raise Held('terminal-source-ancestor')
        return module
    except OSError as exc:
        raise Held('source-unavailable') from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def kernel():
    """Fixed installed source only. No caller path or recovery flag is accepted."""
    return _load(KERNEL_PATH, KERNEL_SHA)

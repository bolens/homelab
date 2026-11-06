"""Build-time normalization and read-only proof of Root-observed Native code."""
import argparse
import hashlib
import os
from pathlib import Path
import stat
import sys

PROTECTED_FILES = (
    'api.py', 'native_writers.py', 'publication_retained_api.py',
    'publication_retained_delivery.py', 'publication_retained_finalize.py',
)


def nine(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)


def node(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


def inspect_sources(root, *, normalize=False, owner=0):
    """Keep every original FD through both passes; normalization preserves bytes."""
    root = Path(root)
    assert root.is_absolute() and root.resolve() == root
    assert not normalize or os.geteuid() == owner, 'normalization owner'
    handles = []
    primary = None
    try:
        for path in (root, *root.parents):
            value = path.lstat()
            assert stat.S_ISDIR(value.st_mode)
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            handles.append((fd, path, nine(value)))
            assert node(os.fstat(fd)) == node(value) == node(path.lstat())
        root_fd = handles[0][0]
        files = []
        for name in PROTECTED_FILES:
            path = root / name
            value = path.lstat()
            assert stat.S_ISREG(value.st_mode) and value.st_nlink == 1
            assert value.st_uid == owner and 0 < value.st_size <= 4 * 1024**2
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
            handles.append((fd, path, nine(value)))
            assert nine(os.fstat(fd)) == nine(value)
            raw = os.pread(fd, value.st_size + 1, 0)
            assert len(raw) == value.st_size and nine(os.fstat(fd)) == nine(value) == nine(path.lstat())
            if not normalize:
                assert not value.st_mode & 0o022, name
            files.append((fd, path, nine(value), hashlib.sha256(raw).hexdigest()))
        # Every callback boundary closes all current incarnations, including
        # leaves not yet normalized. A reused later FD must never reach chmod.
        expected = {fd: frame for fd, _, frame, _ in files}
        directories = handles[:1 + len(root.parents)]

        def close_originals():
            for fd, path, frame in directories:
                original = tuple(frame[i] for i in (0, 1, 5, 6, 7))
                assert node(os.fstat(fd)) == original == node(path.lstat())
            for fd, path, _, _ in files:
                assert nine(os.fstat(fd)) == expected[fd] == nine(path.lstat())

        close_originals()
        for fd, path, frame, digest in files:
            close_originals()
            if normalize and stat.S_IMODE(frame[5]) != 0o644:
                os.fchmod(fd, 0o644)
                current = nine(os.fstat(fd))
                assert current == nine(path.lstat())
                assert all(current[i] == frame[i] for i in (0, 1, 2, 3, 6, 7, 8))
                assert stat.S_IMODE(current[5]) == 0o644
                expected[fd] = current
                close_originals()
                os.fsync(fd)
                close_originals()
            assert not expected[fd][5] & 0o022
            assert not normalize or stat.S_IMODE(expected[fd][5]) == 0o644
            assert hashlib.sha256(os.pread(fd, expected[fd][2] + 1, 0)).hexdigest() == digest
            close_originals()
        for fd, _, _, digest in files:
            assert hashlib.sha256(os.pread(fd, expected[fd][2] + 1, 0)).hexdigest() == digest
        # No reads or mutations follow this final metadata/namespace closure.
        close_originals()
        rows = {path.name: dict(signature9=list(expected[fd]), sha256=digest)
                for fd, path, _, digest in files}
        return rows
    except BaseException as error:
        primary = error
        raise
    finally:
        failures = []
        for fd, _, frame in reversed(handles):
            try:
                assert nine(os.fstat(fd))[:2] == frame[:2], 'foreign descriptor'
                os.close(fd)
            except BaseException as error:
                failures.append(error)
        if failures:
            if primary is None:
                raise failures[0]
            message = 'Protected-source cleanup: ' + ','.join(type(e).__name__ for e in failures)
            try:
                note = getattr(primary, 'add_note', None)
                if callable(note):
                    note(message)
                else:
                    print(message, file=sys.stderr)
            except BaseException:
                pass  # Secondary reporting cannot replace the primary refusal.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--normalize', action='store_true')
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    assert sys.dont_write_bytecode
    rows = inspect_sources(args.root, normalize=args.normalize)
    print('Protected Native image sources verified: ' + str(len(rows)))


if __name__ == '__main__':
    main()

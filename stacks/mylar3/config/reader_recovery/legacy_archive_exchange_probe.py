"""Legacy exchange platform diagnostic, never a plan13 gate or integration pass.

Run only on an explicitly supplied disposable grandparent outside every
protected library. Creates two tiny private files in a new exclusive directory;
no application, library, image or service is read or changed. A rejected syscall
is retained in the returned evidence and exits nonzero. No local-FS fallback.
"""
import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess


class Held(ValueError):
    pass


def canonical(value):
    path = Path(value)
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise Held('platform-canonical-path-required')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise Held('platform-symlink')
    if not path.is_dir():
        raise Held('platform-directory-required')
    return path


def mount_identity(path):
    result = subprocess.run(['findmnt', '--json', '--target', str(path), '--output',
                             'SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN'],
                            capture_output=True, timeout=30, check=True)
    value = json.loads(result.stdout)
    rows = value.get('filesystems')
    if type(rows) is not list or len(rows) != 1 or rows[0].get('fstype') != 'nfs4':
        raise Held('platform-actual-nfs4-required')
    row = rows[0]
    if set(row) != {'source', 'target', 'fstype', 'fsroot', 'options', 'maj:min'}:
        raise Held('platform-exact-mount-identity-required')
    return row


def probe_exchange(grandparent):
    """Test the exact owning syscall flags on two exclusive non-library files.

    This establishes only platform support, without constructing a capability.
    Cleanup verifies exact expected bytes, file identities and namespace first.
    Any unexpected state retains the entire probe directory for inspection.
    """
    grandparent = canonical(grandparent)
    directory = grandparent / ('.comic-exchange-prerequisite-' + secrets.token_hex(16))
    directory.mkdir(mode=0o700)
    dirfd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    originals = {}
    try:
        for name, raw in (('source', b'original\n'), ('stage', b'derivative\n')):
            fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dirfd)
            try:
                os.write(fd, raw)
                os.fsync(fd)
                z = os.fstat(fd)
                originals[name] = (z.st_dev, z.st_ino, raw)
            finally:
                os.close(fd)
        libc = ctypes.CDLL(None, use_errno=True)
        fn = getattr(libc, 'renameat2', None)
        if fn is None:
            raise Held('platform-renameat2-unavailable-probe-retained')
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        fn.restype = ctypes.c_int
        ctypes.set_errno(0)
        result = fn(dirfd, b'source', dirfd, b'stage', 2)
        error = ctypes.get_errno() if result else 0
        if set(os.listdir(directory)) != {'source', 'stage'}:
            raise Held('platform-probe-namespace-changed-retained')
        for name in ('source', 'stage'):
            original = originals[('stage' if name == 'source' else 'source') if result == 0 else name]
            z = os.stat(name, dir_fd=dirfd, follow_symlinks=False)
            if (z.st_dev, z.st_ino) != original[:2] or not stat.S_ISREG(z.st_mode) or z.st_nlink != 1:
                raise Held('platform-probe-file-changed-retained')
            fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=dirfd)
            try:
                if os.read(fd, 100) != original[2]:
                    raise Held('platform-probe-bytes-changed-retained')
            finally:
                os.close(fd)
        for name in ('source', 'stage'):
            os.unlink(name, dir_fd=dirfd)
        os.fsync(dirfd)
        directory.rmdir()
        return dict(version=1, kind='legacy-archive-exchange-platform-diagnostic', exchange_supported=result == 0,
                    errno=error, errno_name=errno.errorcode.get(error), owned_probe_removed=True,
                    runtime_acceptance=False, birth_verified=False, terminal_ack_verified=False)
    finally:
        os.close(dirfd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--disposable-grandparent', required=True)
    parser.add_argument('--library', required=True, help='exact disposable library, checked read-only for mount identity')
    parser.add_argument('--protected-root', action='append', required=True)
    args = parser.parse_args()
    grandparent, library = map(canonical, (args.disposable_grandparent, args.library))
    protected = [canonical(value) for value in args.protected_root]
    if library not in protected:
        raise Held('platform-library-must-be-protected')
    if any(grandparent == root or grandparent in root.parents or root in grandparent.parents for root in protected):
        raise Held('platform-probe-protected-overlap')
    if mount_identity(grandparent) != mount_identity(library):
        raise Held('platform-original-library-nfs-mount-differs')
    result = probe_exchange(grandparent)
    print(json.dumps(result, sort_keys=True))
    return 0 if result['exchange_supported'] else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (Held, OSError, subprocess.SubprocessError, ValueError):
        # Paths, mount source addresses and syscall diagnostics stay private.
        print('archive-platform-prerequisite-held; integration-unproved')
        raise SystemExit(2)

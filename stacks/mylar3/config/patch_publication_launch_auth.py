"""Build-only exact public verifier installation; no deployment or key provisioning."""
import hashlib
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).parent / 'standalone_launch_auth'
SOURCES = {name: digest.removeprefix('sha256:') for name, digest in {
    'standalone_launch_auth.py': 'sha256:fd871556d6af8741623f94e760a9e2e838cddeb087ee3a4d15a9e4412842a5a8',
    'v3_auth_core.py': 'sha256:b8c688bcf6b40e12c54eba5793cc368079b1050d20ed11170deaeb721ac99c93',
    'private_crypto.py': 'sha256:3d888b7155f47b9ae35d99aafd845e0bdaa37cda6cd75ddc91103a02836a6fab',
}.items()}


def full(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def node(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


def security(z):
    if z.st_uid != 0 or z.st_gid != 0 or z.st_mode & 0o022:
        raise ValueError('Auth installation requires root-owned non-writable originals')


def verify_installed(directory):
    target = Path(directory).absolute()
    if target.name != 'auth':
        raise ValueError('Auth destination basename')
    files = {}; nodes = {}
    for path in (target, *target.parents):
        z = os.lstat(path); security(z)
        if not stat.S_ISDIR(z.st_mode): raise ValueError('Auth directory original')
        nodes[path] = node(z)
    if set(os.listdir(target)) != set(SOURCES) or set(os.listdir(target.parent)) != {'auth'}:
        raise ValueError('Auth public-only namespace')
    for name in SOURCES:
        path = target / name; z = os.lstat(path); security(z)
        if not stat.S_ISREG(z.st_mode) or z.st_nlink != 1 or stat.S_IMODE(z.st_mode) != 0o444:
            raise ValueError('Auth readonly regular original')
        files[path] = full(z)
    for name, digest in SOURCES.items():
        path = target / name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if full(os.fstat(fd)) != files[path]: raise ValueError('Auth original FD')
            data = bytearray()
            while chunk := os.read(fd, 65536):
                data.extend(chunk)
                if len(data) > 1024**2: raise ValueError('Auth source bound')
            if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Auth installed byte pin')
            if full(os.fstat(fd)) != files[path]: raise ValueError('Auth original FD final')
        finally:
            os.close(fd)
    if set(os.listdir(target)) != set(SOURCES) or set(os.listdir(target.parent)) != {'auth'}:
        raise ValueError('Auth final public-only namespace')
    for path, original in nodes.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != original:
            raise ValueError('Auth final original ancestor')
    for path, original in files.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != original:
            raise ValueError('Auth final original installed source')


def main(directory):
    # Generic apply_patches never calls this installer. Docker supplies the one
    # fixed image destination; source tests use disposable explicit destinations.
    target = Path(directory).absolute()
    if target.name != 'auth' or not target.parent.parent.is_dir():
        raise ValueError('Auth destination parent')
    files = {}; nodes = {}; destinations = {}; payloads = {}
    for name in SOURCES:
        path = ROOT / name; z = os.lstat(path)
        if not stat.S_ISREG(z.st_mode) or z.st_nlink != 1: raise ValueError('Auth regular source')
        files[path] = full(z)
        for ancestor in (path.parent, *path.parent.parents):
            z = os.lstat(ancestor)
            if not stat.S_ISDIR(z.st_mode): raise ValueError('Auth source directory')
            fact = node(z)
            if ancestor in nodes and nodes[ancestor] != fact: raise ValueError('Auth ancestor conflict')
            nodes[ancestor] = fact
    for path in (target, *target.parents):
        if os.path.lexists(path):
            z = os.lstat(path); security(z)
            if not stat.S_ISDIR(z.st_mode): raise ValueError('Auth destination directory')
            fact = node(z)
            if path in nodes and nodes[path] != fact: raise ValueError('Auth ancestor conflict')
            nodes[path] = fact
    if set(os.listdir(ROOT)) != set(SOURCES): raise ValueError('Auth exact source namespace')
    if target.parent.exists() and set(os.listdir(target.parent)) != ({'auth'} if target.exists() else set()):
        raise ValueError('Auth public-only namespace')
    if target.exists() and set(os.listdir(target)) != set(SOURCES): raise ValueError('Auth existing exact namespace')
    for name, digest in SOURCES.items():
        destination = target / name
        destinations[destination] = full(os.lstat(destination)) if os.path.lexists(destination) else None
    for name, digest in SOURCES.items():
        path = ROOT / name; fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            if full(os.fstat(fd)) != files[path]: raise ValueError('Auth source FD')
            data = bytearray()
            while chunk := os.read(fd, 65536):
                data.extend(chunk)
                if len(data) > 1024**2: raise ValueError('Auth source bound')
            if full(os.fstat(fd)) != files[path]: raise ValueError('Auth source FD final')
        finally:
            os.close(fd)
        if hashlib.sha256(data).hexdigest() != digest: raise ValueError('Auth source byte pin')
        payloads[target / name] = bytes(data)
    # Sources and all original destination leaves are captured before reading.
    for path, original in files.items():
        if full(os.lstat(path)) != original: raise ValueError('Auth source original changed')
    for path, original in destinations.items():
        if (full(os.lstat(path)) if os.path.lexists(path) else None) != original:
            raise ValueError('Auth destination original changed')
        if original is not None and (original[5] & 0o170000 != 0o100000 or original[8] != 1 or
                                     original[5] & 0o7777 != 0o444 or path.read_bytes() != payloads[path]):
            raise ValueError('Auth unknown installed predecessor')
    for path, original in nodes.items():
        if node(os.lstat(path)) != original: raise ValueError('Auth source ancestor changed')
    for directory in (target.parent, target):
        if not directory.exists():
            os.mkdir(directory, 0o755)
            z = os.lstat(directory); security(z)
            if not stat.S_ISDIR(z.st_mode) or stat.S_IMODE(z.st_mode) != 0o755:
                raise ValueError('Auth created directory')
            nodes[directory] = node(z)
    for path, data in payloads.items():
        if destinations[path] is not None: continue
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o444)
        try:
            birth = full(os.fstat(fd)); security(os.fstat(fd))
            if birth[5] & 0o170000 != 0o100000 or birth[5] & 0o7777 != 0o444 or birth[6:9] != (os.geteuid(), os.getegid(), 1):
                raise ValueError('Auth created readonly original')
            view = memoryview(data)
            while view:
                count = os.write(fd, view)
                if count <= 0: raise ValueError('Auth short write')
                view = view[count:]
            os.fsync(fd);result = full(os.fstat(fd))
            if result[:2] + result[5:] != birth[:2] + birth[5:] or result[2] != len(data) or full(os.lstat(path)) != result:
                raise ValueError('Auth created source changed')
            destinations[path] = result
        finally:
            os.close(fd)
    verify_installed(target)
    # All hash/read/verification helpers precede retained original source closure.
    if set(os.listdir(ROOT)) != set(SOURCES) or set(os.listdir(target)) != set(SOURCES) or set(os.listdir(target.parent)) != {'auth'}:
        raise ValueError('Auth final exact public namespace')
    for path, original in nodes.items():
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid) != original:
            raise ValueError('Auth final original ancestor')
    for path, original in (*files.items(), *destinations.items()):
        z = os.lstat(path)
        if (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
                z.st_mode, z.st_uid, z.st_gid, z.st_nlink) != original:
            raise ValueError('Auth final original source')


if __name__ == '__main__': main(sys.argv[1])

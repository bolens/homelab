"""Finite DDL cache allocation admission; retained originals are never deleted."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import stat
import threading

GIB = 1024 ** 3
DEFAULT_MAX_GIB = 20
DEFAULT_FREE_GIB = 5
MAX_ENTRIES = 1000000
BLOCK = 4096
_LOCAL = threading.Lock()


class Held(ValueError):
    """Allocation is unavailable; this is not a provider failure or import ACK."""


def setting(value):
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value.strip())
    if type(value) is not int or not 1 <= value <= 4096:
        raise ValueError('Cache settings require whole GiB from 1 through 4096')
    return value


def validate_update(values):
    for key in ('DDL_CACHE_MAX_GIB', 'DDL_CACHE_MIN_FREE_GIB'):
        supplied = [value for name, value in values.items() if name.upper() == key]
        if len(supplied) > 1:
            raise ValueError('Duplicate cache setting')
        if supplied:
            setting(supplied[0])


def configured():
    import mylar
    cfg = mylar.CONFIG
    try:
        maximum = setting(getattr(cfg, 'DDL_CACHE_MAX_GIB', DEFAULT_MAX_GIB)) * GIB
        reserve = setting(getattr(cfg, 'DDL_CACHE_MIN_FREE_GIB', DEFAULT_FREE_GIB)) * GIB
    except ValueError:
        raise Held('Invalid finite cache configuration') from None
    data = Path(mylar.DATA_DIR).absolute()
    cache = Path(cfg.CACHE_DIR).absolute()
    ddl = Path(cfg.DDL_LOCATION or cfg.CACHE_DIR).absolute()
    roots = tuple(sorted({cache, ddl}, key=lambda p: (len(p.parts), str(p))))
    roots = tuple(p for p in roots if not any(q != p and q in p.parents for q in roots))
    for p in (data, *roots):
        if p.resolve(strict=True) != p or not p.is_dir():
            raise Held('Cache roots must be original canonical directories')
    return data, roots, maximum, reserve


def identity(z):
    return (z.st_dev, z.st_ino, z.st_size, z.st_mtime_ns, z.st_ctime_ns,
            z.st_mode, z.st_uid, z.st_gid, z.st_nlink)


def directory_identity(z):
    return (z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid)


def open_directory(path):
    """Open each canonical component relative to its original nofollow parent."""
    path = Path(path).absolute()
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    nodes = {Path('/'): directory_identity(os.fstat(fd))}
    current = Path('/')
    try:
        for name in path.parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
            os.close(fd); fd = child; current /= name
            nodes[current] = directory_identity(os.fstat(fd))
        for name, expected in nodes.items():
            if directory_identity(os.lstat(name)) != expected:
                raise Held('Original cache ancestor changed')
        return fd, nodes
    except BaseException:
        os.close(fd)
        raise


def usage(roots):
    """FD-relative census; a switched directory cannot become a followed link."""
    seen = set(); count = 0; originals = {}; namespaces = {}; ancestors = {}
    def walk(fd, path, depth=0):
        if depth > 128:
            raise Held('Cache census exceeds its finite depth bound')
        nonlocal count
        before = identity(os.fstat(fd))
        names = tuple(sorted(os.listdir(fd)))
        originals[path] = before; namespaces[path] = names
        total = os.fstat(fd).st_blocks * 512
        for name in names:
            z = os.stat(name, dir_fd=fd, follow_symlinks=False)
            count += 1
            if count > MAX_ENTRIES:
                raise Held('Cache census exceeds its finite entry bound')
            originals[path / name] = identity(z)
            key = (z.st_dev, z.st_ino)
            if key in seen:
                continue
            seen.add(key)
            if stat.S_ISDIR(z.st_mode):
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                try:
                    if identity(os.fstat(child)) != identity(z):
                        raise Held('Cache directory changed during census')
                    total += walk(child, path / name, depth + 1)
                    if identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity(z):
                        raise Held('Cache directory changed during census')
                finally:
                    os.close(child)
            elif stat.S_ISREG(z.st_mode) or stat.S_ISLNK(z.st_mode):
                total += max(z.st_size, z.st_blocks * 512)
                if identity(os.stat(name, dir_fd=fd, follow_symlinks=False)) != identity(z):
                    raise Held('Cache inode changed during census')
            else:
                raise Held('Unsupported cache inode')
        # Fresh original-relative OFD, rather than a retained directory cursor.
        check = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
        try:
            if tuple(sorted(os.listdir(check))) != names or identity(os.fstat(fd)) != before:
                raise Held('Cache namespace changed during census')
        finally:
            os.close(check)
        return total
    opened = []
    try:
        for root in roots:
            fd, nodes = open_directory(root)
            opened.append((root, fd, identity(os.fstat(fd)), nodes))
            ancestors.update(nodes)
        total = sum(walk(fd, root) for root, fd, _, _ in opened)
        for root, fd, expected, nodes in opened:
            for name, expected5 in nodes.items():
                if directory_identity(os.lstat(name)) != expected5:
                    raise Held('Cache ancestor changed during census')
            if identity(os.fstat(fd)) != expected or identity(os.lstat(root)) != expected:
                raise Held('Cache root changed during census')
    finally:
        for _, fd, _, _ in opened:
            os.close(fd)
    # Reclose the complete detached census after traversal/FD cleanup: a later
    # entry callback must not alter a previously counted inode unnoticed.
    for path, expected in namespaces.items():
        fd, _ = open_directory(path)
        try:
            if tuple(sorted(os.listdir(fd))) != expected:
                raise Held('Cache namespace changed during census')
        finally: os.close(fd)
    for path, expected in originals.items():
        if identity(os.lstat(path)) != expected:
            raise Held('Cache original changed during census')
    for path, expected in ancestors.items():
        if directory_identity(os.lstat(path)) != expected:
            raise Held('Cache ancestor changed during census')
    return total


def rounded(value):
    return ((value + BLOCK - 1) // BLOCK) * BLOCK


class Allocation:
    def __init__(self, destination, required=None, nodes=0):
        self.destination = Path(destination).absolute()
        if required is not None and (type(required) is not int or required < 0):
            raise Held('Invalid projected cache allocation')
        if type(nodes) is not int or nodes < 0 or nodes > MAX_ENTRIES:
            raise Held('Invalid projected cache inode count')
        self.required = required
        self.overhead = nodes * BLOCK
        self.fd = None
        self.dirfd = None
        self.local = False
        self.consumed = 0
        self.lock_path = None
        self.lock9 = None
        self.destination5 = None
        self.data5 = None
        self.datafd = None
        self.nodes = {}

    def __enter__(self):
        if not _LOCAL.acquire(blocking=False):
            raise Held('Cache allocation is already reserved')
        self.local = True
        try:
            data, self.roots, self.maximum, self.reserve = configured()
            if (self.destination.resolve(strict=True) != self.destination
                    or not any(self.destination == p or p in self.destination.parents for p in self.roots)):
                raise Held('Allocation is outside configured cache roots')
            self.data = data
            self.datafd, self.nodes = open_directory(data)
            self.data5 = directory_identity(os.fstat(self.datafd))
            self.lock_path = data / 'cache-admission-v1.lock'
            self.fd = os.open(self.lock_path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.datafd)
            z = os.fstat(self.fd)
            if not stat.S_ISREG(z.st_mode) or z.st_nlink != 1 or z.st_uid != os.geteuid() or stat.S_IMODE(z.st_mode) != 0o600:
                raise Held('Cache allocation lock is not private and original')
            self.lock9 = identity(z)
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Held('Cache allocation is already reserved') from None
            self.dirfd, destination_nodes = open_directory(self.destination)
            self.nodes.update(destination_nodes)
            self.destination5 = directory_identity(os.fstat(self.dirfd))
            if self.destination5 != directory_identity(os.lstat(self.destination)):
                raise Held('Original cache destination changed')
            self.used = usage(self.roots)
            self._check(self.required or 0)
            return self
        except BaseException as exc:
            self.__exit__(None, None, None)
            if isinstance(exc, OSError):
                raise Held('Original cache state unavailable') from None
            raise

    def originals(self):
        for name, expected in self.nodes.items():
            if directory_identity(os.lstat(name)) != expected:
                raise Held('Original cache reservation ancestor changed')
        if (identity(os.fstat(self.fd)) != self.lock9 or identity(os.lstat(self.lock_path)) != self.lock9
                or directory_identity(os.fstat(self.dirfd)) != self.destination5
                or directory_identity(os.lstat(self.destination)) != self.destination5
                or directory_identity(os.lstat(self.data)) != self.data5):
            raise Held('Original cache reservation changed')

    def _check(self, projected, free_growth=None):
        self.originals()
        growth = rounded(projected) + self.overhead
        if growth == 0:
            return  # Existing-only recovery does not allocate cache bytes.
        if self.used + growth > self.maximum:
            raise Held('Cache byte budget reached; retained originals require owning recovery')
        z = os.fstatvfs(self.dirfd)
        required_free = growth if free_growth is None else rounded(free_growth) + self.overhead
        if z.f_bavail * z.f_frsize < self.reserve + required_free:
            raise Held('Cache filesystem free-space reserve reached')

    def before_write(self, amount):
        if type(amount) is not int or amount < 0:
            raise Held('Invalid cache write size')
        projected = self.consumed + amount
        if self.required is not None and projected > self.required:
            raise Held('Transfer exceeds its reserved size')
        remaining = amount if self.required is None else self.required - self.consumed
        self._check(projected, remaining)
        self.consumed = projected

    def __exit__(self, *_):
        failure = None
        try:
            if self.dirfd is not None and self.lock9 is not None:
                self.originals()
        except BaseException as exc:
            failure = exc
        finally:
            if self.dirfd is not None:
                os.close(self.dirfd); self.dirfd = None
            if self.fd is not None:
                os.close(self.fd); self.fd = None
            if self.datafd is not None:
                os.close(self.datafd); self.datafd = None
            if self.local:
                _LOCAL.release(); self.local = False
        if self.destination5 is not None:
            for name, expected in self.nodes.items():
                if directory_identity(os.lstat(name)) != expected:
                    raise Held('Original cache reservation ancestor changed')
            if (directory_identity(os.lstat(self.destination)) != self.destination5
                    or directory_identity(os.lstat(self.data)) != self.data5
                    or identity(os.lstat(self.lock_path)) != self.lock9):
                raise Held('Original cache reservation changed')
        if failure is not None:
            raise failure


@contextmanager
def allocation(destination, required=None, nodes=0):
    with Allocation(destination, required, nodes) as reservation:
        yield reservation


class Temporary:
    """Mega's original-relative cache temporary; failed plaintext stays retained."""
    def __init__(self, reservation):
        import secrets
        reservation.originals()
        self.reservation = reservation
        self.leaf = 'megapy_' + secrets.token_hex(16)
        self.name = str(reservation.destination / self.leaf)
        fd = os.open(self.leaf, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=reservation.dirfd)
        self.file = os.fdopen(fd, 'w+b')
        self.birth = os.fstat(self.file.fileno())
        self.promoted = False
        self.output = None

    def __enter__(self):
        return self

    def write(self, chunk):
        self.reservation.originals()
        z = os.stat(self.leaf, dir_fd=self.reservation.dirfd, follow_symlinks=False)
        if (z.st_dev, z.st_ino) != (self.birth.st_dev, self.birth.st_ino) or z.st_nlink != 1 or not stat.S_ISREG(z.st_mode):
            raise Held('Original Mega temporary changed')
        return self.file.write(chunk)

    def close(self):
        # Mega calls close before promotion; keep its original FD until link custody
        # is checked, and actually close it in the enclosing context cleanup.
        self.file.flush()
        os.fsync(self.file.fileno())

    def promote(self, filename, expected):
        self.close(); self.reservation.originals()
        if (not isinstance(filename, str) or Path(filename).name != filename
                or filename in ('', '.', '..') or '/' in filename or '\\' in filename):
            raise Held('Unsafe Mega destination name')
        z = os.fstat(self.file.fileno())
        if z.st_size != expected or z.st_nlink != 1 or identity(os.stat(self.leaf, dir_fd=self.reservation.dirfd, follow_symlinks=False)) != identity(z):
            raise Held('Incomplete or changed Mega temporary')
        # Atomic no-overwrite same-directory promotion. A conflicting original is
        # retained unchanged; neither shutil.move nor os.replace can overwrite it.
        os.link(self.leaf, filename, src_dir_fd=self.reservation.dirfd,
                dst_dir_fd=self.reservation.dirfd, follow_symlinks=False)
        linked = os.stat(filename, dir_fd=self.reservation.dirfd, follow_symlinks=False)
        if (linked.st_dev, linked.st_ino) != (z.st_dev, z.st_ino) or linked.st_nlink != 2:
            raise Held('Mega promotion identity changed')
        os.unlink(self.leaf, dir_fd=self.reservation.dirfd)
        self.output = self.reservation.destination / filename
        self.promoted = True
        return self.output

    def __exit__(self, *_):
        self.file.close()
        self.reservation.originals()
        current = self.output if self.promoted else Path(self.name)
        z = os.lstat(current)
        if (z.st_dev, z.st_ino) != (self.birth.st_dev, self.birth.st_ino) or not stat.S_ISREG(z.st_mode) or z.st_nlink != 1:
            raise Held('Original Mega output changed')


def temporary(reservation):
    return Temporary(reservation)

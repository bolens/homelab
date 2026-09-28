"""Explicit in-place publication results; legacy temporary paths remain strings.

Native automatic imports must never consume an in-place result as a temporary file.
Native producers and consumers import only mylar.tagger_handoff. Foreign or
unknown result objects fail closed. No backend selection or tagging is enabled.
"""
from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
import stat

MAX_ARCHIVE = 4 * 1024 ** 3
SUCCESS = {'committed', 'unchanged'}


class Failure(str):
    """Native automatic callers keep their legacy 'fail' sentinel and reason."""
    def __new__(cls, state):
        value = super().__new__(cls, 'fail')
        value.state = state if state in ('failed', 'timed_out', 'unsupported', 'conflict') else 'failed'
        return value


@dataclass(frozen=True)
class Published:
    state: str
    metadata: str = ''
    path: str = field(default='', repr=False)
    digest: str = field(default='', repr=False)
    identity: tuple = field(default=(), repr=False)
    permissions: tuple = field(default=(), repr=False)

    def valid_for(self, source):
        """Verify the exact expected caller source before bypassing native cleanup."""
        if (not isinstance(self.state, str) or not isinstance(self.metadata, str)
                or self.state not in SUCCESS or self.metadata not in ('added', 'updated', 'unchanged')):
            return False
        try:
            expected = Path(source).absolute()
            if (str(expected) != self.path or expected.anchor != '/' or '..' in expected.parts
                    or any(p.is_symlink() for p in (expected, *expected.parents))):
                return False
            fd = os.open(expected, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as stream:
                info = os.fstat(stream.fileno())
                stamp = (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                        or info.st_size > MAX_ARCHIVE or stamp != self.identity
                        or (stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid) != self.permissions
                        or os.listxattr(expected, follow_symlinks=False)):
                    return False
                digest = hashlib.sha256()
                remaining = info.st_size
                while remaining:
                    data = stream.read(min(1024 * 1024, remaining))
                    if not data:
                        return False
                    digest.update(data)
                    remaining -= len(data)
                def identity(value):
                    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns,
                            value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink)
                extra = stream.read(1)
                final = os.fstat(stream.fileno())
                current = expected.lstat()
                return (not extra and digest.hexdigest() == self.digest
                        and identity(final) == identity(info) == identity(current))
        except (OSError, ValueError, TypeError):
            return False


def capture(publisher, token):
    """Build a handoff only from a reconciled durable publisher receipt."""
    result = publisher.recover(token)
    if result.state not in SUCCESS:
        return Published(result.state)
    record = publisher.read(token)
    if not record['cleaned'] or record['state'] != result.state:
        return Published('conflict')
    committed = result.state == 'committed'
    value = Published(result.state, result.metadata, record['source'],
                      record['after'] if committed else record['before'],
                      tuple(record['candidate_identity' if committed else 'source_identity'][:4]),
                      tuple(record['permissions']))
    return value if value.valid_for(record['source']) else Published('conflict')


def automatic(value):
    """Automatic placement owns temporary paths, never an in-place source."""
    if not isinstance(value, str):
        raise RuntimeError('In-place tagger result cannot enter automatic placement')
    return value

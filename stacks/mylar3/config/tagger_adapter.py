"""Inactive CBZ publication owner with private, versioned crash-recovery receipts.

Callers must exclude non-cooperating writers. Atomic exchange retains the displaced
file even if a writer races the last check; uncertain contents are never discarded.
No conversion, native caller integration or automatic retry. The displaced source
is removed only after a verified commit has been durably recorded.
"""
from contextlib import contextmanager
import ctypes
import errno
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import time
import zipfile
import zlib

from tagger_archive import MAX_UNPACKED, identity, prepare, regular, snapshot
from tagger_cli import save, VERSION

TERMINAL = {'committed', 'unchanged', 'failed', 'timed_out', 'unsupported'}
HEX = re.compile(r'[0-9a-f]{32}\Z')


@dataclass(frozen=True)
class Result:
    state: str
    metadata: str = ''
    # Paths, raw errors, command arguments and metadata stay out of the result.


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fingerprint(path):
    with regular(path) as stream:
        before = os.fstat(stream.fileno())
        if before.st_size > MAX_UNPACKED:
            raise ValueError('Oversized source')
        digest = hashlib.sha256()
        received = 0
        while block := stream.read(1024 * 1024):
            received += len(block)
            if received > before.st_size:
                raise ValueError('Source grew while hashing')
            digest.update(block)
        if identity(before) != identity(os.fstat(stream.fileno())) or identity(before) != identity(Path(path).lstat()):
            raise ValueError('File changed')
        return digest.hexdigest()


def exchange(left, right):
    """Linux atomic exchange; unsupported filesystems fail without a fallback."""
    library = ctypes.CDLL(None, use_errno=True)
    try:
        call = library.renameat2
    except AttributeError as error:
        raise OSError(errno.ENOSYS, 'Atomic exchange unavailable') from error
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(-100, os.fsencode(left), -100, os.fsencode(right), 2):
        raise OSError(ctypes.get_errno(), 'Archive exchange failed')


def _checkpoint(stage):
    """Failure-injection seam used by fixture subprocess crash tests."""


class Publisher:
    def __init__(self, directory):
        self.root = Path(directory).absolute()
        if '..' in self.root.parts or any(p.is_symlink() for p in (self.root, *self.root.parents)):
            raise ValueError('Linked journal directory')
        self.root.mkdir(mode=0o700, exist_ok=True)
        info = self.root.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise ValueError('Expected private owned journal')
        sync(self.root.parent)

    def receipt(self, token):
        if not isinstance(token, str) or not HEX.fullmatch(token):
            raise ValueError('Invalid operation token')
        return self.root / (token + '.json')

    def read(self, token):
        path = self.receipt(token)
        with regular(path) as stream:
            raw = stream.read(1048577)
        if len(raw) > 1048576:
            raise ValueError('Oversized journal')
        value = json.loads(raw)
        if value.get('version') != 1 or value.get('token') != token:
            raise ValueError('Unsupported journal')
        return value

    def write(self, value):
        path = self.receipt(value['token'])
        temporary = path.with_suffix('.new')
        data = json.dumps(value, ensure_ascii=True, allow_nan=False).encode()
        if len(data) > 1048576:
            raise ValueError('Oversized journal')
        # A stale .new is private and never replaces the last durable .json.
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        sync(self.root)

    @contextmanager
    def lock(self, source):
        key = hashlib.sha256(os.fsencode(source)).hexdigest()
        fd = os.open(self.root / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Invalid lock')
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    def workspace(self, record):
        source = Path(record['source'])
        expected = source.parent / ('.mylar-tag-' + record['token'])
        if not source.is_absolute() or '..' in source.parts or any(p.is_symlink() for p in source.parents):
            raise ValueError('Invalid source ancestry')
        info = expected.lstat()
        if not stat.S_ISDIR(info.st_mode) or list(identity(info)[:2]) != record['workspace']:
            raise ValueError('Workspace identity changed')
        return expected

    def finish(self, record, state, *, cleanup=True):
        if cleanup and state in ('failed', 'timed_out', 'unchanged'):
            try:
                source = Path(record['source'])
                intact = (fingerprint(source) == record['before']
                          and list(identity(source.lstat())) == record['source_identity'])
            except (OSError, ValueError):
                intact = False
            if not intact:
                state, cleanup = 'conflict', False
        record.update(state=state, updated=time.time())
        self.write(record)  # Terminal state is durable before removing any copy.
        if cleanup and state in TERMINAL:
            folder = self.workspace(record)
            shutil.rmtree(folder)
            sync(folder.parent)
            record['cleaned'] = True
            self.write(record)
        return Result(state, record.get('metadata', '') if state in ('committed', 'unchanged') else '')

    def recover(self, token):
        self.receipt(token)
        with self.lock('token:' + token):
            record = self.read(token)
            with self.lock(record['source']):
                return self._recover(self.read(token))

    def _recover(self, record):
        source = Path(record['source'])
        try:
            if record['state'] in TERMINAL:
                if record['state'] in ('committed', 'unchanged'):
                    expected = record['after'] if record['state'] == 'committed' else record['before']
                    if fingerprint(source) != expected:
                        # A newer job/operator can supersede a completed receipt.
                        # Do not turn cleaned history into a blocking active owner.
                        return Result('conflict') if record.get('cleaned') else self.finish(record, 'conflict', cleanup=False)
                if not record.get('cleaned'):
                    folder = source.parent / ('.mylar-tag-' + record['token'])
                    if folder.exists():
                        self.workspace(record)
                        return self.finish(record, record['state'])
                    record['cleaned'] = True
                    self.write(record)
                return Result(record['state'], record.get('metadata', '') if record['state'] in ('committed', 'unchanged') else '')
            folder = self.workspace(record)
            if record['state'] == 'publishing':
                output = folder / 'verified.cbz'
                current, displaced = fingerprint(source), fingerprint(output)
                # Compare both bytes and inodes; rename changes ctime.
                swapped = (current == record['after'] and displaced == record['before']
                           and list(identity(source.lstat())[:4]) == record['candidate_identity'][:4]
                           and list(identity(output.lstat())[:4]) == record['source_identity'][:4]
                           and [stat.S_IMODE(source.stat().st_mode), source.stat().st_uid,
                                source.stat().st_gid] == record['permissions']
                           and output.stat().st_nlink == 1)
                if swapped:
                    sync(source.parent)
                    sync(folder)
                    return self.finish(record, 'committed')
                untouched = (current == record['before'] and displaced == record['after']
                             and list(identity(source.lstat())) == record['source_identity'])
                if untouched:
                    return self.finish(record, 'failed')
                return self.finish(record, 'conflict', cleanup=False)
            if record['state'] == 'conflict':
                return Result('conflict')
            if fingerprint(source) != record['before']:
                return self.finish(record, 'conflict', cleanup=False)
            return self.finish(record, 'failed')  # Never replay an interrupted CLI.
        except (OSError, ValueError, KeyError, TypeError):
            if record.get('cleaned') and record['state'] in TERMINAL:
                return Result('conflict')
            return self.finish(record, 'conflict', cleanup=False)

    def tag(self, source, metadata, *, token, updates=None, replace_fields=(), executable=None):
        source = Path(source).absolute()
        replace_fields = tuple(replace_fields)
        if source.suffix.lower() != '.cbz' or '..' in source.parts or any(p.is_symlink() for p in (source, *source.parents)):
            return Result('unsupported')
        request = hashlib.sha256(json.dumps([str(source), metadata, updates, list(replace_fields)],
                                           sort_keys=True, allow_nan=False).encode()).hexdigest()
        path = self.receipt(token)
        # A token belongs to exactly one request, even across different sources.
        # Keep this order in recover too to prevent token/source lock inversion.
        with self.lock('token:' + token), self.lock(source):
            if path.exists() or path.is_symlink():
                record = self.read(token)
                if record['source'] != str(source) or record['request'] != request:
                    return Result('conflict')
                return self._recover(record)
            # Stream retained receipts rather than imposing a lifetime job quota.
            for journal in self.root.glob('*.json'):
                other = self.read(journal.stem)
                if other['source'] == str(source) and (other['state'] not in TERMINAL or not other.get('cleaned')):
                    return Result('conflict')
            folder = source.parent / ('.mylar-tag-' + token)
            record = None
            try:
                old = snapshot(source)
                if source.stat().st_nlink != 1 or os.listxattr(source, follow_symlinks=False):
                    return Result('unsupported')  # Do not silently sever links/ACLs.
                before = fingerprint(source)
                if identity(source.lstat()) != old.identity:
                    return Result('conflict')
                if shutil.disk_usage(source.parent).free < old.identity[2] * 3 + 16 * 1024 ** 2:
                    return Result('failed')
                folder.mkdir(mode=0o700)
                sync(folder.parent)
                record = dict(version=1, token=token, source=str(source), request=request,
                              backend=VERSION, before=before, source_identity=list(old.identity),
                              permissions=[old.mode, old.uid, old.gid],
                              workspace=list(identity(folder.stat())[:2]), state='staged', cleaned=False)
                self.write(record)
                original, tagged, output = (folder / name for name in ('original.cbz', 'tagged.cbz', 'verified.cbz'))
                with regular(source) as reader, original.open('xb') as writer:
                    remaining = old.identity[2]
                    while remaining:
                        block = reader.read(min(1024 * 1024, remaining))
                        if not block:
                            raise ValueError('Source shrank while staging')
                        writer.write(block)
                        remaining -= len(block)
                    if reader.read(1):
                        raise ValueError('Source grew while staging')
                    writer.flush()
                    os.fchown(writer.fileno(), old.uid, old.gid)
                    os.fchmod(writer.fileno(), old.mode)
                    os.fsync(writer.fileno())
                if fingerprint(original) != before or identity(source.lstat()) != old.identity:
                    return self.finish(record, 'conflict', cleanup=False)
                shutil.copyfile(original, tagged)
                _checkpoint('staged')
                options = {'executable': executable} if executable else {}
                result = save(tagged, metadata, workdir=folder, **options)
                if result.state != 'saved':
                    return self.finish(record, 'timed_out' if result.state == 'timed_out' else 'failed')
                record['metadata'] = prepare(original, tagged, output, updates=updates, replace_fields=replace_fields)
                if identity(source.lstat()) != old.identity or fingerprint(source) != before:
                    return self.finish(record, 'conflict', cleanup=False)
                if record['metadata'] == 'unchanged':
                    return self.finish(record, 'unchanged')
                record.update(state='publishing', after=fingerprint(output),
                              candidate_identity=list(identity(output.stat())))
                sync(folder)
                self.write(record)
                _checkpoint('before_exchange')
                if identity(source.lstat()) != old.identity:
                    return self.finish(record, 'conflict', cleanup=False)
                exchange(source, output)
                _checkpoint('after_exchange')
                return self._recover(record)
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, zlib.error, EOFError):
                if record:
                    return self._recover(record)
                return Result('failed')

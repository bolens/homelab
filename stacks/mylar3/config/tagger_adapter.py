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

if __package__:
    from .tagger_archive import MAX_UNPACKED, identity, prepare, regular, snapshot
    from .tagger_cli import save, VERSION
else:
    from tagger_archive import MAX_UNPACKED, identity, prepare, regular, snapshot
    from tagger_cli import save, VERSION

TERMINAL = {'committed', 'unchanged', 'failed', 'timed_out', 'unsupported'}
HEX = re.compile(r'[0-9a-f]{32}\Z')
HASH = re.compile(r'[0-9a-f]{64}\Z')
STATES = TERMINAL | {'staged', 'publishing', 'conflict'}


@dataclass(frozen=True)
class Result:
    state: str
    metadata: str = ''
    # Paths, raw errors, command arguments and metadata stay out of the result.


@dataclass(frozen=True)
class RecoveryResult:
    token: str
    state: str
    metadata: str = ''


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
        if self.root.anchor != '/' or '..' in self.root.parts or any(p.is_symlink() for p in (self.root, *self.root.parents)):
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
        try:
            value = json.loads(raw)
        except RecursionError as error:
            raise ValueError('Overnested journal') from error
        def integers(name, length, signed_tail=0):
            field = value.get(name)
            return (isinstance(field, list) and len(field) == length
                    and all(type(n) is int for n in field)
                    and all(n >= 0 for n in field[:length-signed_tail]))
        def digest(name):
            field = value.get(name)
            return isinstance(field, str) and HASH.fullmatch(field) is not None
        if not isinstance(value, dict):
            raise ValueError('Invalid journal')
        source = value.get('source')
        if (type(value.get('version')) is not int or value['version'] != 1 or value.get('token') != token
                or not isinstance(value.get('state'), str) or value['state'] not in STATES
                or type(value.get('cleaned')) is not bool
                or not isinstance(source, str) or '\0' in source or source != str(Path(source))
                or Path(source).anchor != '/' or '..' in Path(source).parts
                or not digest('request') or not digest('before')
                or not integers('source_identity', 5, 2) or not integers('workspace', 2)
                or not integers('permissions', 3)
                or value.get('metadata', '') not in ('', 'added', 'updated', 'unchanged')
                or (value['cleaned'] and value['state'] not in TERMINAL)):
            raise ValueError('Unsupported journal')
        os.fsencode(source)  # Reject unencodable receipt paths before any mutation.
        if value['state'] in ('publishing', 'committed') and (not digest('after') or not integers('candidate_identity', 5, 2)):
            raise ValueError('Invalid publication intent')
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
    def lock(self, source, *, blocking=True):
        key = hashlib.sha256(os.fsencode(source)).hexdigest()
        fd = os.open(self.root / (key + '.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('Invalid lock')
            fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            yield
        finally:
            os.close(fd)

    def workspace(self, record):
        source = Path(record['source'])
        expected = source.parent / ('.mylar-tag-' + record['token'])
        if source.anchor != '/' or '..' in source.parts or any(p.is_symlink() for p in source.parents):
            raise ValueError('Invalid source ancestry')
        info = expected.lstat()
        if not stat.S_ISDIR(info.st_mode) or list(identity(info)[:2]) != record['workspace']:
            raise ValueError('Workspace identity changed')
        return expected

    def committed_intact(self, record):
        source = Path(record['source'])
        if any(p.is_symlink() for p in (source, *source.parents)):
            return False
        info = source.lstat()
        if (fingerprint(source) != record['after']
                or list(identity(info)[:4]) != record['candidate_identity'][:4]
                or [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid] != record['permissions']
                or info.st_nlink != 1 or os.listxattr(source, follow_symlinks=False)):
            return False
        folder = source.parent / ('.mylar-tag-' + record['token'])
        if folder.exists() or folder.is_symlink():
            folder = self.workspace(record)
            displaced = folder / 'verified.cbz'
            if displaced.exists() or displaced.is_symlink():
                info = displaced.lstat()
                if (fingerprint(displaced) != record['before']
                        or list(identity(info)[:4]) != record['source_identity'][:4]
                        or [stat.S_IMODE(info.st_mode), info.st_uid, info.st_gid] != record['permissions']
                        or info.st_nlink != 1 or os.listxattr(displaced, follow_symlinks=False)):
                    return False
        return True

    def finish(self, record, state, *, cleanup=True):
        if cleanup and state == 'committed':
            try:
                intact = self.committed_intact(record)
            except (OSError, ValueError):
                intact = False
            if not intact:
                state, cleanup = 'conflict', False
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

    def recover_pending(self):
        """Stream startup results without waiting on active jobs or hashing history.

        A caller must exhaust this iterator before admitting modern tag jobs and
        keep the gate closed for busy, invalid_journal, io_error or conflict.
        Unknown receipts are retained, not guessed or overwritten. No native
        startup calls this method until other-writer coordination is installed.
        """
        with os.scandir(self.root) as entries:
            for entry in entries:
                if not entry.name.endswith('.json'):
                    continue
                token = entry.name[:-5]
                if not HEX.fullmatch(token):
                    yield RecoveryResult('', 'invalid_journal')
                    continue
                try:
                    # Do not yield while holding either lock: callers may pause.
                    with self.lock('token:' + token, blocking=False):
                        record = self.read(token)
                        if record['state'] in TERMINAL and record['cleaned']:
                            continue
                        with self.lock(record['source'], blocking=False):
                            result = self._recover(record)
                    outcome = RecoveryResult(token, result.state, result.metadata)
                except BlockingIOError:
                    outcome = RecoveryResult(token, 'busy')
                except (ValueError, TypeError, KeyError):
                    outcome = RecoveryResult(token, 'invalid_journal')
                except OSError:
                    outcome = RecoveryResult(token, 'io_error')
                yield outcome

    def _recover(self, record):
        source = Path(record['source'])
        try:
            if record['state'] in TERMINAL:
                if record['state'] in ('committed', 'unchanged'):
                    expected = record['after'] if record['state'] == 'committed' else record['before']
                    if fingerprint(source) != expected or (not record.get('cleaned') and record['state'] == 'committed' and not self.committed_intact(record)):
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

    def tag(self, source, metadata, *, token, updates=None, replace_fields=(), executable=None, preserve_existing=False):
        if type(preserve_existing) is not bool:
            raise ValueError('Expected explicit no-overwrite policy')
        source = Path(source).absolute()
        replace_fields = tuple(replace_fields)
        if source.anchor != '/' or source.suffix.lower() != '.cbz' or '..' in source.parts or any(p.is_symlink() for p in (source, *source.parents)):
            return Result('unsupported')
        intent = [str(source), metadata, updates, list(replace_fields)]
        if preserve_existing:
            intent.append('preserve_existing')
        request = hashlib.sha256(json.dumps(intent, sort_keys=True, allow_nan=False).encode()).hexdigest()
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
                if preserve_existing:
                    if old.xml is None:
                        raise ValueError('Existing metadata disappeared')
                    record['metadata'] = 'unchanged'
                    return self.finish(record, 'unchanged')
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

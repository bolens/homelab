"""Root app-only Restic primitives. No CLI, receipt hydration or execution grant."""
import io
import select
import tarfile
import subprocess
from contextlib import closing
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import stat
import struct
import tempfile
import time
import weakref
import threading
import zipfile
import codecs
MAX_FILES = 100000
MAX_MANIFEST = 64 * 1024 ** 2
MAX_BYTES = 512 * 1024 ** 3
DEADLINE = 180

class Held(Exception):
    pass

def absolute(value):
    if not isinstance(value, str) or not value or '\x00' in value or (len(value.encode()) > 4096):
        raise Held('path')
    result = Path(value)
    if not result.is_absolute() or '..' in result.parts:
        raise Held('path')
    if any((p.is_symlink() for p in (result, *result.parents))):
        raise Held('linked-root')
    return result

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()

def stat_signature(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_mode, s.st_uid, s.st_gid, s.st_nlink]

def stamp(path):
    return stat_signature(path.lstat())

def attrs(path):
    s = path.lstat()
    names = os.listxattr(path, follow_symlinks=False)
    if len(names) > 64:
        raise Held('attributes')
    values = {key: os.getxattr(path, key, follow_symlinks=False).hex() for key in names}
    if sum((len(value) for value in values.values())) > 1024 ** 2:
        raise Held('attributes')
    return dict(mode=stat.S_IMODE(s.st_mode), uid=s.st_uid, gid=s.st_gid, mtime_ns=s.st_mtime_ns, xattrs=values)

def check_deadline(deadline):
    if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline) or time.monotonic() >= deadline):
        raise Held('original-deadline')

def copy_stream(incoming, outgoing, deadline=None):
    while True:
        check_deadline(deadline)
        block = incoming.read(1024 ** 2)
        check_deadline(deadline)
        if not block:
            break
        if outgoing.write(block) != len(block):
            raise Held('copy-short-write')
    outgoing.flush()
    check_deadline(deadline)

def attributes_many(paths, *, deadline=None):
    """Use one captured metadata reader; do not revalidate unrelated functions per leaf."""
    check_deadline(deadline)
    reader = attrs
    code = reader.__code__
    defaults = reader.__defaults__
    keywords = reader.__kwdefaults__
    result = []
    for path in paths:
        check_deadline(deadline)
        if attrs is not reader or reader.__code__ is not code or reader.__defaults__ is not defaults or (reader.__kwdefaults__ is not keywords):
            raise Held('attributes-original-reader')
        value = reader(Path(path))
        if attrs is not reader or reader.__code__ is not code or reader.__defaults__ is not defaults or (reader.__kwdefaults__ is not keywords):
            raise Held('attributes-original-reader')
        result.append((str(path), value))
    check_deadline(deadline)
    return tuple(result)

def hash_file(path, *, deadline=None):
    check_deadline(deadline)
    before = stamp(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or stat_signature(opened) != before:
            raise Held('hash-original-FD')
        result = hashlib.sha256()
        while True:
            check_deadline(deadline)
            block = stream.read(1024 ** 2)
            check_deadline(deadline)
            if not block:
                break
            result.update(block)
        if stat_signature(os.fstat(stream.fileno())) != before:
            raise Held('hash-original-FD')
    if stamp(path) != before:
        raise Held('source-changed')
    return result.hexdigest()

def inventory(root, kind, *, detached=False, deadline=None):
    check_deadline(deadline)
    if kind not in ('tree', 'file'):
        raise Held('kind')
    before = stamp(root)
    if not (stat.S_ISDIR(before[5]) if kind == 'tree' else stat.S_ISREG(before[5])):
        raise Held('scope-type')
    nodes = [root]
    if kind == 'tree':

        def failed(_):
            raise Held('walk')
        for directory, folders, files in os.walk(root, followlinks=False, onerror=failed):
            check_deadline(deadline)
            for name in list(folders):
                if (Path(directory) / name).is_symlink():
                    folders.remove(name)
                    files.append(name)
            nodes.extend((Path(directory) / name for name in folders + files))
            if len(nodes) > MAX_FILES:
                raise Held('bounds')
    rows = []
    total = 0
    for node in sorted(nodes):
        check_deadline(deadline)
        initial = stamp(node)
        mode = initial[5]
        if stat.S_ISREG(mode):
            if initial[8] < 1 or (detached and initial[8] != 1):
                raise Held('physical-alias')
            total += initial[2]
            if total > MAX_BYTES:
                raise Held('bounds')
            form, sha, link = ('file', hash_file(node, deadline=deadline), None)
        elif stat.S_ISDIR(mode):
            form, sha, link = ('directory', None, None)
        elif stat.S_ISLNK(mode):
            form, sha, link = ('symlink', None, os.readlink(node))
        else:
            raise Held('special-file')
        metadata = attrs(node)
        if stamp(node) != initial:
            raise Held('source-changed')
        rows.append(dict(path='.' if node == root else str(node.relative_to(root)), kind=form, sha256=sha, link=link, attributes=metadata, stamp=initial))
    if stamp(root) != before:
        raise Held('source-changed')
    return (rows, total)

def logical(rows):
    return [{key: value for key, value in row.items() if key != 'stamp'} for row in rows]

def mode_nfs4_acl(mode, kind):
    """Exact trivial NFSv4 ACL for POSIX mode bits (RFC 7530, section 6)."""
    if type(mode) is not int or not 0 <= mode <= 4095 or kind not in ('file', 'directory'):
        raise Held('nfs4-mode-kind')

    def access(bits):
        return (1 if bits & 4 else 0) | (6 | (64 if kind == 'directory' else 0) if bits & 2 else 0) | (32 if bits & 1 else 0)
    owner, group, other = (access(mode >> shift) for shift in (6, 3, 0))
    aces = []
    if (group | other) & ~owner:
        aces.append((1, (group | other) & ~owner, b'OWNER@'))
    aces.extend(((0, 1442176 | owner, b'OWNER@'), (0, 1179776 | group, b'GROUP@')))
    if other & ~group:
        aces.append((1, other & ~group, b'GROUP@'))
    aces.append((0, 1179776 | other, b'EVERYONE@'))
    return struct.pack('>I', len(aces)) + b''.join((struct.pack('>IIII', typ, 0, mask, len(who)) + who + b'\x00' * (-len(who) % 4) for typ, mask, who in aces))

def copied_attributes_match(actual, original, kind):
    if actual == original:
        return True
    if kind not in ('file', 'directory') or 'system.nfs4_acl' in original['xattrs']:
        return False
    if {k: v for k, v in actual.items() if k != 'xattrs'} != {k: v for k, v in original.items() if k != 'xattrs'}:
        return False
    expected = dict(original['xattrs'], **{'system.nfs4_acl': mode_nfs4_acl(original['mode'], kind).hex()})
    return actual['xattrs'] == expected

def copied_records_match(actual, original):
    if len(actual) != len(original):
        return False
    for current, expected in zip(actual, original):
        if {k: v for k, v in current.items() if k not in ('stamp', 'attributes')} != {k: v for k, v in expected.items() if k not in ('stamp', 'attributes')}:
            return False
        if not copied_attributes_match(current['attributes'], expected['attributes'], expected['kind']):
            return False
    return True

def apply_attrs(path, value):
    initial = attrs(path)
    mode = path.lstat().st_mode
    kind = 'directory' if stat.S_ISDIR(mode) else 'file' if stat.S_ISREG(mode) else 'symlink'
    acl = initial['xattrs'].get('system.nfs4_acl')
    if acl is not None and acl != value['xattrs'].get('system.nfs4_acl'):
        if kind == 'symlink' or acl != mode_nfs4_acl(initial['mode'], kind).hex():
            raise Held('foreign-copy-nfs4-acl')
    os.chown(path, value['uid'], value['gid'], follow_symlinks=False)
    if not path.is_symlink():
        os.chmod(path, value['mode'])
    current = os.listxattr(path, follow_symlinks=False)
    for name in set(current) - set(value['xattrs']):
        if name == 'system.nfs4_acl':
            if kind == 'symlink' or os.getxattr(path, name, follow_symlinks=False) != mode_nfs4_acl(value['mode'], kind):
                raise Held('foreign-copy-nfs4-acl')
        else:
            os.removexattr(path, name, follow_symlinks=False)
    for name, encoded in value['xattrs'].items():
        if name == 'system.nfs4_acl' and name in current and (os.getxattr(path, name, follow_symlinks=False).hex() == encoded):
            continue
        os.setxattr(path, name, bytes.fromhex(encoded), follow_symlinks=False)
    os.utime(path, ns=(value['mtime_ns'], value['mtime_ns']), follow_symlinks=False)
    if not copied_attributes_match(attrs(path), value, kind):
        raise Held('copy-attributes')

def wal_header(path, database_path, *, deadline=None):
    """Validate the committed readable WAL prefix; retain stale reset frames.

    SQLite fileformat2.html §§4.1–4.4 specify salts/checksums and stale tails.
    Matching-salt corruption, partial frames or unknown format remains held.
    """
    check_deadline(deadline)
    size = path.stat().st_size
    if size == 0:
        return dict(valid_frames=0, committed_frames=0, stale_frames=0)
    with path.open('rb') as stream:
        raw = stream.read(32)
        if len(raw) != 32:
            raise Held('malformed-wal')
        magic, version, pagesize, _, salt1, salt2, c0, c1 = struct.unpack('>8I', raw)
        if magic not in (931071618, 931071619) or version != 3007000 or pagesize < 512 or (pagesize > 65536) or pagesize & pagesize - 1 or (size - 32) % (24 + pagesize):
            raise Held('malformed-wal')
        with database_path.open('rb') as base:
            header = base.read(100)
        if len(header) < 100 or header[:16] != b'SQLite format 3\x00':
            raise Held('database-integrity')
        base_pagesize = int.from_bytes(header[16:18], 'big')
        if (65536 if base_pagesize == 1 else base_pagesize) != pagesize:
            raise Held('mismatched-wal')
        endian = '<' if magic == 931071618 else '>'

        def checksum(data, current):
            words = struct.unpack(endian + str(len(data) // 4) + 'I', data)
            a, b = current
            for i in range(0, len(words), 2):
                a = a + words[i] + b & 4294967295
                b = b + words[i + 1] + a & 4294967295
            return (a, b)
        current = checksum(raw[:24], (0, 0))
        if current != (c0, c1):
            raise Held('malformed-wal')
        valid = committed = stale = 0
        frames = (size - 32) // (24 + pagesize)
        if frames > 1000000:
            raise Held('database-bounds')
        for index in range(frames):
            check_deadline(deadline)
            frame = stream.read(24)
            page = stream.read(pagesize)
            page_number, commit, s1, s2, a, b = struct.unpack('>6I', frame)
            if (s1, s2) != (salt1, salt2):
                stale = frames - index
                break
            current = checksum(frame[:8] + page, current)
            if page_number == 0 or current != (a, b):
                raise Held('malformed-wal')
            valid += 1
            if commit:
                committed = valid
        return dict(valid_frames=valid, committed_frames=committed, stale_frames=stale)

def database(path, *, deadline=None):
    """Only a detached temporary SQLite pair may perform WAL-index recovery."""
    local_deadline = time.monotonic() + DEADLINE
    deadline = local_deadline if deadline is None else min(deadline, local_deadline)
    check_deadline(deadline)
    path = absolute(str(path))
    if os.path.lexists(str(path) + '-journal'):
        raise Held('rollback-journal-retained')
    companions = [Path(str(path) + suffix) for suffix in ('-wal', '-shm') if os.path.lexists(str(path) + suffix)]
    if any((item.name.endswith('-shm') for item in companions)) and (not any((item.name.endswith('-wal') for item in companions))):
        raise Held('orphan-shm')
    sources = [path, *companions]
    states = {}
    for source in sources:
        absolute(str(source))
        before = stamp(source)
        if not stat.S_ISREG(before[5]) or before[8] < 1:
            raise Held('database-companion')
        states[source] = dict(stamp=before, sha256=hash_file(source, deadline=deadline))
    wal = next((item for item in companions if item.name.endswith('-wal')), None)
    wal_proof = None if wal is None else wal_header(wal, path, deadline=deadline)
    with tempfile.TemporaryDirectory(prefix='owned-publication-db-') as work:
        root = Path(work)
        root.chmod(448)
        isolated = root / path.name
        for source in sources:
            fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as incoming, (root / source.name).open('xb') as target:
                copy_stream(incoming, target, deadline)
            (root / source.name).chmod(384)
            if hash_file(root / source.name, deadline=deadline) != states[source]['sha256']:
                raise Held('database-copy-drift')
        with closing(sqlite3.connect(isolated.as_uri() + '?mode=ro', uri=True)) as db:
            db.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
            db.execute('PRAGMA query_only=ON')
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise Held('database-integrity')
            schema = db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name,tbl_name,sql').fetchall()
            tables = {}
            for name, in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"):
                quoted = '"' + name.replace('"', '""') + '"'
                hashes = []
                for row in db.execute('SELECT * FROM ' + quoted):
                    check_deadline(deadline)
                    hashes.append(digest([dict(blob=item.hex()) if isinstance(item, bytes) else item for item in row]))
                    if len(hashes) > 1000000:
                        raise Held('database-bounds')
                tables[name] = dict(rows=len(hashes), digest=digest(sorted(hashes)))
    expected = {str(item) for item in companions}
    present = {str(Path(str(path) + suffix)) for suffix in ('-wal', '-shm') if os.path.lexists(str(path) + suffix)}
    if present != expected or os.path.lexists(str(path) + '-journal'):
        raise Held('database-companion-drift')
    for source, before in states.items():
        if stamp(source) != before['stamp'] or hash_file(source, deadline=deadline) != before['sha256']:
            raise Held('database-source-drift')
    return dict(schema=digest(schema), tables=tables, companions={item.name[len(path.name):]: states[item]['sha256'] for item in companions}, wal=wal_proof)

def database_rows(scopes, required, *, deadline=None):
    result = {}
    for scope in scopes:
        source = Path(scope['path'])
        declared = {row['path'] for row in scope['records'] if row['kind'] == 'file'}
        for row in scope['records']:
            check_deadline(deadline)
            if row['kind'] != 'file':
                continue
            path = source if row['path'] == '.' else source / row['path']
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                before = stat_signature(os.fstat(fd))
                if not stat.S_ISREG(before[5]) or before != row['stamp']:
                    raise Held('database-header-original-FD')
                is_db = os.read(fd, 16) == b'SQLite format 3\x00'
                if stat_signature(os.fstat(fd)) != before or stamp(path) != before:
                    raise Held('database-header-original-FD')
            finally:
                os.close(fd)
            key = scope['name'] + ':' + row['path']
            if is_db or key in required:
                for suffix in ('-wal', '-shm', '-journal'):
                    sibling = Path(str(path) + suffix)
                    if os.path.lexists(sibling):
                        if scope['kind'] != 'tree' or str(sibling.relative_to(source)) not in declared:
                            raise Held('missing-database-companion-scope')
                result[key] = database(path, deadline=deadline)
    if not set(required).issubset(result):
        raise Held('missing-database')
    return result
APPDATA_MAX_INDEX = 64 * 1024 ** 2
APPDATA_MAX_FILE = 4 * 1024 ** 3
APPDATA_MAX_NODES = 100000
APPDATA_MEDIA_SUFFIXES = frozenset(('.zip', '.rar', '.7z', '.cbz', '.cbr', '.cb7', '.cbt', '.cba', '.pdf', '.epub', '.mobi', '.azw', '.azw3', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.tif', '.tiff', '.bmp', '.mp4', '.mkv', '.mp3', '.flac'))
APPDATA_MAGIC = (b'PK\x03\x04', b'PK\x05\x06', b'Rar!\x1a\x07', b"7z\xbc\xaf'\x1c", b'%PDF-', b'\xff\xd8\xff', b'\x89PNG\r\n\x1a\n', b'GIF87a', b'GIF89a')

def appdata_need(value, reason):
    if not value:
        raise Held(reason)

def appdata_signature(value):
    return [value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_mode, value.st_uid, value.st_gid, value.st_nlink]

def appdata_freeze(value):
    kind = type(value)
    if kind is dict:
        appdata_need(all(type(key) is str for key in value), 'policy-key')
        return ('dict', tuple((key, appdata_freeze(value[key])) for key in sorted(value)))
    if kind is list:
        return ('list', tuple(appdata_freeze(item) for item in value))
    appdata_need(kind in (str, int, bool, type(None)), 'policy-scalar')
    return (kind.__name__, value)


def appdata_thaw(value):
    if value[0] == 'dict':
        return {key: appdata_thaw(item) for key, item in value[1]}
    if value[0] == 'list':
        return [appdata_thaw(item) for item in value[1]]
    return value[1]


def appdata_encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()

def appdata_carepackage(path, original, *, deadline=None):
    """Inspect the diagnostic ZIP schema from pinned carepackage.py 61cdac38.

    A filename or ZIP header alone cannot distinguish app diagnostics from a
    book. The owning producer writes only a DB, cleaned config and UTF-8 text.
    """
    check_deadline(deadline)
    appdata_need(path is not None and original is not None, 'unproved-app-archive')
    path = Path(path)
    expected = list(original)
    appdata_need(appdata_signature(path.lstat()) == expected and stat.S_ISREG(expected[5]),
                 'carepackage-original')
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        appdata_need(appdata_signature(os.fstat(descriptor)) == expected, 'carepackage-FD')
        with os.fdopen(os.dup(descriptor), 'rb') as source, zipfile.ZipFile(source) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            appdata_need(3 <= len(members) <= 64 and len(set(names)) == len(names) and
                         {'MylarRunningEnvironment.txt', 'mylar.db', 'clean_config.ini'} <= set(names),
                         'carepackage-member-census')
            appdata_need(sum(member.file_size for member in members) <= 512 * 1024**2,
                         'carepackage-expanded-bound')
            for member in members:
                check_deadline(deadline)
                name = member.filename
                appdata_need(Path(name).name == name and name not in ('.', '..') and
                             (name in ('MylarRunningEnvironment.txt', 'mylar.db', 'clean_config.ini', '.LASTRELEASE')
                              or re.fullmatch(r'mylar\.log(?:[.0-9_-]*)', name) is not None) and
                             not member.is_dir() and not member.flag_bits & 1 and
                             stat.S_IFMT(member.external_attr >> 16) in (0, stat.S_IFREG) and
                             member.file_size <= 256 * 1024**2, 'carepackage-app-member')
                decoder = None if name == 'mylar.db' else codecs.getincrementaldecoder('utf-8')()
                total = 0
                with archive.open(member) as incoming:
                    while raw := incoming.read(1024**2):
                        check_deadline(deadline)
                        if total == 0 and decoder is None:
                            appdata_need(raw.startswith(b'SQLite format 3\0'), 'carepackage-database-type')
                        total += len(raw)
                        appdata_need(total <= member.file_size, 'carepackage-member-overrun')
                        if decoder is not None:
                            decoder.decode(raw)
                    if decoder is not None:
                        decoder.decode(b'', final=True)
                appdata_need(total == member.file_size and (decoder is not None or total >= 16),
                             'carepackage-complete-member')
        appdata_need(appdata_signature(os.fstat(descriptor)) == expected ==
                     appdata_signature(path.lstat()), 'carepackage-original-close')
    except (zipfile.BadZipFile, UnicodeError, EOFError):
        raise Held('carepackage-invalid-app-archive') from None
    finally:
        os.close(descriptor)
    return False


def appdata_payload(role, relative, head, *, path=None, original=None, deadline=None):
    """Finite owning payload layouts; uncertain archives hold before streaming."""
    check_deadline(deadline)
    appdata_need(role in ('native_config', 'worker_state', 'reader_config'), 'scope-role')
    suffix = Path(relative).suffix.lower()
    archive = suffix in (APPDATA_MEDIA_SUFFIXES - {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.tif', '.tiff', '.bmp'}) or any(head.startswith(value) for value in APPDATA_MAGIC[:5])
    if role == 'reader_config':
        appdata_need(not archive, 'reader-unexpected-book-payload')
        return False
    if role == 'worker_state':
        return suffix in APPDATA_MEDIA_SUFFIXES or any(head.startswith(value) for value in APPDATA_MAGIC) or head.startswith(b'RIFF') and head[8:12] == b'WEBP'
    parts = Path(relative).parts
    if parts and parts[0] == 'mylar':
        parts = parts[1:]
    leaf = parts[-1] if parts else ''
    if (len(parts) >= 3 and parts[-3] == 'retained-standalone-v1' and
            re.fullmatch('[0-9a-f]{64}', parts[-2]) and
            re.fullmatch(r'target-(?:preserved|restored)(?:\.[^./\\\x00]*)?', leaf)):
        return True
    for position, part in enumerate(parts[:-1]):
        if re.fullmatch('archive-repair-[0-9a-f]{64}', part) and leaf in ('original.arc', 'restored-original.arc', 'prepared.cbz'):
            return True
        if re.fullmatch('adopt-[0-9a-f]{64}', part) and leaf in ('swap.arc', 'install-displaced.arc', 'reverse-displaced.arc'):
            return True
        if re.fullmatch('.mylar-tag-[0-9a-f]{32}', part) and leaf in ('original.cbz', 'tagged.cbz', 'verified.cbz', 'displaced.cbz'):
            return True
        if parts[position:position+2] == ('modern-tagger-v2', 'staging') and len(parts) > position+3 and re.fullmatch('mylar_modern_[0-9a-f]{32}', parts[position+2]):
            return True
        if parts[position:position+2] == ('media-writer', 'retained-repeats-v1') and len(parts) == position+4 and re.fullmatch('[0-9a-f]{32}|[0-9a-f]{64}', parts[position+2]) and leaf.startswith('original'):
            return True
        if re.fullmatch('[0-9a-f]{32}', part) and leaf in ('original.cbz', 'restored.cbz'):
            return True
    if archive and re.fullmatch(r'carepackage_[A-Za-z0-9_.() -]{1,128}\.zip', leaf):
        return appdata_carepackage(path, original, deadline=deadline)
    legacy = bool(parts) and (parts[0] == 'cache' or parts[0].startswith(('.reader-', 'tagger-stage-')))
    held = bool(parts) and (parts[0].startswith(('.reader-', 'tagger-stage-')) or
                            len(parts) > 1 and parts[0] == 'cache' and parts[1].startswith(('.mylar-pack-', '.mylar-recovery-')))
    if archive:
        appdata_need(legacy, 'native-unclassified-archive')
        return True
    image = suffix in {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.tif', '.tiff', '.bmp'} or any(head.startswith(value) for value in APPDATA_MAGIC[5:]) or head.startswith(b'RIFF') and head[8:12] == b'WEBP'
    return held and image


def appdata_validate(index):
    appdata_need(type(index) is dict and set(index) == {'version', 'kind', 'scopes'} and (type(index['version']) is int) and (index['version'] == 1) and (index['kind'] == 'publication-appdata-transport-v1'), 'index-schema')
    scopes = index['scopes']
    appdata_need(type(scopes) is list and tuple((row['role'] for row in scopes)) in (('native_config', 'reader_config'), ('native_config', 'worker_state', 'reader_config')), 'scope-order')
    total = 0
    for scope in scopes:
        appdata_need(type(scope) is dict and set(scope) == {'role', 'root', 'records'}, 'scope-schema')
        root = Path(scope['root'])
        appdata_need(root.is_absolute() and str(root) == scope['root'], 'scope-root')
        records = scope['records']
        appdata_need(type(records) is list and len(records) <= APPDATA_MAX_NODES, 'scope-census')
        by_path = {}
        for row in records:
            appdata_need(type(row) is dict and set(row) == {'path', 'kind', 'sha256', 'link', 'attributes', 'stamp', 'media'}, 'record-schema')
            relative = row['path']
            p = Path(relative)
            appdata_need(type(relative) is str and (not p.is_absolute()) and ('..' not in p.parts) and (p.as_posix() == relative) and (relative not in by_path), 'record-path')
            appdata_need(row['kind'] in ('file', 'directory', 'symlink') and type(row['media']) is bool and (not row['media'] or row['kind'] == 'file'), 'record-kind')
            appdata_need(type(row['stamp']) is list and len(row['stamp']) == 9 and all((type(value) is int for value in row['stamp'])), 'record-signature')
            if row['kind'] == 'file':
                appdata_need(type(row['sha256']) is str and len(row['sha256']) == 64 and all((c in '0123456789abcdef' for c in row['sha256'])) and (0 <= row['stamp'][2] <= 512 * 1024 ** 3), 'record-file')
                appdata_need(row['media'] or row['stamp'][2] <= APPDATA_MAX_FILE, 'app-file-bound')
            by_path[relative] = row
        appdata_need(by_path.get('.', {}).get('kind') == 'directory', 'record-root')
        for relative, row in by_path.items():
            p = Path(relative)
            if relative != '.':
                appdata_need(by_path.get(p.parent.as_posix(), {}).get('kind') == 'directory', 'record-parent')
            if row['kind'] == 'symlink':
                target = row['link']
                appdata_need(type(target) is str and target not in ('', '.', '..') and (Path(target).name == target), 'link-local-file')
                target_row = by_path.get((p.parent / target).as_posix(), {})
                appdata_need(target_row.get('kind') == 'file' and (not target_row.get('media')), 'link-app-target')
                appdata_need(row['attributes']['mode'] == 511 and (not row['attributes']['xattrs']), 'link-portable-metadata')
        total += len(records)
    appdata_need(total <= APPDATA_MAX_NODES, 'index-node-bound')

def _appdata_policy_factory():
    table = weakref.WeakKeyDictionary()
    class Selection:
        __slots__ = ('__weakref__',)
        def __init__(self, *args, **kwargs):
            raise Held('original-app-selection-required')
    def create(index):
        frozen = appdata_freeze(index)
        value = object.__new__(Selection)
        table[value] = (os.getpid(), threading.get_ident(), frozen)
        return value
    def frozen(value):
        appdata_need(type(value) is Selection, 'original-app-selection-type')
        original = table.get(value)
        appdata_need(original is not None and original[:2] == (os.getpid(), threading.get_ident()),
                     'original-app-selection-owner')
        return original[2]
    def opened(value):
        return appdata_thaw(frozen(value))
    return create, frozen, opened


_appdata_policy_create, appdata_policy_frozen, appdata_policy_value = _appdata_policy_factory()


def appdata_make_index(scopes, *, deadline=None):
    """Select from the owning caller's freshly captured complete inventories."""
    check_deadline(deadline)
    index = {'version': 1, 'kind': 'publication-appdata-transport-v1', 'scopes': appdata_thaw(appdata_freeze(scopes))}
    for scope in index['scopes']:
        root = Path(scope['root'])
        appdata_need(root.is_absolute() and str(root) == scope['root'] and (root.resolve() == root), 'selection-root')
        for row in scope['records']:
            check_deadline(deadline)
            relative = Path(row['path'])
            appdata_need(not relative.is_absolute() and '..' not in relative.parts and (relative.as_posix() == row['path']), 'selection-path')
            row['media'] = False
            if row['kind'] != 'file':
                continue
            path = Path(scope['root']) / row['path']
            appdata_need(appdata_signature(path.lstat()) == row['stamp'], 'selection-original')
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                appdata_need(appdata_signature(os.fstat(fd)) == row['stamp'] and stat.S_ISREG(os.fstat(fd).st_mode), 'selection-FD')
                head = os.read(fd, 16)
                row['media'] = appdata_payload(scope['role'], row['path'], head, path=path, original=row['stamp'], deadline=deadline)
                appdata_need(appdata_signature(os.fstat(fd)) == row['stamp'] == appdata_signature(path.lstat()), 'selection-original-close')
            finally:
                os.close(fd)
    appdata_validate(index)
    return _appdata_policy_create(index)

def appdata_estimate(scopes, files, *, deadline=None):
    """Capacity estimate only, from the original metadata census and file heads."""
    result = dict(app_bytes=0, media_bytes=0, largest_app_file=0)
    for text, original in files:
        check_deadline(deadline)
        if not stat.S_ISREG(original[5]):
            continue
        candidates = [scope for scope in scopes if Path(text).is_relative_to(scope['root'])]
        appdata_need(len(candidates) == 1, 'appdata-estimate-scope')
        scope = candidates[0]
        source = Path(text)
        appdata_need(appdata_signature(source.lstat()) == list(original), 'appdata-estimate-original')
        fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            appdata_need(appdata_signature(os.fstat(fd)) == list(original), 'appdata-estimate-FD')
            media = appdata_payload(scope['role'], source.relative_to(scope['root']).as_posix(), os.read(fd, 16), path=source, original=original, deadline=deadline)
            appdata_need(appdata_signature(os.fstat(fd)) == list(original) == appdata_signature(source.lstat()), 'appdata-estimate-close')
        finally:
            os.close(fd)
        result['media_bytes' if media else 'app_bytes'] += original[2]
        if not media:
            result['largest_app_file'] = max(result['largest_app_file'], original[2])
    return result

def appdata_selected(index):
    appdata_validate(index)
    return [(scope, row) for scope in index['scopes'] for row in sorted(scope['records'], key=lambda value: value['path']) if row['kind'] == 'file' and (not row['media'])]

def appdata_wait_ready(fd, event, deadline):
    """poll supports the high FD numbers used by complete original custody."""
    poller = select.poll()
    poller.register(fd, event)
    while True:
        remaining = deadline - time.monotonic()
        appdata_need(remaining > 0, 'transport-deadline')
        if poller.poll(max(1, min(1000, int(remaining * 1000)))):
            return

def appdata_OriginalFile(path, row, deadline):

    class OriginalFile:

        def __init__(self, path, row, deadline):
            self.path = Path(path)
            self.row = row
            self.fd = None
            self.count = 0
            self.sha = hashlib.sha256()
            self.deadline = deadline
            appdata_need(appdata_signature(self.path.lstat()) == row['stamp'] and stat.S_ISREG(row['stamp'][5]), 'original-file')
            try:
                self.fd = os.open(self.path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                self.check()
            except BaseException:
                self.close()
                raise

        def check(self):
            appdata_need(time.monotonic() < self.deadline, 'transport-deadline')
            appdata_need(self.fd is not None and appdata_signature(os.fstat(self.fd)) == self.row['stamp'] == appdata_signature(self.path.lstat()), 'original-file-custody')

        def read(self, size):
            appdata_need(type(size) is int and 0 <= size <= 1024 ** 2, 'bounded-source-read')
            self.check()
            raw = os.read(self.fd, size)
            self.count += len(raw)
            self.sha.update(raw)
            self.check()
            return raw

        def finish(self):
            self.check()
            appdata_need(self.count == self.row['stamp'][2] and self.sha.hexdigest() == self.row['sha256'], 'source-complete-hash')

        def close(self):
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
    return OriginalFile(path, row, deadline)

def appdata_decode_index(raw, sealed):
    appdata_need(type(raw) is bytes and len(raw) <= APPDATA_MAX_INDEX, 'index-byte-bound')
    try:
        decoded = json.loads(raw)
    except (json.JSONDecodeError, UnicodeError):
        raise Held('app-index-json') from None
    appdata_need(appdata_freeze(decoded) == sealed, 'app-index-encoded-semantics')


def appdata_write_archive(stream, index, *, deadline):
    appdata_need(time.monotonic() < deadline, 'transport-deadline')
    sealed = appdata_policy_frozen(index)
    rows = appdata_selected(appdata_thaw(sealed))
    body_value = appdata_thaw(sealed)
    body = appdata_encode(body_value)
    appdata_need(appdata_freeze(body_value) == sealed, 'stream-index-codec-custody')
    appdata_decode_index(body, sealed)
    appdata_need(len(body) <= APPDATA_MAX_INDEX, 'index-byte-bound')
    with tarfile.open(fileobj=stream, mode='w|', format=tarfile.PAX_FORMAT) as archive:
        member = tarfile.TarInfo('source-index.json')
        member.size = len(body)
        member.mode = 384
        archive.addfile(member, io.BytesIO(body))
        for scope, row in rows:
            appdata_need(time.monotonic() < deadline, 'transport-deadline')
            source = appdata_OriginalFile(Path(scope['root']) / row['path'], row, deadline)
            try:
                member = tarfile.TarInfo(scope['role'] + '/' + row['path'])
                member.size = row['stamp'][2]
                member.mode = 384
                archive.addfile(member, source)
                source.finish()
            finally:
                source.close()

def appdata_close_restore(custody):
    """Close the same born descriptors and namespaces, never a new census."""
    for path, descriptor, original, names in custody:
        expected = list(original)
        appdata_need(appdata_signature(os.fstat(descriptor)) == expected ==
                     appdata_signature(Path(path).lstat()), 'restore-born-node-drift')
        if names is not None:
            fresh = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=descriptor)
            try:
                appdata_need(tuple(sorted(os.listdir(fresh))) == names, 'restore-born-namespace')
            finally:
                os.close(fresh)
        appdata_need(appdata_signature(os.fstat(descriptor)) == expected ==
                     appdata_signature(Path(path).lstat()), 'restore-born-node-close')


def appdata_release_restore(custody):
    for _, descriptor, original, _ in custody:
        try:
            current = appdata_signature(os.fstat(descriptor))
        except OSError:
            continue
        if current[:2] == list(original[:2]) and stat.S_IFMT(current[5]) == stat.S_IFMT(original[5]):
            os.close(descriptor)


def appdata_restore_archive(stream, destination, index, *, deadline, parent_original=None):
    """Only born directory FDs may receive exclusive app files or links."""
    sealed = appdata_policy_frozen(index)
    index = appdata_thaw(sealed)
    rows = appdata_selected(index)
    appdata_need(time.monotonic() < deadline, 'transport-deadline')
    destination = Path(destination)
    appdata_need(not os.path.lexists(destination) and destination.is_absolute(), 'exclusive-restore-root')
    owned = {}
    names = {}
    success = False

    def path_close(path):
        descriptor, frame = owned[path]
        appdata_need(appdata_signature(os.fstat(descriptor)) == frame ==
                     appdata_signature(path.lstat()), 'restore-original-parent')
        return descriptor

    def parent_close(path):
        parent = path.parent
        for ancestor in (parent, *parent.parents):
            if ancestor in owned:
                path_close(ancestor)
        return path_close(parent)

    def inserted(path, parent_descriptor, previous, directory):
        after = appdata_signature(os.fstat(parent_descriptor))
        appdata_need(after[:2] + after[5:8] == previous[:2] + previous[5:8] and
                     after[8] == (previous[8] if previous[8] == 1 else previous[8] + int(directory)),
                     'restore-owned-insertion')
        appdata_need(appdata_signature(path.parent.lstat()) == after, 'restore-parent-incarnation')
        owned[path.parent] = (parent_descriptor, after)
        names[path.parent].add(path.name)

    def directory(path):
        parent_descriptor = parent_close(path)
        previous = owned[path.parent][1]
        os.mkdir(path.name, 0o700, dir_fd=parent_descriptor)
        born = appdata_signature(os.stat(path.name, dir_fd=parent_descriptor, follow_symlinks=False))
        descriptor = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                             dir_fd=parent_descriptor)
        frame = appdata_signature(os.fstat(descriptor))
        owned[path] = (descriptor, frame)
        appdata_need(frame == born == appdata_signature(path.lstat()), 'restore-directory-birth-open')
        names[path] = set()
        appdata_need(stat.S_ISDIR(frame[5]) and stat.S_IMODE(frame[5]) == 0o700 and
                     frame[6] == os.geteuid() and appdata_signature(path.lstat()) == frame,
                     'restore-born-directory')
        inserted(path, parent_descriptor, previous, True)

    def capture():
        return tuple((str(path), descriptor, tuple(frame),
                      tuple(sorted(names[path])) if path in names else None)
                     for path, (descriptor, frame) in sorted(owned.items()))

    try:
        if parent_original is None:
            descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
            frame = appdata_signature(os.fstat(descriptor))
        else:
            descriptor, initial = parent_original
            frame = list(initial)
        owned[destination.parent] = (descriptor, frame)
        parent_close(destination)
        fresh = os.open('.', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
        try:
            names[destination.parent] = set(os.listdir(fresh))
        finally:
            os.close(fresh)
        parent_close(destination)
        directory(destination)
        expected_names = ['source-index.json'] + [scope['role'] + '/' + row['path'] for scope, row in rows]
        count = 0
        with tarfile.open(fileobj=stream, mode='r|') as archive:
            for member in archive:
                appdata_need(time.monotonic() < deadline, 'transport-deadline')
                appdata_need(count < len(expected_names) and member.name == expected_names[count] and
                             member.isfile() and not member.issym() and not member.islnk() and
                             member.size <= max(APPDATA_MAX_INDEX, APPDATA_MAX_FILE), 'exact-app-member')
                count += 1
                incoming = archive.extractfile(member)
                appdata_need(incoming is not None, 'member-stream')
                if count == 1:
                    appdata_decode_index(incoming.read(APPDATA_MAX_INDEX + 1), sealed)
                    for scope in index['scopes']:
                        root = destination / scope['role']
                        directory(root)
                        for row in sorted(scope['records'], key=lambda r: len(Path(r['path']).parts)):
                            if row['kind'] == 'directory' and row['path'] != '.':
                                directory(root / row['path'])
                    continue
                scope, row = rows[count - 2]
                target = destination / scope['role'] / row['path']
                appdata_need(member.size == row['stamp'][2], 'member-original-size')
                parent_descriptor = parent_close(target)
                previous = owned[target.parent][1]
                descriptor = os.open(target.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                     0o600, dir_fd=parent_descriptor)
                frame = appdata_signature(os.fstat(descriptor))
                owned[target] = (descriptor, frame)
                appdata_need(stat.S_ISREG(frame[5]) and frame[2] == 0 and frame[8] == 1 and
                             stat.S_IMODE(frame[5]) == 0o600 and frame[6] == os.geteuid(), 'restore-born-file')
                inserted(target, parent_descriptor, previous, False)
                sha = hashlib.sha256()
                total = 0
                while raw := incoming.read(1024**2):
                    appdata_need(time.monotonic() < deadline, 'transport-deadline')
                    total += len(raw)
                    appdata_need(total <= member.size, 'member-overrun')
                    sha.update(raw)
                    remaining = memoryview(raw)
                    while remaining:
                        written = os.write(descriptor, remaining)
                        appdata_need(written > 0, 'restore-write')
                        remaining = remaining[written:]
                os.fsync(descriptor)
                after = appdata_signature(os.fstat(descriptor))
                appdata_need(after[:2] + after[5:] == frame[:2] + frame[5:] and after[2] == total and
                             total == member.size and sha.hexdigest() == row['sha256'] and
                             appdata_signature(target.lstat()) == after, 'restored-original-bytes')
                owned[target] = (descriptor, after)
        appdata_need(count == len(expected_names), 'missing-app-members')
        for scope in index['scopes']:
            root = destination / scope['role']
            for row in scope['records']:
                if row['kind'] != 'symlink':
                    continue
                target = root / row['path']
                parent_descriptor = parent_close(target)
                previous = owned[target.parent][1]
                os.symlink(row['link'], target.name, dir_fd=parent_descriptor)
                descriptor = os.open(target.name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                                     dir_fd=parent_descriptor)
                frame = appdata_signature(os.fstat(descriptor))
                owned[target] = (descriptor, frame)
                appdata_need(stat.S_ISLNK(frame[5]) and frame[8] == 1 and
                             appdata_signature(target.lstat()) == frame, 'restore-born-link')
                inserted(target, parent_descriptor, previous, False)
        appdata_close_restore(capture())
        # Metadata changes address held nodes, never paths through a mutable
        # directory. Preserve the actual incarnation across each syscall.
        attributes = {destination / scope['role'] / row['path']: row['attributes']
                      for scope in index['scopes'] for row in scope['records'] if not row['media']}
        for path in sorted(attributes, key=lambda value: len(value.parts), reverse=True):
            parent_close(path)
            descriptor = path_close(path)
            previous = owned[path][1]
            value = attributes[path]
            if stat.S_ISLNK(previous[5]):
                parent_descriptor = parent_close(path)
                os.chown(path.name, value['uid'], value['gid'], dir_fd=parent_descriptor, follow_symlinks=False)
                os.utime(path.name, ns=(value['mtime_ns'], value['mtime_ns']),
                         dir_fd=parent_descriptor, follow_symlinks=False)
            else:
                os.fchown(descriptor, value['uid'], value['gid'])
                os.fchmod(descriptor, value['mode'])
                current = set(os.listxattr(descriptor))
                for name in current - set(value['xattrs']):
                    os.removexattr(descriptor, name)
                for name, encoded in value['xattrs'].items():
                    os.setxattr(descriptor, name, bytes.fromhex(encoded))
                os.utime(descriptor, ns=(value['mtime_ns'], value['mtime_ns']))
                os.fsync(descriptor)
            after = appdata_signature(os.fstat(descriptor))
            appdata_need(after[:3] == previous[:3] and stat.S_IFMT(after[5]) == stat.S_IFMT(previous[5]) and
                         after[8] == previous[8] and appdata_signature(path.lstat()) == after,
                         'restore-owned-metadata-transition')
            appdata_need(attrs(path) == value, 'restore-owned-attributes')
            owned[path] = (descriptor, after)
        custody = capture()
        appdata_close_restore(custody)
        success = True
        return dict(root=str(destination), custody=custody)
    finally:
        if not success:
            appdata_release_restore(capture())


def appdata_verify_restored(destination, index, *, deadline, custody):
    """Independent bytes, aliases, metadata and namespace verification."""
    appdata_close_restore(custody)
    index = appdata_policy_value(index)
    appdata_validate(index)
    destination = Path(destination)
    expected_roots = {scope['role'] for scope in index['scopes']}
    appdata_need(set(os.listdir(destination)) == expected_roots, 'restore-root-census')
    for scope in index['scopes']:
        appdata_need(time.monotonic() < deadline, 'transport-deadline')
        root = destination / scope['role']
        expected = {row['path']: row for row in scope['records'] if not row['media']}
        actual = set()
        for directory, dirs, files in os.walk(root, followlinks=False):
            relative = Path(directory).relative_to(root).as_posix()
            actual.add(relative)
            for name in dirs + files:
                actual.add((Path(directory) / name).relative_to(root).as_posix())
        appdata_need(actual == set(expected), 'restore-complete-census')
        for relative, row in expected.items():
            appdata_need(time.monotonic() < deadline, 'transport-deadline')
            path = root / relative
            before = appdata_signature(path.lstat())
            kind = 'directory' if stat.S_ISDIR(before[5]) else 'file' if stat.S_ISREG(before[5]) else 'symlink' if stat.S_ISLNK(before[5]) else 'unsupported'
            appdata_need(kind == row['kind'] and before[:2] != row['stamp'][:2], 'restore-detached-kind')
            appdata_need(kind == 'directory' or before[8] == 1, 'restore-detached-alias')
            attributes = dict(mode=stat.S_IMODE(before[5]), uid=before[6], gid=before[7], mtime_ns=before[3], xattrs={name: os.getxattr(path, name, follow_symlinks=False).hex() for name in os.listxattr(path, follow_symlinks=False)})
            appdata_need(attributes == row['attributes'], 'restore-attributes')
            if kind == 'symlink':
                appdata_need(os.readlink(path) == row['link'], 'restore-link-target')
            if kind == 'file':
                appdata_need(before[2] == row['stamp'][2], 'restore-file-size')
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    appdata_need(appdata_signature(os.fstat(fd)) == before, 'restore-file-FD')
                    sha = hashlib.sha256()
                    total = 0
                    while (raw := os.read(fd, 1024 ** 2)):
                        appdata_need(time.monotonic() < deadline, 'transport-deadline')
                        total += len(raw)
                        appdata_need(total <= before[2], 'restore-file-overrun')
                        sha.update(raw)
                    appdata_need(total == before[2] and sha.hexdigest() == row['sha256'] and (appdata_signature(os.fstat(fd)) == before), 'restore-file-readback')
                finally:
                    os.close(fd)
            appdata_need(appdata_signature(path.lstat()) == before, 'restore-original-close')
    appdata_close_restore(custody)
    return {'app_files': len(appdata_selected(index)), 'media_copies': 0}

def appdata_restic_profile(*, deadline):
    """The explicit first profile supports the existing local Restic owner."""
    profile = json.loads(appdata_docker(('inspect', 'restic'), deadline=deadline))
    appdata_need(type(profile) is list and len(profile) == 1, 'restic-original-container')
    row = profile[0]
    appdata_need(row['Name'] == '/restic' and row['State']['Running'] is True and (re.fullmatch('[0-9a-f]{64}', row['Id']) is not None), 'restic-existing-owner')
    environment = {}
    for entry in row['Config']['Env']:
        key, separator, value = entry.partition('=')
        appdata_need(separator and key not in environment, 'restic-environment')
        environment[key] = value
    appdata_need(environment.get('RESTIC_REPOSITORY') == '/repository', 'restic-local-profile')
    mounts = {}
    for leaf in ('/repository', '/cache'):
        values = [mount for mount in row['Mounts'] if mount['Destination'] == leaf]
        appdata_need(len(values) == 1 and values[0]['RW'] is True and (values[0]['Type'] in ('bind', 'volume')), 'restic-existing-mount')
        path = Path(values[0]['Source'])
        appdata_need(path.is_absolute() and path.resolve() == path and path.is_dir(), 'restic-original-mount-root')
        mounts[leaf] = str(path)
    appdata_need(not Path(mounts['/repository']).is_relative_to(mounts['/cache']) and (not Path(mounts['/cache']).is_relative_to(mounts['/repository'])), 'restic-mount-overlap')
    projected = {key: row[key] for key in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts', 'RestartCount')}
    projected['process'] = {key: row['State'][key] for key in ('Pid', 'StartedAt', 'Running', 'Status')}
    return dict(container_id=row['Id'], image=row['Image'], mounts=mounts, mount_nodes={leaf: tuple(appdata_signature(Path(path).lstat())[i] for i in (0,1,5,6,7)) for leaf,path in mounts.items()}, profile_sha256=hashlib.sha256(appdata_encode(projected)).hexdigest())

def appdata_docker(arguments, *, deadline):
    appdata_need(time.monotonic() < deadline, 'transport-deadline')
    try:
        result = subprocess.run(('/usr/bin/docker', *arguments), capture_output=True, timeout=min(600, max(0.001, deadline - time.monotonic())))
    except (OSError, subprocess.TimeoutExpired):
        raise Held('restic-command-unavailable') from None
    appdata_need(result.returncode == 0 and len(result.stdout) + len(result.stderr) <= MAX_MANIFEST, 'restic-command-refused')
    return result.stdout

def appdata_restic_command(binding, arguments, *, deadline):
    return appdata_docker(('exec', binding['container_id'], 'restic', *arguments), deadline=deadline)

def appdata_node5(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


def appdata_close_ancestors(records):
    for path, descriptor, original in records:
        appdata_need(appdata_node5(os.fstat(descriptor)) == original == appdata_node5(Path(path).lstat()),
                     'restic-original-ancestor')


def appdata_release_ancestors(records):
    for _, descriptor, original in records:
        try:
            current = os.fstat(descriptor)
        except OSError:
            continue
        if (current.st_dev,current.st_ino,stat.S_IFMT(current.st_mode)) == (original[0],original[1],stat.S_IFMT(original[2])):
            os.close(descriptor)


def appdata_hold_output_parent(output):
    output = Path(output)
    absolute(str(output.parent))
    records = []
    try:
        path = Path('/')
        descriptor = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        records.append((str(path),descriptor,appdata_node5(os.fstat(descriptor))))
        for part in output.parent.parts[1:]:
            path = path / part
            born = appdata_node5(os.stat(part,dir_fd=descriptor,follow_symlinks=False))
            descriptor = os.open(part,os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,dir_fd=descriptor)
            acquired = appdata_node5(os.fstat(descriptor))
            records.append((str(path),descriptor,acquired))
            appdata_need(acquired == born == appdata_node5(path.lstat()), 'restic-original-output-parent-open')
        appdata_close_ancestors(records)
        return tuple(records)
    except BaseException:
        appdata_release_ancestors(records)
        raise


def appdata_restic_backup(index, output, *, deadline):
    appdata_policy_frozen(index)
    ancestors = appdata_hold_output_parent(output)
    mounts = []
    try:
        binding = appdata_restic_profile(deadline=deadline)
        for leaf,path in binding['mounts'].items():
            descriptor = os.open(path,os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
            acquired = appdata_node5(os.fstat(descriptor))
            mounts.append((path,descriptor,acquired))
            appdata_need(acquired == binding['mount_nodes'][leaf] == appdata_node5(Path(path).lstat()),
                         'restic-original-mount-open')
        result = _appdata_restic_backup_owned(index,output,binding,ancestors,tuple(mounts),deadline=deadline)
        appdata_close_ancestors(ancestors)
        appdata_close_ancestors(mounts)
        result['output_ancestors'] = ancestors
        result['mount_custody'] = tuple(mounts)
        ancestors = ()
        mounts = []
        return result
    finally:
        appdata_release_ancestors(ancestors)
        appdata_release_ancestors(mounts)


def _appdata_restic_backup_owned(index, output, binding, ancestors, mount_custody, *, deadline):
    """Actual encrypted backup plus one independent app restore, no media copy.

    The caller owns consistent original scopes and all executable authority.
    Returned facts alone cannot construct a typed owning observation.
    """
    selection = appdata_policy_frozen(index)
    appdata_validate(appdata_policy_value(index))
    output = Path(output)
    appdata_need(output.is_absolute() and (not os.path.lexists(output)) and (output.parent.resolve() == output.parent), 'restic-private-output')
    parent = output.parent.lstat()
    appdata_need(stat.S_ISDIR(parent.st_mode) and stat.S_IMODE(parent.st_mode) == 448 and (parent.st_uid == os.geteuid()), 'restic-private-output-parent')
    roots = [Path(scope['root']) for scope in appdata_policy_value(index)['scopes']]
    appdata_need(all((not output.is_relative_to(root) and (not root.is_relative_to(output)) for root in roots)), 'restic-output-overlap')
    cache = Path(binding['mounts']['/cache'])
    repository = Path(binding['mounts']['/repository'])
    app_bytes = sum((row['stamp'][2] for _, row in appdata_selected(appdata_policy_value(index))))
    required = app_bytes + len(appdata_encode(appdata_policy_value(index))) + 1024 ** 3
    appdata_need(shutil.disk_usage(repository).free >= required and shutil.disk_usage(output.parent).free >= required and (shutil.disk_usage(cache).free >= 128 * 1024 ** 2), 'restic-appdata-capacity')
    locks = appdata_restic_command(binding, ('list', 'locks'), deadline=deadline).splitlines()
    appdata_need(not locks, 'restic-existing-operation')
    tag = 'mylar-publication-appdata-' + os.urandom(16).hex()
    scope_id = hashlib.sha256(appdata_encode([(scope['role'],scope['root']) for scope in appdata_policy_value(index)['scopes']])).hexdigest()
    name = 'publication-appdata-' + scope_id + '.tar'
    with tempfile.TemporaryFile(dir=cache) as stdout, tempfile.TemporaryFile(dir=cache) as stderr:
        process = subprocess.Popen(('/usr/bin/docker', 'exec', '-i', binding['container_id'], 'restic', 'backup', '--stdin', '--stdin-filename', name, '--tag', tag, '--json', '--quiet'), stdin=subprocess.PIPE, stdout=stdout, stderr=stderr)
        os.set_blocking(process.stdin.fileno(), False)

        class Sink:

            def __init__(self):
                self.sha = hashlib.sha256()
                self.count = 0

            def write(self, raw):
                appdata_need(type(raw) is bytes and len(raw) <= MAX_MANIFEST, 'restic-write-bound')
                remaining = memoryview(raw)
                while remaining:
                    appdata_need(process.poll() is None, 'restic-stdin-closed')
                    appdata_wait_ready(process.stdin.fileno(), select.POLLOUT, deadline)
                    try:
                        written = os.write(process.stdin.fileno(), remaining)
                    except BlockingIOError:
                        continue
                    appdata_need(written > 0, 'restic-stdin-write')
                    self.sha.update(remaining[:written])
                    self.count += written
                    remaining = remaining[written:]
                return len(raw)

            def flush(self):
                pass
        sink = Sink()
        try:
            appdata_write_archive(sink, index, deadline=deadline)
            process.stdin.close()
            appdata_need(process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0, 'restic-backup-failed')
        finally:
            if not process.stdin.closed:
                process.stdin.close()
            if process.poll() is None:
                try:
                    process.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
                    raise Held('restic-backup-outcome-uncertain') from None
        appdata_need(os.fstat(stdout.fileno()).st_size <= MAX_MANIFEST and os.fstat(stderr.fileno()).st_size <= MAX_MANIFEST, 'restic-output-bound')
        stdout.seek(0)
        summaries = [row for row in (json.loads(line) for line in stdout) if row.get('message_type') == 'summary']
    appdata_need(len(summaries) == 1, 'restic-one-snapshot')
    snapshot_id = summaries[0]['snapshot_id']
    appdata_need(type(snapshot_id) is str and re.fullmatch('[0-9a-f]{64}', snapshot_id) is not None, 'restic-actual-snapshot-id')
    document = json.loads(appdata_restic_command(binding, ('cat', 'snapshot', snapshot_id), deadline=deadline))
    appdata_need(document.get('tags', []).count(tag) == 1, 'restic-original-snapshot-tag')
    listing = [json.loads(line) for line in appdata_restic_command(binding, ('ls', snapshot_id, '--json'), deadline=deadline).splitlines()]
    files = [row for row in listing if row.get('type') == 'file']
    appdata_need(len(files) == 1 and Path(files[0]['path']).name == name and (files[0]['size'] == sink.count), 'restic-exact-app-artifact')
    snapshot = repository / 'snapshots' / snapshot_id
    frame = stamp(snapshot)
    appdata_need(stat.S_ISREG(frame[5]) and frame[8] == 1 and (hash_file(snapshot, deadline=deadline) == snapshot_id), 'restic-encrypted-snapshot')
    descriptor = os.open(snapshot, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
    restore_custody = None
    output_fd = None
    try:
        appdata_need(appdata_signature(os.fstat(descriptor)) == frame == stamp(snapshot), 'restic-original-snapshot-FD')
        appdata_close_ancestors(ancestors)
        appdata_close_ancestors(mount_custody)
        parent_fd = ancestors[-1][1]
        os.mkdir(output.name,0o700,dir_fd=parent_fd)
        output_born = appdata_signature(os.stat(output.name,dir_fd=parent_fd,follow_symlinks=False))
        output_fd = os.open(output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,dir_fd=parent_fd)
        output_frame = appdata_signature(os.fstat(output_fd))
        appdata_need(output_frame == output_born == appdata_signature(output.lstat()), 'restic-born-output')
        with tempfile.TemporaryFile(dir=cache) as stderr:
            process = subprocess.Popen(('/usr/bin/docker', 'exec', binding['container_id'], 'restic', 'dump', snapshot_id, files[0]['path']), stdout=subprocess.PIPE, stderr=stderr)
            os.set_blocking(process.stdout.fileno(), False)

            class Reader:

                def __init__(self):
                    self.sha = hashlib.sha256()
                    self.count = 0

                def read(self, size):
                    appdata_need(type(size) is int and 0 <= size <= 1024 ** 2, 'restic-read-bound')
                    if size == 0:
                        return b''
                    while True:
                        appdata_wait_ready(process.stdout.fileno(), select.POLLIN, deadline)
                        try:
                            raw = os.read(process.stdout.fileno(), size)
                        except BlockingIOError:
                            continue
                        self.count += len(raw)
                        appdata_need(self.count <= sink.count, 'restic-dump-overrun')
                        self.sha.update(raw)
                        return raw
            reader = Reader()
            try:
                restored_view = appdata_restore_archive(reader, output / 'restore', index, deadline=deadline, parent_original=(os.dup(output_fd), tuple(output_frame)))
                restored = Path(restored_view['root'])
                restore_custody = restored_view['custody']
                while reader.read(1024 ** 2):
                    pass
                appdata_need(process.wait(timeout=max(0.001, deadline - time.monotonic())) == 0 and reader.count == sink.count and (reader.sha.digest() == sink.sha.digest()), 'restic-independent-dump-hash')
            finally:
                process.stdout.close()
                if process.poll() is None:
                    try:
                        process.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                        raise Held('restic-dump-outcome-uncertain') from None
        proof = appdata_verify_restored(restored, index, deadline=deadline, custody=restore_custody)
        appdata_need(appdata_restic_profile(deadline=deadline) == binding, 'restic-owner-closure')
        appdata_need(appdata_signature(os.fstat(descriptor)) == frame == stamp(snapshot), 'restic-snapshot-final-FD')
        result = dict(version=1, kind='original-restic-appdata-backup-v1', snapshot_id=snapshot_id, tag=tag, artifact_path=files[0]['path'], artifact_bytes=sink.count, artifact_sha256=sink.sha.hexdigest(), app_bytes=app_bytes, app_files=proof['app_files'], media_copies=0, binding=binding, snapshot_path=str(snapshot), snapshot_signature9=frame, snapshot_fd=descriptor, snapshot_attributes=attrs(snapshot), restore_root=str(restored), restore_custody=restore_custody, selection=selection)
        descriptor = None
        restore_custody = None
        return result
    finally:
        if restore_custody is not None:
            appdata_release_restore(restore_custody)
        if output_fd is not None:
            os.close(output_fd)
        if descriptor is not None:
            os.close(descriptor)

APPDATA_ONLY = True

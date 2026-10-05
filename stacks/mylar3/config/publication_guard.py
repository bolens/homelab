"""Bounded read-only publication payload evidence.

This foundation does not admit corrections or authorize publication. Registry,
owner and writer admission must validate this evidence before any mutation.
"""

from contextlib import closing, contextmanager
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import selectors
import stat
import subprocess
import sys
import tarfile
import time
import zipfile

MAX_MEMBERS = 4096
MAX_BYTES = 4 * 1024 ** 3
MAX_MEMBER = 512 * 1024 ** 2
MAX_METADATA = 262144
MAX_OUTPUT = 2 * 1024 ** 2
TIMEOUT = 180
TOOL_ROOT = Path('/opt/archiving-utils')
METADATA = ('ComicInfo.xml', 'ComicBookInfo.json')
PAGE_EXTENSIONS = frozenset(('.jpg', '.jpeg', '.jpe', '.jfif', '.png', '.apng',
    '.webp', '.gif', '.tif', '.tiff', '.bmp', '.dib', '.avif', '.heic', '.heif',
    '.jxl', '.jp2', '.j2k', '.jpf', '.jpx', '.ppm', '.pgm', '.pbm', '.pnm', '.qoi'))


class Unavailable(ValueError):
    """Required complete stable evidence is unavailable; retain the source."""


def compact(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def signature(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid,
            info.st_nlink]


def regular(path):
    path = Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise Unavailable('Expected an absolute unlinked archive path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    stream = os.fdopen(fd, 'rb')
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        stream.close()
        raise Unavailable('Expected a regular archive')
    return stream


def file_hash(path, *, deadline=None):
    deadline = time.monotonic() + TIMEOUT if deadline is None else deadline
    with regular(path) as stream:
        before = signature(os.fstat(stream.fileno()))
        if not 0 < before[2] <= MAX_BYTES:
            raise Unavailable('Archive exceeds input bounds')
        digest, count = hashlib.sha256(), 0
        while True:
            if time.monotonic() >= deadline:
                raise Unavailable('Archive hashing timed out')
            block = stream.read(min(1024 * 1024, before[2] - count + 1))
            if not block:
                break
            count += len(block)
            if count > before[2] or count > MAX_BYTES:
                raise Unavailable('Archive grew during verification')
            digest.update(block)
        if (count != before[2] or signature(os.fstat(stream.fileno())) != before
                or signature(Path(path).lstat()) != before):
            raise Unavailable('Archive changed during verification')
    return before, digest.hexdigest()


def object_pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise Unavailable('Duplicate metadata or protocol key')
        value[key] = item
    return value


def decode_json(raw):
    return json.loads(raw, object_pairs_hook=object_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          Unavailable('Non-finite JSON value')))


def metadata(name, raw):
    if len(raw) > MAX_METADATA:
        raise Unavailable('Metadata exceeds bounds')
    if name == 'ComicInfo.xml':
        if __package__:
            from .tagger_metadata import parse
        else:
            from tagger_metadata import parse
        parse(raw)
    else:
        value = decode_json(raw.decode('utf-8-sig'))
        if (not isinstance(value, dict)
                or not isinstance(value.get('ComicBookInfo/1.0'), dict)):
            raise Unavailable('Unsupported ComicBookInfo schema')


def safe_name(name, directory):
    if not isinstance(name, str):
        raise Unavailable('Invalid member name')
    path = PurePosixPath(name)
    canonical = name[:-1] if directory and name.endswith('/') else name
    if (not canonical or canonical != path.as_posix() or path.is_absolute()
            or canonical == '.' or '..' in path.parts
            or any(c in name for c in ('\\', '\0', ':'))
            or len(name.encode('utf-8')) > 4096):
        raise Unavailable('Unsafe or noncanonical member name')
    return canonical


def token(rows, pages):
    members = sorted(([r['name'], r['bytes'], r['sha256']] for r in rows
                      if not r['directory'] and r['name'] not in METADATA),
                     key=lambda row: row[0].encode('utf-8'))
    return hashlib.sha256(compact(dict(version=1, members=members,
                                       pages=pages))).hexdigest()


def natural_key(name):
    return (tuple((1, int(part)) if part.isascii() and part.isdigit() else (0, part)
                  for part in re.split(r'([0-9]+)', name.casefold())), name)


def validate(value):
    if (not isinstance(value, dict) or set(value) != {'version', 'members', 'pages', 'payload'}
            or type(value['version']) is not int or value['version'] != 1
            or not isinstance(value['members'], list)
            or not 0 < len(value['members']) <= MAX_MEMBERS):
        raise Unavailable('Invalid archive verifier schema')
    seen, total, metadata_count = set(), 0, 0
    for row in value['members']:
        if (not isinstance(row, dict) or set(row) != {'name', 'bytes', 'directory', 'sha256'}
                or type(row['directory']) is not bool or type(row['bytes']) is not int
                or not 0 <= row['bytes'] <= MAX_MEMBER
                or not isinstance(row['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', row['sha256'])):
            raise Unavailable('Invalid member evidence schema')
        name = safe_name(row['name'], row['directory'])
        if name != row['name'] or name in seen:
            raise Unavailable('Ambiguous member evidence')
        seen.add(name)
        total += row['bytes']
        if total > MAX_BYTES or (row['directory'] and (row['bytes']
                or row['sha256'] != hashlib.sha256(b'').hexdigest())):
            raise Unavailable('Invalid directory or expanded-byte evidence')
        if name.casefold() in {m.casefold() for m in METADATA}:
            metadata_count += 1
            if (name not in METADATA or metadata_count > 1 or row['directory']
                    or row['bytes'] > MAX_METADATA):
                raise Unavailable('Ambiguous metadata evidence')
    pages = sorted((r['name'] for r in value['members'] if not r['directory']
                    and PurePosixPath(r['name']).suffix.lower() in PAGE_EXTENSIONS),
                   key=natural_key)
    if not pages or value['pages'] != pages or value['payload'] != token(value['members'], pages):
        raise Unavailable('Incomplete or unordered payload evidence')


def scan(path, tool_root):
    """Child-only streaming scan. No extraction or tool configuration lookup."""
    root = Path(tool_root).resolve(strict=True)
    sys.path.insert(0, str(root / 'lib'))
    import comics
    if comics.PAGE_EXTENSIONS != PAGE_EXTENSIONS:
        raise Unavailable('Archive verifier page protocol changed')
    from tagger_archive import directory_limits
    rows, seen, total, root_metadata = [], set(), 0, []

    def consume(name, size, directory, stream):
        nonlocal total
        name = safe_name(name, directory)
        if name in seen or len(seen) >= MAX_MEMBERS:
            raise Unavailable('Duplicate or excessive archive members')
        seen.add(name)
        if (type(size) is not int or size < 0 or size > MAX_MEMBER
                or total + size > MAX_BYTES or (directory and size)):
            raise Unavailable('Archive exceeds payload bounds')
        total += size
        if name.casefold() in {m.casefold() for m in METADATA}:
            if name not in METADATA or directory or root_metadata:
                raise Unavailable('Ambiguous root metadata')
            root_metadata.append(name)
        limit = MAX_METADATA if name in METADATA else MAX_MEMBER
        if size > limit:
            raise Unavailable('Archive member exceeds bounds')
        digest, count, chunks = hashlib.sha256(), 0, []
        if stream is not None:
            while block := stream.read(min(1024 * 1024, limit - count + 1)):
                count += len(block)
                if count > size or count > limit:
                    raise Unavailable('Archive member exceeds declared size')
                digest.update(block)
                if name in METADATA:
                    chunks.append(block)
        if count != size:
            raise Unavailable('Incomplete archive member')
        if name in METADATA:
            metadata(name, b''.join(chunks))
        rows.append(dict(name=name, bytes=count, directory=directory,
                         sha256=digest.hexdigest()))

    path = Path(path)
    with regular(path) as source:
        magic = source.read(8)
        source.seek(0)
        if magic.startswith(b'PK'):
            directory_limits(source)
            with zipfile.ZipFile(source) as archive:
                for member in archive.infolist():
                    mode = member.external_attr >> 16
                    kind = stat.S_IFMT(mode)
                    directory = member.is_dir()
                    if (member.filename != member.orig_filename
                            or member.flag_bits & 1
                            or kind not in (0, stat.S_IFREG, stat.S_IFDIR)
                            or (kind == stat.S_IFDIR and not directory)
                            or (kind == stat.S_IFREG and directory)
                            or (member.external_attr & 0x10 and not directory)):
                        raise Unavailable('Linked, encrypted or special ZIP member')
                    with archive.open(member) as stream:
                        consume(member.filename, member.file_size, member.is_dir(), stream)
        elif magic.startswith((b'Rar!\x1a\x07', b'7z\xbc\xaf\x27\x1c')):
            from archive_backend import scan as native_scan
            native_scan(path, consume, MAX_MEMBERS)
        else:
            # Compressed TAR wrappers remain unavailable until their complete
            # trailer/integrity is proved. tarfile may stop before that trailer.
            with tarfile.open(fileobj=source, mode='r:') as archive:
                for member in archive:
                    if not (member.isfile() or member.isdir()):
                        raise Unavailable('Linked or special TAR member')
                    if member.isdir():
                        consume(member.name, member.size, True, None)
                    else:
                        with archive.extractfile(member) as stream:
                            consume(member.name, member.size, False, stream)
                source.seek(archive.offset)
                padding = 0
                while block := source.read(1024 * 1024):
                    if block.strip(b'\0'):
                        raise Unavailable('Unverified trailing TAR contents')
                    padding += len(block)
                    if padding > MAX_BYTES:
                        raise Unavailable('TAR padding exceeds bounds')
                if padding < 1024 or padding % 512:
                    raise Unavailable('Missing complete TAR termination')
    pages = sorted((r['name'] for r in rows if not r['directory']
                    and PurePosixPath(r['name']).suffix.lower() in PAGE_EXTENSIONS),
                   key=natural_key)
    if not pages:
        raise Unavailable('Archive has no recognized pages')
    return dict(version=1, members=rows, pages=pages, payload=token(rows, pages))


def bounded_run(command, *, timeout=TIMEOUT, max_output=MAX_OUTPUT):
    """Bound stdout AND stderr allocation and execution, including hung pipes."""
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    deadline, output, total = time.monotonic() + timeout, bytearray(), 0
    try:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ)
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise Unavailable('Archive verification timed out')
                for key, _ in selector.select(remaining):
                    block = os.read(key.fileobj.fileno(), 65536)
                    if not block:
                        selector.unregister(key.fileobj)
                        continue
                    total += len(block)
                    if total > max_output:
                        raise Unavailable('Archive verification output exceeds bounds')
                    if key.fileobj is process.stdout:
                        output.extend(block)
            if process.wait(timeout=max(0.001, deadline - time.monotonic())):
                raise Unavailable('Complete archive verification unavailable')
        return bytes(output)
    except subprocess.TimeoutExpired as error:
        raise Unavailable('Archive verification timed out') from error
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        process.stdout.close()
        process.stderr.close()


def inventory(path, *, tool_root=TOOL_ROOT):
    """Return full source bindings and payload evidence; never an admission."""
    try:
        deadline = time.monotonic() + TIMEOUT
        before, digest = file_hash(path, deadline=deadline)
        raw = bounded_run([sys.executable, '-I', str(Path(__file__).resolve()),
                           '--inventory', str(path), str(tool_root)],
                          timeout=max(0.001, deadline - time.monotonic()))
        value = decode_json(raw)
        after, current = file_hash(path, deadline=deadline)
        if before != after or digest != current:
            raise Unavailable('Archive changed during inventory')
        validate(value)
        value.update(source_sha256=digest, source_signature=before)
        return value
    except (OSError, ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise Unavailable('Stable complete publication payload evidence unavailable') from error


# Registry reads are deliberately independent of Store construction: Store opens
# with O_CREAT, which must never recreate lost correction authority.
REGISTRY_LIMIT = 512
REGISTRY_BYTES = 32 * 1024 ** 2
REGISTRY_KINDS = frozenset(('publication_attestation', 'publication_census', 'publication_intent'))


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def digest_value(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def exact_owner(value):
    fields = {'table', 'issueid', 'parentcomicid', 'releasecomicid'}
    if (not isinstance(value, dict) or set(value) != fields
            or value['table'] not in ('issues', 'annuals')
            or any(not isinstance(value[key], str)
                   or re.fullmatch('[1-9][0-9]{0,15}', value[key]) is None
                   for key in fields - {'table'})
            or (value['table'] == 'issues'
                and value['parentcomicid'] != value['releasecomicid'])):
        raise Unavailable('Invalid exact publication owner')
    return value


def attestation(value):
    fields = {'version', 'epoch', 'prior_revision', 'inventory', 'allowed',
              'rejected', 'evidence', 'observed', 'intent', 'created'}
    if (not isinstance(value, dict) or set(value) != fields
            or type(value['version']) is not int or value['version'] != 1
            or not digest_value(value['epoch']) or not digest_value(value['intent'])
            or type(value['prior_revision']) is not int or value['prior_revision'] < 0
            or type(value['created']) is not int or value['created'] < 0):
        raise Unavailable('Invalid correction attestation')
    validate(value['inventory'])
    owners = []
    for kind in ('allowed', 'rejected'):
        group = value[kind]
        if not isinstance(group, list) or not group or len(group) > 8:
            raise Unavailable('Correction requires bounded explicit owners')
        owners.extend(canonical_digest(exact_owner(owner)) for owner in group)
    if len(owners) > 8 or len(owners) != len(set(owners)):
        raise Unavailable('Duplicate or contradictory correction owners')
    evidence = value['evidence']
    if (not isinstance(evidence, dict) or set(evidence) != {'sha256', 'description'}
            or not digest_value(evidence['sha256'])
            or not isinstance(evidence['description'], str)
            or not 1 <= len(evidence['description'].encode('utf-8')) <= 2048):
        raise Unavailable('Invalid reviewed evidence binding')
    observed = value['observed']
    if not isinstance(observed, list) or len(observed) != len(value['allowed']):
        raise Unavailable('Missing observed correct-owner facts')
    for owner, facts in zip(value['allowed'], observed):
        if (not isinstance(facts, dict)
                or set(facts) != {'owner', 'source_sha256', 'signature', 'catalog'}
                or facts['owner'] != owner or not digest_value(facts['source_sha256'])
                or not isinstance(facts['signature'], list)
                or len(facts['signature']) != 9
                or any(type(v) is not int or v < 0 for v in facts['signature'])
                or not isinstance(facts['catalog'], dict) or not facts['catalog']):
            raise Unavailable('Invalid observed correct-owner facts')
    return canonical_digest(value)


def complete_census(db):
    """Validate all authority rows in one caller-owned SQLite read snapshot."""
    count, size = db.execute("SELECT count(*),coalesce(sum(length(CAST(value AS BLOB))),0) "
        "FROM records WHERE substr(CAST(kind AS TEXT),1,12)='publication_'").fetchone()
    if count > REGISTRY_LIMIT + INTENT_LIMIT + 1 or size > REGISTRY_BYTES:
        raise Unavailable('Correction census exceeds v1 bounds')
    rows = db.execute("SELECT kind,key,value FROM records WHERE substr(CAST(kind AS TEXT),1,12)='publication_' "
                      'ORDER BY kind,key').fetchmany(REGISTRY_LIMIT + INTENT_LIMIT + 2)
    if len(rows) > REGISTRY_LIMIT + INTENT_LIMIT + 1:
        raise Unavailable('Correction census exceeds v1 bounds')
    records, census, size, intents = {}, None, 0, 0
    for kind, key, raw in rows:
        if any(not isinstance(value, str) for value in (kind, key, raw)):
            raise Unavailable('Malformed correction authority record')
        size += len(raw.encode('utf-8'))
        if size > REGISTRY_BYTES or kind not in REGISTRY_KINDS:
            raise Unavailable('Unknown or oversized correction authority')
        value = decode_json(raw)
        if kind == 'publication_intent':
            if len(raw.encode('utf-8')) > 65536:
                raise Unavailable('Initialization receipt exceeds bounds')
            intents += 1
            if intents > INTENT_LIMIT:
                raise Unavailable('Initialization intent history exceeds bounds')
            bootstrap_record(key, value)
            continue
        if kind == 'publication_census':
            if key != 'v1' or census is not None:
                raise Unavailable('Ambiguous correction census')
            census = value
        else:
            if not digest_value(key) or key != attestation(value):
                raise Unavailable('Correction attestation digest mismatch')
            if key in records:
                raise Unavailable('Duplicate correction attestation key')
            records[key] = value
    if len(records) > REGISTRY_LIMIT:
        raise Unavailable('Correction attestation census exceeds bounds')
    fields = {'version', 'epoch', 'revision', 'keys', 'digest'}
    if (not isinstance(census, dict) or set(census) != fields
            or type(census['version']) is not int or census['version'] != 1
            or not digest_value(census['epoch'])
            or type(census['revision']) is not int or census['revision'] < 0
            or census['revision'] != len(records)
            or census['keys'] != sorted(records)
            or census['digest'] != canonical_digest(sorted(records))):
        raise Unavailable('Missing or incomplete correction census')
    revisions, payload_owners = set(), {}
    for value in records.values():
        if value['epoch'] != census['epoch']:
            raise Unavailable('Foreign correction epoch')
        revisions.add(value['prior_revision'])
        payload = value['inventory']['payload']
        allowed, rejected = payload_owners.setdefault(payload, (set(), set()))
        allowed.update(canonical_digest(owner) for owner in value['allowed'])
        rejected.update(canonical_digest(owner) for owner in value['rejected'])
        if allowed & rejected:
            raise Unavailable('Contradictory immutable correction history')
    if revisions != set(range(census['revision'])):
        raise Unavailable('Missing correction revision history')
    return census, records


def registry_snapshot(database, marker):
    """Read existing authority only; prepared/missing state never admits media.

    The eventual writer adapter must hold its Writer before calling this helper.
    This function neither initializes nor recovers authority and never opens Store.
    """
    if __package__:
        from .workflow_store import LOCK
    else:
        from workflow_store import LOCK
    with LOCK:
        return _registry_snapshot(database, marker)


def _registry_snapshot(database, marker):
    import sqlite3
    database, marker = Path(database), Path(marker)
    try:
        with regular(database) as stream, regular(marker) as binding:
            before = signature(os.fstat(stream.fileno()))
            mark_before = signature(os.fstat(binding.fileno()))
            for info in (before, mark_before):
                if info[6] != os.geteuid() or stat.S_IMODE(info[5]) != 0o600 or info[8] != 1:
                    raise Unavailable('Correction authority must be private and owned')
            sidecars = [Path(str(database) + suffix) for suffix in ('-wal', '-shm', '-journal')]
            header = stream.read(100)
            if (len(header) != 100 or header[:16] != b'SQLite format 3\0'
                    or header[18:20] != b'\x01\x01'
                    or any(os.path.lexists(path) for path in sidecars)):
                raise Unavailable('Correction authority requires complete rollback-journal state')
            raw = binding.read(MARKER_BYTES + 1)
            if len(raw) > MARKER_BYTES:
                raise Unavailable('Oversized correction marker')
            value = decode_json(raw.decode('utf-8'))
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
                db.execute('BEGIN')
                if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise Unavailable('Unreadable correction database')
                census, records = complete_census(db)
                if __package__:
                    from .media_writer import Writer
                else:
                    from media_writer import Writer
                current_writer = writer_identity(Writer(marker.parent, create=False))
                if not isinstance(value, dict) or not digest_value(value.get('initialization_intent')):
                    raise Unavailable('Missing initialization witness binding')
                initialization_witness(db, value['initialization_intent'], census, before[:2], current_writer)
            expected = dict(version=1, phase='final', census=census,
                            initialization_intent=value['initialization_intent'],
                            database_identity=before[:2], writer_identity=current_writer)
            if canonical_digest(value) != canonical_digest(expected):
                raise Unavailable('Correction marker does not bind complete final state')
            if (signature(os.fstat(stream.fileno())) != before
                    or signature(database.lstat()) != before
                    or signature(os.fstat(binding.fileno())) != mark_before
                    or signature(marker.lstat()) != mark_before
                    or any(os.path.lexists(path) for path in sidecars)):
                raise Unavailable('Correction authority changed during read')
            return census, records
    except (OSError, sqlite3.Error, UnicodeError, ValueError, TypeError, KeyError, RecursionError) as error:
        raise Unavailable('Correction authority unavailable') from error



INTENT_LIMIT = 128
MARKER_BYTES = 131072


def writer_identity(writer):
    if __package__:
        from .media_writer import checked_file
    else:
        from media_writer import checked_file
    writer.validate_root()
    fd = checked_file(writer.lock)
    try:
        info = os.fstat(fd)
        lock = (info.st_dev, info.st_ino)
        if lock != writer.lock_identity:
            raise Unavailable('Writer lock identity changed')
        return list(writer.root_identity) + list(lock)
    finally:
        os.close(fd)


def database_stamp(path):
    with regular(path) as stream:
        info = signature(os.fstat(stream.fileno()))
        header = stream.read(100)
    if (info[6] != os.geteuid() or stat.S_IMODE(info[5]) != 0o600 or info[8] != 1
            or len(header) != 100 or header[:16] != b'SQLite format 3\0'
            or header[18:20] != b'\x01\x01'
            or any(os.path.lexists(str(path) + suffix) for suffix in ('-wal', '-shm', '-journal'))):
        raise Unavailable('Expected private complete rollback-journal database')
    return info


def empty_census(epoch):
    return dict(version=1, epoch=epoch, revision=0, keys=[], digest=canonical_digest([]))


def bootstrap_record(key, value):
    if (not isinstance(value, dict) or set(value) != {'plan', 'accepted', 'outcome'}
            or type(value['accepted']) is not bool
            or value['outcome'] not in ('prepared', 'accepted', 'committed', 'aborted')
            or value['accepted'] != (value['outcome'] != 'prepared')):
        raise Unavailable('Invalid initialization receipt')
    plan = value['plan']
    if (not isinstance(plan, dict)
            or set(plan) != {'version', 'action', 'epoch', 'binding', 'backup', 'new'}
            or type(plan['version']) is not int or plan['version'] != 1
            or plan['action'] != 'bootstrap' or not digest_value(plan['epoch'])
            or canonical_digest(plan['new']) != canonical_digest(empty_census(plan['epoch']))
            or key != canonical_digest(plan)):
        raise Unavailable('Invalid immutable initialization plan')
    binding = plan['binding']
    if (not isinstance(binding, dict)
            or set(binding) != {'database_identity', 'writer_identity', 'schema', 'workflow', 'pending'}
            or not digest_value(binding['schema'])):
        raise Unavailable('Invalid initialization state binding')
    for field, count in (('database_identity', 2), ('writer_identity', 4)):
        items = binding[field]
        if (not isinstance(items, list) or len(items) != count
                or any(type(item) is not int or item < 0 for item in items)):
            raise Unavailable('Invalid initialization filesystem identity')
    workflow = binding['workflow']
    if (not isinstance(workflow, dict) or set(workflow) != {'version', 'count', 'digest'}
            or type(workflow['version']) is not int or workflow['version'] != 1
            or type(workflow['count']) is not int or not 0 <= workflow['count'] <= 100000
            or not digest_value(workflow['digest'])):
        raise Unavailable('Invalid protected workflow binding')
    pending = binding['pending']
    if not isinstance(pending, dict) or set(pending) != {'normalizer', 'tagger', 'release'}:
        raise Unavailable('Invalid existing publication fence binding')
    for stamp in pending.values():
        if stamp is not None and (not isinstance(stamp, list) or len(stamp) != 9
                or any(type(item) is not int or item < 0 for item in stamp)):
            raise Unavailable('Invalid existing publication fence signature')
    backup = plan['backup']
    if (not isinstance(backup, dict)
            or set(backup) != {'manifest_sha256', 'restore_sha256', 'description'}
            or not digest_value(backup['manifest_sha256']) or not digest_value(backup['restore_sha256'])
            or not isinstance(backup['description'], str)
            or not 1 <= len(backup['description'].encode('utf-8')) <= 1024):
        raise Unavailable('Reviewed restore evidence is required')
    return plan


def workflow_schema(db):
    tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = [tuple(row) for row in db.execute('PRAGMA table_info(records)')]
    expected = [(0, 'kind', 'TEXT', 1, None, 1), (1, 'key', 'TEXT', 1, None, 2),
                (2, 'value', 'TEXT', 1, None, 0), (3, 'updated', 'REAL', 1, None, 0)]
    if (tables != {'events', 'records'} or columns != expected
            or db.execute("SELECT count(*) FROM sqlite_master WHERE type IN ('view','trigger')").fetchone()[0]):
        raise Unavailable('Unsupported workflow authority schema')
    return canonical_digest([list(row) for row in db.execute(
        'SELECT type,name,tbl_name,sql FROM sqlite_master ORDER BY type,name')])


def initialization_witness(db, token, census, identity, writer):
    rows = db.execute("SELECT key,value FROM records WHERE kind='publication_intent'").fetchall()
    committed = []
    for key, raw in rows:
        value = decode_json(raw)
        plan = bootstrap_record(key, value)
        if value['outcome'] == 'accepted':
            raise Unavailable('Unfinished initialization blocks admission')
        if value['outcome'] == 'committed':
            committed.append(key)
            if (key != token or plan['epoch'] != census['epoch']
                    or plan['binding']['database_identity'] != identity
                    or plan['binding']['writer_identity'] != writer
                    or plan['binding']['schema'] != workflow_schema(db)):
                raise Unavailable('Foreign initialization witness')
    if committed != [token]:
        raise Unavailable('Missing unique committed initialization witness')


def state_errors(function):
    from functools import wraps
    @wraps(function)
    def wrapped(*args, **kwargs):
        import sqlite3
        try:
            return function(*args, **kwargs)
        except Unavailable:
            raise
        except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
            raise Unavailable('Initialization state unavailable') from error
    return wrapped


class RegistryState:
    """Explicit reviewed bootstrap only; no media recovery or API authorization.

    The future primary-key adapter must authenticate acceptance. These methods
    own Writer -> workflow LOCK -> SQLite, and never call ordinary native
    operation/replay. Existing fences are bound and preserved, not cleared.
    """
    @state_errors
    def __init__(self, database, writer):
        self.database = Path(database)
        self.writer = writer
        self.identity = database_stamp(self.database)[:2]
        self.writer_binding = writer_identity(writer)
        self.marker = writer.root / 'publication-v1.json'

    def _binding(self, db):
        if __package__:
            from .workflow_store import protected_snapshot
        else:
            from workflow_store import protected_snapshot
        pending = {}
        for name, path, args in (('normalizer', self.writer.pending, {}),
                ('tagger', self.writer.tagger_pending, {'tagger': True}),
                ('release', self.writer.release_pending, {'release': True})):
            pending[name] = signature(path.lstat()) if self.writer.fenced(**args) else None
        return dict(database_identity=self.identity, writer_identity=self.writer_binding,
                    schema=workflow_schema(db), workflow=protected_snapshot(db), pending=pending)

    @contextmanager
    def _session(self):
        import sqlite3
        if __package__:
            from .workflow_store import LOCK
        else:
            from workflow_store import LOCK
        with self.writer.hold(allow_pending=True, allow_tagger_pending=True,
                              allow_release_pending=True):
            with LOCK:
                if (database_stamp(self.database)[:2] != self.identity
                        or writer_identity(self.writer) != self.writer_binding):
                    raise Unavailable('Initialization filesystem identity changed')
                with closing(sqlite3.connect(self.database.as_uri() + '?mode=rw', uri=True)) as db:
                    db.execute('PRAGMA synchronous=FULL')
                    db.execute('BEGIN IMMEDIATE')
                    try:
                        workflow_schema(db)
                        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                            raise Unavailable('Unreadable workflow database')
                        yield db
                    finally:
                        db.rollback()
                if database_stamp(self.database)[:2] != self.identity:
                    raise Unavailable('Initialization database was replaced')

    def _empty(self, db, *, own=None):
        count, size = db.execute("SELECT count(*),coalesce(sum(length(CAST(value AS BLOB))),0) FROM records WHERE substr(CAST(kind AS TEXT),1,12)='publication_'").fetchone()
        if count > INTENT_LIMIT or size > REGISTRY_BYTES:
            raise Unavailable('Initialization authority exceeds bounds')
        rows = db.execute("SELECT kind,key,value FROM records WHERE "
                          "substr(CAST(kind AS TEXT),1,12)='publication_'").fetchmany(INTENT_LIMIT + 1)
        if len(rows) > INTENT_LIMIT:
            raise Unavailable('Initialization intent history exceeds bounds')
        for kind, key, raw in rows:
            if kind != 'publication_intent' or not isinstance(raw, str):
                raise Unavailable('Existing correction authority cannot be reinitialized')
            record = decode_json(raw);bootstrap_record(key, record)
            if record['accepted'] and record['outcome'] != 'aborted' and (key != own or record['outcome'] != 'accepted'):
                raise Unavailable('Prior accepted initialization requires exact recovery')

    def _record(self, db, token):
        row = db.execute("SELECT value FROM records WHERE kind='publication_intent' AND key=? AND typeof(value)='text' AND length(CAST(value AS BLOB))<=65536", (token,)).fetchone()
        if row is None or not isinstance(row[0], str):
            raise Unavailable('Missing initialization receipt')
        value = decode_json(row[0]);plan = bootstrap_record(token, value)
        if (plan['binding']['database_identity'] != self.identity
                or plan['binding']['writer_identity'] != self.writer_binding):
            raise Unavailable('Initialization receipt belongs to foreign state')
        return value

    def _save(self, db, token, record):
        # Only the accepted/outcome envelope changes; the digest-bound plan does not.
        original = self._record(db, token)
        if canonical_digest(original['plan']) != canonical_digest(record['plan']):
            raise Unavailable('Immutable initialization plan changed')
        bootstrap_record(token, record)
        transitions = {'prepared': {'accepted'}, 'accepted': {'accepted', 'committed', 'aborted'},
                       'committed': {'committed'}, 'aborted': {'aborted'}}
        if record['outcome'] not in transitions[original['outcome']]:
            raise Unavailable('Initialization outcome is terminal')
        db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                   (compact(record).decode('utf-8'), token))

    @state_errors
    def prepare_bootstrap(self, backup, *, epoch):
        with self._session() as db:
            if os.path.lexists(self.marker):
                raise Unavailable('Existing initialization marker requires reconciliation')
            self._empty(db)
            plan = dict(version=1, action='bootstrap', epoch=epoch, binding=self._binding(db),
                        backup=backup, new=empty_census(epoch))
            token = canonical_digest(plan)
            record = dict(plan=plan, accepted=False, outcome='prepared')
            bootstrap_record(token, record)
            if db.execute("SELECT count(*) FROM records WHERE kind='publication_intent'").fetchone()[0] >= INTENT_LIMIT:
                raise Unavailable('Initialization intent history exceeds bounds')
            db.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?)',
                ('publication_intent', token, compact(record).decode('utf-8'), time.time()))
            if self._record(db, token) != record:
                raise Unavailable('Initialization intent replay differs')
            db.commit()
            return token

    def _prepared(self, token, plan):
        return dict(version=1, phase='prepared', intent=token, old=None, new=plan['new'],
                    database_identity=self.identity, writer_identity=self.writer_binding)

    def final_marker(self, census, token):
        return dict(version=1, phase='final', census=census, initialization_intent=token,
                    database_identity=self.identity, writer_identity=self.writer_binding)

    def _read_marker(self):
        with regular(self.marker) as stream:
            info = signature(os.fstat(stream.fileno()))
            if info[6] != os.geteuid() or stat.S_IMODE(info[5]) != 0o600 or info[8] != 1:
                raise Unavailable('Initialization marker must be private and owned')
            raw = stream.read(MARKER_BYTES + 1)
            if len(raw) > MARKER_BYTES:
                raise Unavailable('Initialization marker exceeds bounds')
            if signature(self.marker.lstat()) != info:
                raise Unavailable('Initialization marker changed')
        value = decode_json(raw.decode('utf-8'))
        if not isinstance(value, dict):
            raise Unavailable('Expected initialization marker object')
        return value

    def _publish_marker(self, value, phase, boundary, *, expected):
        import secrets
        if __package__:
            from .media_writer import sync
        else:
            from media_writer import sync
        self.writer.validate_root()
        def check_previous():
            if expected is None:
                if os.path.lexists(self.marker):
                    raise Unavailable('Initialization marker appeared unexpectedly')
            elif canonical_digest(self._read_marker()) != canonical_digest(expected):
                raise Unavailable('Initialization marker changed before publication')
            if (database_stamp(self.database)[:2] != self.identity
                    or writer_identity(self.writer) != self.writer_binding):
                raise Unavailable('Initialization authority identity changed')
        check_previous()
        raw = compact(value)
        if len(raw) > MARKER_BYTES:
            raise Unavailable('Initialization marker exceeds bounds')
        temporary = self.writer.root / ('.publication-v1-' + secrets.token_hex(16) + '.tmp')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(raw);stream.flush();os.fsync(stream.fileno())
            boundary(phase + '-file')
            check_previous()
            os.replace(temporary, self.marker);sync(self.writer.root)
            boundary(phase + '-marker')
        finally:
            if temporary.exists():temporary.unlink();sync(self.writer.root)

    def _commit_census(self, db, token, record, boundary):
        if database_stamp(self.database)[:2] != self.identity:
            raise Unavailable('Initialization database was replaced')
        db.execute('BEGIN IMMEDIATE')
        record = dict(record, outcome='committed')
        self._save(db, token, record)
        db.execute('INSERT INTO records VALUES (?,?,?,?)',
            ('publication_census', 'v1', compact(record['plan']['new']).decode('utf-8'), time.time()))
        complete_census(db)
        boundary('sqlite-pending')
        db.commit();boundary('sqlite-committed')
        return self._finalize(db, token, record, boundary)

    def _finalize(self, db, token, record, boundary):
        if database_stamp(self.database)[:2] != self.identity:
            raise Unavailable('Initialization database was replaced')
        db.execute('BEGIN')
        census, _ = complete_census(db)
        initialization_witness(db, token, census, self.identity, self.writer_binding)
        if canonical_digest(census) != canonical_digest(record['plan']['new']):
            raise Unavailable('Committed initialization census changed')
        db.commit()
        self._publish_marker(self.final_marker(census, token), 'final', boundary,
                             expected=self._prepared(token, record['plan']))
        return record['plan']['new']

    @state_errors
    def initialize(self, token, *, accepted_token, boundary=lambda _: None):
        if not digest_value(token) or accepted_token != token:
            raise Unavailable('Explicit exact reviewed initialization acceptance required')
        with self._session() as db:
            record = self._record(db, token)
            if os.path.lexists(self.marker):
                value = self._read_marker()
                if value.get('phase') == 'final' and value.get('initialization_intent') == token:
                    return _registry_snapshot(self.database, self.marker)[0]
                raise Unavailable('Pending initialization requires exact recovery')
            if record['outcome'] not in ('prepared', 'accepted'):
                raise Unavailable('Initialization receipt is terminal')
            self._empty(db, own=token)
            if canonical_digest(self._binding(db)) != canonical_digest(record['plan']['binding']):
                raise Unavailable('Reviewed initialization state is stale')
            record = dict(record, accepted=True, outcome='accepted')
            self._save(db, token, record);db.commit();boundary('intent-accepted')
            self._publish_marker(self._prepared(token, record['plan']), 'prepared', boundary, expected=None)
            return self._commit_census(db, token, record, boundary)

    @state_errors
    def recover_bootstrap(self, token, *, abort=False, boundary=lambda _: None):
        if not digest_value(token) or type(abort) is not bool:
            raise Unavailable('Invalid exact initialization recovery')
        with self._session() as db:
            record = self._record(db, token)
            if not record['accepted']:
                raise Unavailable('Unaccepted initialization cannot recover')
            if record['outcome'] == 'aborted' and not os.path.lexists(self.marker):
                self._empty(db, own=token)
                return None
            if canonical_digest(self._read_marker()) != canonical_digest(self._prepared(token, record['plan'])):
                raise Unavailable('Missing or foreign prepared initialization marker')
            count = db.execute("SELECT count(*) FROM records WHERE kind='publication_census'").fetchone()[0]
            if count:
                if abort:
                    raise Unavailable('Committed initialization must finalize, not abort')
                census, _ = complete_census(db)
                if (record['outcome'] != 'committed'
                        or canonical_digest(census) != canonical_digest(record['plan']['new'])):
                    raise Unavailable('Mixed initialization state requires review')
                db.commit()
                return self._finalize(db, token, record, boundary)
            self._empty(db, own=token)
            if abort or record['outcome'] == 'aborted':
                if record['outcome'] != 'aborted':
                    self._save(db, token, dict(record, outcome='aborted'))
                db.commit();boundary('abort-committed')
                if __package__:
                    from .media_writer import sync
                else:
                    from media_writer import sync
                if canonical_digest(self._read_marker()) != canonical_digest(self._prepared(token, record['plan'])):
                    raise Unavailable('Prepared initialization marker changed during abort')
                self.marker.unlink();sync(self.writer.root);boundary('abort-marker')
                return None
            if canonical_digest(self._binding(db)) != canonical_digest(record['plan']['binding']):
                raise Unavailable('Accepted initialization facts are stale')
            db.commit()
            return self._commit_census(db, token, record, boundary)

    @state_errors
    def snapshot(self):
        with self.writer.hold(allow_pending=True, allow_tagger_pending=True, allow_release_pending=True):
            return registry_snapshot(self.database, self.marker)


if __name__ == '__main__':
    import resource
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 ** 2, 512 * 1024 ** 2))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    if len(sys.argv) != 4 or sys.argv[1] != '--inventory':
        sys.exit(2)
    try:
        sys.stdout.buffer.write(compact(scan(sys.argv[2], sys.argv[3])))
    except Exception:
        # Protocol failures reveal neither filesystem paths nor private member names.
        sys.exit(1)

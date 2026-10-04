"""Bounded read-only publication payload evidence.

This foundation does not admit corrections or authorize publication. Registry,
owner and writer admission must validate this evidence before any mutation.
"""

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

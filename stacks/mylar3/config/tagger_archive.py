"""Verify and reconcile disposable CBZs. This module never publishes over a source."""

import copy
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import struct
import zipfile

from tagger_metadata import MAX_XML, parse, reconcile

MAX_MEMBERS = 4096
MAX_UNPACKED = 4 * 1024 ** 3
MAX_MEMBER = 512 * 1024 ** 2
MAX_DIRECTORY = 8 * 1024 ** 2
PAGES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.avif', '.bmp', '.tif', '.tiff'}
XML = 'ComicInfo.xml'


@dataclass(frozen=True)
class Archive:
    members: tuple
    comment: bytes
    xml: bytes | None
    identity: tuple
    mode: int
    uid: int
    gid: int


def identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def regular(path):
    stream = os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb')
    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
        stream.close()
        raise ValueError('Expected regular archive')
    return stream


def directory_limits(stream):
    """Bound ZipFile's central-directory allocation before constructing it."""
    size = os.fstat(stream.fileno()).st_size
    if size > MAX_UNPACKED or size < 22:
        raise ValueError('Unsupported archive size')
    stream.seek(max(0, size - 65557))
    tail = stream.read(65557)
    offset = tail.rfind(b'PK\x05\x06')
    if offset < 0 or len(tail) - offset < 22:
        raise ValueError('Missing archive directory')
    _, disk, start_disk, disk_count, count, length, start, comment = struct.unpack_from('<4s4H2LH', tail, offset)
    footer_offset = size - len(tail) + offset
    # A maximum-length comment leaves the locator outside the tail buffer.
    stream.seek(max(0, footer_offset - 20))
    zip64 = footer_offset >= 20 and stream.read(4) == b'PK\x06\x07'
    if (disk or start_disk or disk_count != count or not 0 < count <= MAX_MEMBERS
            or length > MAX_DIRECTORY or start == 0xffffffff
            or offset + 22 + comment != len(tail)
            or start + length > footer_offset or zip64):
        raise ValueError('Unsupported or oversized archive directory')
    stream.seek(0)


def snapshot(path):
    """Read every member with CRC checks and fixed decompressed-size bounds."""
    archive_path = Path(path)
    with regular(path) as stream:
        before = os.fstat(stream.fileno())
        directory_limits(stream)
        with zipfile.ZipFile(stream) as archive:
            infos = archive.infolist()
            if not infos or len(infos) > MAX_MEMBERS:
                raise ValueError('Unsupported archive member count')
            names, total, pages, members, xml = set(), 0, 0, [], None
            for info in infos:
                name = info.filename
                member_path = PurePosixPath(name)
                if (not name or name != info.orig_filename or '\\' in name or '\0' in name or ':' in name
                        or member_path.is_absolute() or '..' in member_path.parts or name in names
                        or name.rstrip('/') != member_path.as_posix()
                        or stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1):
                    raise ValueError('Unsafe or ambiguous archive member')
                names.add(name)
                if member_path.name.lower() == XML.lower() and name != XML:
                    raise ValueError('Ambiguous metadata location')
                limit = MAX_XML if name == XML else MAX_MEMBER
                total += info.file_size
                if info.file_size > limit or total > MAX_UNPACKED:
                    raise ValueError('Archive exceeds verification limits')
                digest, received, chunks = hashlib.sha256(), 0, []
                with archive.open(info) as member:
                    while block := member.read(min(1024 * 1024, limit + 1)):
                        received += len(block)
                        if received > limit or received > info.file_size:
                            raise ValueError('Archive member exceeds declared size')
                        digest.update(block)
                        if name == XML:
                            chunks.append(block)
                if received != info.file_size:
                    raise ValueError('Incomplete archive member')
                if name == XML:
                    xml = b''.join(chunks)
                    parse(xml)
                else:
                    members.append((name, received, digest.hexdigest()))
                    pages += not info.is_dir() and member_path.suffix.lower() in PAGES
            if not pages:
                raise ValueError('Archive has no comic pages')
            comment = archive.comment
        after = os.fstat(stream.fileno())
        if identity(before) != identity(after) or identity(before) != identity(archive_path.lstat()):
            raise ValueError('Archive changed during verification')
    return Archive(tuple(members), comment, xml, identity(before), stat.S_IMODE(before.st_mode), before.st_uid, before.st_gid)


def semantic(raw):
    def node(value):
        text = value.text or ''
        if len(value) and not text.strip():
            text = ''
        tail = value.tail or ''
        return (value.tag if isinstance(value.tag, str) else '#comment',
                tuple(sorted(value.attrib.items())), text, tail if tail.strip() else '',
                tuple(node(child) for child in value))
    root = parse(raw)
    value = node(root)
    # ComicInfo field order is insignificant; page/bookmark order is preserved.
    return value[:4] + (tuple(sorted(value[4], key=lambda child: child[0])),)


def prepare(original, tagged, output, *, updates=None, replace_fields=()):
    """Create a verified output only when metadata changes; retain both inputs.

    Return added/updated/unchanged, never an import or publication receipt. The
    future publication owner must recheck source identity and persist intent.
    """
    original, tagged, output = Path(original), Path(tagged), Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError('Output must be a new operation file')
    old, new = snapshot(original), snapshot(tagged)
    if old.members != new.members or old.comment != new.comment:
        raise ValueError('Tagger changed non-metadata contents')
    if not new.xml or not any(isinstance(child.tag, str) and child.tag != 'Pages'
                              and (child.text or '').strip() for child in parse(new.xml)):
        raise ValueError('Tagger produced no descriptive metadata')
    merged = reconcile(old.xml, new.xml, updates=updates, replace_fields=replace_fields)
    if identity(original.lstat()) != old.identity:
        raise ValueError('Source changed before reconciliation')
    if old.xml is not None and semantic(old.xml) == semantic(merged):
        return 'unchanged'
    created = None
    try:
        with output.open('xb') as target:
            created = identity(os.fstat(target.fileno()))[:2]
            with regular(original) as source:
                if identity(os.fstat(source.fileno())) != old.identity:
                    raise ValueError('Source changed before reconciliation')
                directory_limits(source)
                with zipfile.ZipFile(source) as source_zip, zipfile.ZipFile(target, 'w') as result:
                    result.comment = old.comment
                    xml_info = None
                    for info in source_zip.infolist():
                        if info.filename == XML:
                            xml_info = copy.copy(info)
                            continue
                        with source_zip.open(info) as member, result.open(copy.copy(info), 'w') as dest:
                            while block := member.read(1024 * 1024):
                                dest.write(block)
                    result.writestr(xml_info or XML, merged,
                                    compress_type=xml_info.compress_type if xml_info else zipfile.ZIP_DEFLATED)
                if identity(os.fstat(source.fileno())) != old.identity:
                    raise ValueError('Source changed during reconciliation')
            target.flush()
            os.fchown(target.fileno(), old.uid, old.gid)
            os.fchmod(target.fileno(), old.mode)
            os.fsync(target.fileno())
        verified = snapshot(output)
        if (verified.members != old.members or verified.comment != old.comment
                or verified.xml != merged or verified.mode != old.mode
                or verified.identity[:2] != created
                or (verified.uid, verified.gid) != (old.uid, old.gid)
                or identity(original.lstat()) != old.identity):
            raise ValueError('Reconciled archive failed preservation checks')
        return 'updated' if old.xml is not None else 'added'
    except BaseException:
        if created is not None:
            try:
                if identity(output.lstat())[:2] == created:
                    output.unlink()
            except FileNotFoundError:
                pass
        raise

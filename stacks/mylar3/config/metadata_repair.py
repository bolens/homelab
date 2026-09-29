"""Reconcile agreeing root/nested ComicInfo in a disposable, verified archive."""
import copy
from decimal import Decimal, InvalidOperation
import os
from pathlib import PurePosixPath
import re
import shutil
import struct
import zipfile
import xml.etree.ElementTree as ET

if __package__:
    from . import tagger_archive as archive, tagger_metadata as metadata
else:
    import tagger_archive as archive
    import tagger_metadata as metadata


def issue_identity(root):
    series = ' '.join((root.findtext('Series') or '').casefold().split())
    number = (root.findtext('Number') or '').strip().casefold()
    if not series or not number:
        raise ValueError('Metadata lacks series or issue identity')
    try:
        value = Decimal(number)
        if not value.is_finite():
            raise ValueError('Invalid issue number')
        number = str(value.normalize())
    except InvalidOperation:
        pass
    return series, number


def merge(root_xml, nested_xml):
    root, nested = metadata.parse(root_xml), metadata.parse(nested_xml)
    if issue_identity(root) != issue_identity(nested):
        raise ValueError('Nested metadata has a different issue identity')
    for field in ('Volume',):
        a, b = root.findtext(field), nested.findtext(field)
        if a and b and a.strip().casefold() != b.strip().casefold():
            raise ValueError('Nested metadata has conflicting '+field)
    ids = [re.findall(r'ComicVineIssueID\s*[:=]\s*(\d+)', x.findtext('Notes') or '', re.I)
           for x in (root, nested)]
    if ids[0] and ids[1] and set(ids[0]) != set(ids[1]):
        raise ValueError('Nested metadata has conflicting provider identity')
    # Nested Pages can refer to a different ordering, and arc names/numbers must
    # stay paired. Preserve them in provenance, never infer or transplant them.
    for child in list(nested):
        if child.tag in ('Pages', 'StoryArc', 'StoryArcNumber', 'SeriesGroup'):
            nested.remove(child)
    return metadata.reconcile(root_xml, ET.tostring(nested, encoding='utf-8'))


def layout(z):
    names = z.namelist()
    copies = [n for n in names if PurePosixPath(n).name.casefold() == 'comicinfo.xml']
    if len(copies) != 2 or 'ComicInfo.xml' not in copies:
        raise ValueError('Expected exactly one root and one nested ComicInfo')
    nested = next(n for n in copies if n != 'ComicInfo.xml')
    if '/' not in nested:
        raise ValueError('Case-variant root metadata requires review')
    target = str(PurePosixPath(nested).with_name('SourceMetadata.xml'))
    if target.casefold() in {n.casefold() for n in names}:
        raise ValueError('Source metadata provenance name already exists')
    # A Unicode-path extra field would still advertise the old metadata name.
    extra = z.getinfo(nested).extra
    while extra:
        if len(extra) < 4:
            raise ValueError('Invalid ZIP extra field')
        kind, size = struct.unpack('<HH', extra[:4])
        if len(extra) < size+4 or kind == 0x7075:
            raise ValueError('Unsupported renamed-member path attributes')
        extra = extra[size+4:]
    return nested, target, merge(z.read('ComicInfo.xml'), z.read(nested))


def prepare(original, output):
    old = archive.snapshot(original, allow_nested_metadata=True)
    with archive.regular(original) as stream, zipfile.ZipFile(stream) as source:
        nested, target, merged = layout(source)
        if archive.identity(os.fstat(stream.fileno())) != old.identity:
            raise ValueError('Source changed before repair')
        with zipfile.ZipFile(output, 'x') as dest:
            dest.comment = source.comment
            for info in source.infolist():
                item = copy.copy(info)
                if info.filename == 'ComicInfo.xml':
                    dest.writestr(item, merged)
                else:
                    if info.filename == nested:
                        item.filename = target
                    with source.open(info) as reader, dest.open(item, 'w') as writer:
                        shutil.copyfileobj(reader, writer, 1024*1024)
        if archive.identity(os.fstat(stream.fileno())) != old.identity:
            raise ValueError('Source changed during repair')
    os.chmod(output, old.mode)
    os.chown(output, old.uid, old.gid)
    verified = archive.snapshot(output)
    expected = tuple((target if n == nested else n, size, digest) for n, size, digest in old.members)
    attributes = tuple((target if row[0] == nested else row[0], *row[1:]) for row in old.attributes)
    if (verified.members != expected or verified.comment != old.comment or verified.xml != merged
            or verified.attributes != attributes or verified.mode != old.mode
            or verified.uid != old.uid or verified.gid != old.gid):
        raise ValueError('Metadata repair preservation failed')
    return 'updated'

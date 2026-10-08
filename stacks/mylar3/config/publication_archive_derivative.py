"""Pure bounded ZIP32 spelling derivative. No file writing or live CLI operations."""
import binascii
import hashlib
import io
import json
from pathlib import Path
import stat
import struct
import time
import zipfile

PRODUCER_SHA = 'c46add9ed2b57c1f44ec4fe23db73189b77925bea01a247df9333b526bd95168'
MAX_SOURCE = 512 * 1024**2


def producer():
    if __package__:
        from . import publication_archive_layout as module
    else:
        import publication_archive_layout as module
    if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != PRODUCER_SHA:
        raise ValueError('producer-pin')
    return module


def independent(raw, guard, deadline, malformed=None):
    """Read every decoded member independently of the producer's inventory."""
    rows, metadata = [], {}
    total = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if not 0 < len(infos) <= guard.MAX_MEMBERS:
            raise ValueError('member-count')
        for index, info in enumerate(infos):
            if time.monotonic() >= deadline:
                raise ValueError('deadline')
            directory = info.is_dir()
            mode = stat.S_IFMT(info.external_attr >> 16)
            if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise ValueError('special-member')
            if index == malformed:
                if directory or mode != stat.S_IFDIR or not info.external_attr & 0x10:
                    raise ValueError('malformed-kind')
                directory = True
            elif (mode == stat.S_IFDIR or info.external_attr & 0x10) and not directory:
                raise ValueError('other-malformed-directory')
            if mode == stat.S_IFREG and directory:
                raise ValueError('regular-directory')
            name = guard.safe_name(info.filename, directory)
            if info.file_size > guard.MAX_MEMBER or total + info.file_size > guard.MAX_BYTES:
                raise ValueError('expanded-bound')
            if directory and (info.file_size or info.CRC):
                raise ValueError('nonempty-directory')
            h, crc, count, metadata_bytes = hashlib.sha256(), 0, 0, []
            with archive.open(info) as member:
                while True:
                    if time.monotonic() >= deadline:
                        raise ValueError('deadline')
                    chunk = member.read(1024**2)
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > info.file_size:
                        raise ValueError('expanded-size')
                    h.update(chunk)
                    crc = binascii.crc32(chunk, crc)
                    if name in guard.METADATA:
                        if count > guard.MAX_METADATA:
                            raise ValueError('metadata-bound')
                        metadata_bytes.append(chunk)
            if count != info.file_size or crc & 0xffffffff != info.CRC:
                raise ValueError('crc')
            total += count
            rows.append(dict(name=name, bytes=count, directory=directory, sha256=h.hexdigest()))
            if name in guard.METADATA:
                guard.metadata(name, b''.join(metadata_bytes))
                metadata[name] = h.hexdigest()
    files = {r['name'] for r in rows if not r['directory']}
    if any(parent.as_posix() in files for r in rows for parent in Path(r['name']).parents
           if parent.as_posix() != '.'):
        raise ValueError('file-parent-alias')
    pages = sorted([r['name'] for r in rows if not r['directory'] and
                    Path(r['name']).suffix.lower() in guard.PAGE_EXTENSIONS], key=guard.natural_key)
    inventory = dict(version=1, members=rows, pages=pages, payload=guard.token(rows, pages))
    guard.validate(inventory)
    return inventory, metadata


def derive(raw, witness, guard, deadline):
    """Return derivative bytes plus evidence; neither grants mutation/admission."""
    m = producer()
    check = m.check
    check(type(raw) is bytes and 0 < len(raw) <= MAX_SOURCE, 'bounded-source-bytes')
    check(type(deadline) in (float, int) and time.monotonic() < deadline, 'deadline')
    check(type(witness) is dict and witness.get('version') == 1 and
          witness.get('kind') == 'one-zip-directory-header-virtual-inventory', 'producer-witness')
    for key in ('ordinary_source_admission', 'native_grant', 'mutation_authority',
                'publication_acceptance', 'derivative_written', 'derivative_equivalence_verified',
                'purpose_integration_verified'):
        check(witness.get(key) is False, 'no-authority')
    source = witness['source']
    check(type(source) is dict and set(source) == {'path', 'signature9', 'sha256'} and
          type(source['signature9']) is list and len(source['signature9']) == 9 and
          all(type(x) is int for x in source['signature9']) and
          source['signature9'][2] == len(raw) and source['sha256'] == m.sha(raw), 'exact-source-bytes')
    entry = m.exact_entry(witness['entry'])
    headers, envelope = m.layout(io.BytesIO(raw), len(raw))
    index = entry['index']
    check(index < len(headers) and {k: headers[index][k] for k in entry} == entry, 'exact-entry')
    check(witness['zip_envelope'] == envelope and witness['all_members_crc_verified'] is True and
          witness['proposed_directory_name'] == entry['name'] + '/', 'witness-envelope')
    before, meta_before = independent(raw, guard, deadline, index)
    check(before == witness['virtual_original_inventory'] and
          meta_before == witness['root_metadata_sha256'], 'independent-source-inventory')
    commitments = witness['raw_header_commitments']
    check(type(commitments) is list and len(commitments) == len(headers), 'commitment-count')
    for row, commit, member in zip(headers, commitments, before['members']):
        check(commit == {**row, 'crc_verified': True, 'uncompressed_sha256': member['sha256'],
                         'virtual_directory': member['directory'],
                         'header_change_declared': row['index'] == index}, 'header-commitment')
    target = headers[index]
    local_at = target['header_offset']
    name_length = struct.unpack_from('<H', raw, local_at + 26)[0]
    check(name_length < 65535, 'name-length-overflow')
    insert = local_at + 30 + name_length
    local_header = bytearray(raw[local_at:local_at + 30])
    struct.pack_into('<H', local_header, 26, name_length + 1)
    local = raw[:local_at] + bytes(local_header) + raw[local_at + 30:insert] + b'/' + raw[insert:envelope['central_offset']]
    central_parts, pos = [], envelope['central_offset']
    for row in headers:
        nl, el, cl = struct.unpack_from('<3H', raw, pos + 28)
        length = 46 + nl + el + cl
        record = bytearray(raw[pos:pos + length])
        offset = row['header_offset'] + (row['header_offset'] > local_at)
        struct.pack_into('<L', record, 42, offset)
        if row['index'] == index:
            check(nl == name_length, 'name-length-match')
            struct.pack_into('<H', record, 28, nl + 1)
            record[46 + nl:46 + nl] = b'/'
        central_parts.append(bytes(record))
        pos += length
    central = b''.join(central_parts)
    footer = bytearray(raw[envelope['eocd_offset']:])
    struct.pack_into('<L', footer, 12, len(central))
    struct.pack_into('<L', footer, 16, len(local))
    derivative = local + central + bytes(footer)
    check(len(derivative) == len(raw) + 2, 'exact-growth')
    after_headers, after_envelope = m.layout(io.BytesIO(derivative), len(derivative))
    after, meta_after = independent(derivative, guard, deadline)
    check(before == after and meta_before == meta_after, 'member-page-payload-metadata-equality')
    # Reconstruct every original record from derivative by undoing only declared edits.
    # This separately proves all compressed payloads, timestamps, extras and comments.
    for old, new in zip(headers, after_headers):
        old_start, new_start = old['header_offset'], new['header_offset']
        old_chunk = raw[old_start:old['local_end']]
        new_chunk = bytearray(derivative[new_start:new['local_end']])
        if old['index'] == index:
            check(new['name'] == old['name'] + '/', 'directory-spelling')
            n = struct.unpack_from('<H', new_chunk, 26)[0]
            check(new_chunk[30 + n - 1] == 47, 'added-local-slash')
            del new_chunk[30 + n - 1]
            struct.pack_into('<H', new_chunk, 26, n - 1)
        check(bytes(new_chunk) == old_chunk, 'local-record-payload-exact')
    restored_central, pos = [], after_envelope['central_offset']
    for old in headers:
        nl, el, cl = struct.unpack_from('<3H', derivative, pos + 28)
        record = bytearray(derivative[pos:pos + 46 + nl + el + cl])
        struct.pack_into('<L', record, 42, old['header_offset'])
        if old['index'] == index:
            check(record[46 + nl - 1] == 47, 'added-central-slash')
            del record[46 + nl - 1]
            struct.pack_into('<H', record, 28, nl - 1)
        restored_central.append(bytes(record))
        pos += 46 + nl + el + cl
    check(b''.join(restored_central) == raw[envelope['central_offset']:envelope['eocd_offset']], 'central-records-exact')
    restored_footer = bytearray(derivative[after_envelope['eocd_offset']:])
    struct.pack_into('<L', restored_footer, 12, envelope['central_bytes'])
    struct.pack_into('<L', restored_footer, 16, envelope['central_offset'])
    check(bytes(restored_footer) == raw[envelope['eocd_offset']:], 'footer-comment-exact')
    check(time.monotonic() < deadline, 'terminal-deadline')
    evidence = dict(version=1, kind='zip32-directory-spelling-derivative-bytes',
                    producer_sha256=PRODUCER_SHA, source=witness['source'], entry=entry,
                    original_sha256=m.sha(raw), derivative_sha256=m.sha(derivative),
                    original_bytes=len(raw), derivative_bytes=len(derivative),
                    inventory=after, root_metadata_sha256=meta_after,
                    all_members_crc_verified_before_after=True,
                    compressed_payloads_and_other_header_bytes_preserved=True,
                    derivative_equivalence_verified=True, derivative_written=False,
                    ordinary_source_admission=False, native_grant=False,
                    mutation_authority=False, publication_acceptance=False,
                    purpose_integration_verified=False)
    json.dumps(evidence, sort_keys=True, allow_nan=False)
    return derivative, evidence


if __name__ == '__main__':
    print(json.dumps(dict(derive=False, mutation_authority=False, publication_acceptance=False)))

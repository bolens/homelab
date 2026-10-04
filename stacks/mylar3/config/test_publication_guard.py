"""Payload refusal and preservation controls without live application state."""

import hashlib
import gzip
import base64
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile
import zlib

import publication_guard as guard

TOOL_ROOT = os.environ.get('ARCHIVING_UTILS_ROOT', '/opt/archiving-utils')


class PayloadTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def archive(self, name='input.cbz', entries=None, compression=zipfile.ZIP_STORED):
        target = self.root / name
        entries = entries if entries is not None else [('01.jpg', b'one'), ('10.png', b'ten'),
            ('provenance/ComicInfo.xml', b'private'), ('ComicInfo.xml', b'<ComicInfo/>')]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', UserWarning)
            with zipfile.ZipFile(target, 'w', compression=compression) as archive:
                for member, raw in entries:
                    archive.writestr(member, raw)
        return target

    def check(self, path):
        return guard.inventory(path, tool_root=TOOL_ROOT)

    def test_fixed_vector_and_no_source_mutation(self):
        source = self.archive()
        before = source.read_bytes(), guard.signature(source.stat())
        value = self.check(source)
        self.assertEqual(value['payload'],
            '82367ae669301a8f9af31fab7e1ff5ce132d8cf212b61d0c414c05a4a88b6d9b')
        self.assertEqual(value['pages'], ['01.jpg', '10.png'])
        self.assertEqual((source.read_bytes(), guard.signature(source.stat())), before)
        self.assertEqual(value['source_sha256'], hashlib.sha256(before[0]).hexdigest())

    def test_recompression_retagging_header_order_and_directories(self):
        first = self.check(self.archive())
        entries = [('10.png', b'ten'), ('provenance/', b''),
                   ('ComicInfo.xml', b'<ComicInfo><Year>2026</Year></ComicInfo>'),
                   ('provenance/ComicInfo.xml', b'private'), ('01.jpg', b'one')]
        second = self.check(self.archive('retagged.cbz', entries, zipfile.ZIP_DEFLATED))
        self.assertEqual(first['payload'], second['payload'])
        self.assertNotEqual(first['source_sha256'], second['source_sha256'])
        self.assertTrue(any(row['directory'] for row in second['members']))

    def test_sidecar_and_page_changes_change_identity(self):
        first = self.check(self.archive())
        for member in ('10.png', 'provenance/ComicInfo.xml'):
            with self.subTest(member=member):
                entries = [('01.jpg', b'one'), ('10.png', b'ten'),
                           ('provenance/ComicInfo.xml', b'private')]
                entries = [(name, raw + b'changed' if name == member else raw)
                           for name, raw in entries]
                second = self.check(self.archive(member.replace('/', '-') + '.cbz', entries))
                self.assertNotEqual(first['payload'], second['payload'])

    def test_tar_and_zip_regular_payload_identity(self):
        zipped = self.check(self.archive())
        target = self.root / 'comic.cbt'
        with tarfile.open(target, 'w') as archive:
            for name, raw in [('01.jpg', b'one'), ('10.png', b'ten'),
                              ('provenance/ComicInfo.xml', b'private')]:
                info = tarfile.TarInfo(name)
                info.size = len(raw)
                archive.addfile(info, io.BytesIO(raw))
        self.assertEqual(self.check(target)['payload'], zipped['payload'])

    def test_native_rar4_rar5_and_7zip_with_fixed_payload_vector(self):
        # RAR fixtures are authored stored headers containing only our own
        # three-byte page. The 7z fixture contains the same authored bytes.
        name, data = b'01.jpg', b'one'
        def rar4_header(kind, flags, body):
            raw = struct.pack('<BHH', kind, flags, 7 + len(body)) + body
            return struct.pack('<H', zlib.crc32(raw) & 0xffff) + raw
        def rar5_block(raw):
            body = bytes([len(raw)]) + raw
            return struct.pack('<I', zlib.crc32(body)) + body
        rar4 = (b'Rar!\x1a\x07\x00' + rar4_header(0x73, 0, bytes(6))
            + rar4_header(0x74, 0x8000, struct.pack('<IIBIIBBHI', len(data), len(data),
                3, zlib.crc32(data), 0, 20, 0x30, len(name), 0o100644) + name)
            + data + rar4_header(0x7b, 0, b''))
        rar5 = (b'Rar!\x1a\x07\x01\x00' + rar5_block(b'\x01\x00\x00')
            + rar5_block(b'\x02\x02\x03\x04\x03\x20'
                + struct.pack('<I', zlib.crc32(data)) + b'\x00\x00\x06' + name)
            + data + rar5_block(b'\x05\x00\x00'))
        seven = base64.b64decode(
            'N3q8ryccAANwYwOYDQAAAAAAAABkAAAAAAAAAKP2ZM0AN5uI3lgj///3PEAA'
            'AQQGAAEJDQAHCwEAASMDAQEFXQAAgAAMAwAICgHxhmx6AAAFAREPADAAMQAu'
            'AGoAcABnAAAAFAoBAOmGTeEhVN0BEgoBAOmGTeEhVN0BEwoBANVTTeEhVN0B'
            'FQYBACCApIEAAA==')
        for name, raw in [('rar4.cbr', rar4), ('rar5.cbr', rar5), ('comic.cb7', seven)]:
            with self.subTest(name=name):
                source = self.root / name
                source.write_bytes(raw)
                self.assertEqual(self.check(source)['payload'],
                    'f3b9b8fbb15a74d27c2c157e48dc04856159c95e0666b08eef41f941e69bfb6a')
                if name.endswith('.cbr'):
                    source.write_bytes(raw.replace(b'one', b'bad', 1))
                else:
                    changed = bytearray(raw)
                    changed[40] ^= 1
                    source.write_bytes(changed)
                self.assertRaises(guard.Unavailable, self.check, source)

    def test_parent_protocol_refuses_partial_and_reordered_evidence(self):
        value = self.check(self.archive())
        value = {key: item for key, item in value.items() if key not in
                 ('source_sha256', 'source_signature')}
        for changed in (dict(value, version=True), dict(value, pages=[]),
                        dict(value, pages=list(reversed(value['pages']))),
                        dict(value, members=value['members'] + [value['members'][0]])):
            self.assertRaises(guard.Unavailable, guard.validate, changed)

    def test_supported_json_root_and_duplicates(self):
        json_tag = json.dumps({'ComicBookInfo/1.0': {'title': 'Different title'}}).encode()
        a = self.check(self.archive('xml.cbz', [('01.jpg', b'one')]))
        b = self.check(self.archive('json.cbz', [('01.jpg', b'one'), ('ComicBookInfo.json', json_tag)]))
        self.assertEqual(a['payload'], b['payload'])
        for raw in (b'{}', b'{"ComicBookInfo/1.0":{},"ComicBookInfo/1.0":{}}',
                    b'{"ComicBookInfo/1.0":{"bad":NaN}}'):
            with self.subTest(raw=raw):
                self.assertRaises(guard.Unavailable, self.check,
                    self.archive('bad.cbz', [('01.jpg', b'one'), ('ComicBookInfo.json', raw)]))

    def test_unsafe_duplicate_ambiguous_and_unsupported_inputs_held(self):
        cases = [[('01.jpg', b'one'), (name, b'other')] for name in
                 ('01.jpg', '../bad', './bad', 'a//b', 'a\\b', '/bad', 'x:y', 'comicinfo.xml')]
        cases += [[('01.jpg', b'one'), ('ComicInfo.xml', b'<bad/>')],
                  [('01.jpg', b'one'), ('ComicInfo.xml', b'<ComicInfo/>'),
                   ('ComicBookInfo.json', b'{"ComicBookInfo/1.0":{}}')],
                  [('01.jpg', b'one'), ('dir/', b'not-empty')]]
        for entries in cases:
            with self.subTest(entries=entries):
                source = self.archive('bad.cbz', entries)
                before = source.read_bytes()
                self.assertRaises(guard.Unavailable, self.check, source)
                self.assertEqual(source.read_bytes(), before)
        source = self.root / 'not-an-archive.cbz'
        source.write_bytes(b'html response')
        self.assertRaises(guard.Unavailable, self.check, source)

    def test_zip_link_and_crc_corruption_held(self):
        target = self.archive()
        with zipfile.ZipFile(target, 'a') as archive:
            link = zipfile.ZipInfo('link.jpg')
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, b'01.jpg')
        self.assertRaises(guard.Unavailable, self.check, target)
        target = self.archive('corrupt.cbz')
        raw = target.read_bytes().replace(b'one', b'bad', 1)
        target.write_bytes(raw)
        self.assertRaises(guard.Unavailable, self.check, target)

    def test_linked_source_and_linked_parent_held(self):
        source = self.archive()
        link = self.root / 'linked.cbz'
        link.symlink_to(source)
        self.assertRaises(guard.Unavailable, self.check, link)
        parent = self.root / 'linked-dir'
        parent.symlink_to(self.root, target_is_directory=True)
        self.assertRaises(guard.Unavailable, self.check, parent / source.name)

    def test_source_change_during_child_rejected(self):
        source = self.archive()
        original = guard.bounded_run
        def changed(command, **kwargs):
            raw = original(command, **kwargs)
            with source.open('ab') as stream:
                stream.write(b'changed')
            return raw
        with patch.object(guard, 'bounded_run', changed):
            self.assertRaises(guard.Unavailable, self.check, source)

    def test_metadata_and_member_bounds(self):
        source = self.archive(entries=[('01.jpg', b'one'),
            ('ComicInfo.xml', b' ' * (guard.MAX_METADATA + 1))])
        self.assertRaises(guard.Unavailable, self.check, source)
        with patch.object(guard, 'MAX_MEMBERS', 1):
            self.assertRaises(guard.Unavailable, guard.scan, self.archive(), TOOL_ROOT)

    def test_directory_type_conflicts_and_nonempty_directories_held(self):
        for mode, name, dos in ((stat.S_IFDIR, '01.jpg', 0),
                                (stat.S_IFREG, 'dir/', 0), (0, '01.jpg', 0x10)):
            with self.subTest(mode=mode, name=name, dos=dos):
                source = self.archive('modes.cbz')
                with zipfile.ZipFile(source, 'a') as archive:
                    member = zipfile.ZipInfo(name)
                    member.create_system = 3
                    member.external_attr = ((mode | 0o644) << 16) | dos
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore', UserWarning)
                        archive.writestr(member, b'not-empty')
                self.assertRaises(guard.Unavailable, self.check, source)

    def test_compressed_and_unterminated_tar_held(self):
        source = self.root / 'comic.cbt'
        with tarfile.open(source, 'w') as archive:
            info = tarfile.TarInfo('01.jpg')
            info.size = 3
            archive.addfile(info, io.BytesIO(b'one'))
        self.check(source)
        raw = source.read_bytes()
        for changed in (raw[:1024], raw + b'unverified second archive', gzip.compress(raw)):
            source.write_bytes(changed)
            self.assertRaises(guard.Unavailable, self.check, source)
        corrupted = bytearray(gzip.compress(raw))
        corrupted[-8] ^= 1
        source.write_bytes(corrupted)
        self.assertRaises(guard.Unavailable, self.check, source)

    def test_hashing_deadline_and_initial_size_limit(self):
        source = self.archive()
        self.assertRaises(guard.Unavailable, guard.file_hash, source, deadline=0)
        info = source.stat()
        with patch.object(guard, 'signature', return_value=[info.st_dev, info.st_ino, 1,
                info.st_mtime_ns, info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid,
                info.st_nlink]):
            self.assertRaises(guard.Unavailable, guard.file_hash, source)


class ProcessLimits(unittest.TestCase):
    def test_stdout_and_stderr_are_bounded(self):
        for stream in ('stdout', 'stderr'):
            with self.subTest(stream=stream):
                self.assertRaises(guard.Unavailable, guard.bounded_run,
                    [sys.executable, '-c', 'import sys;sys.' + stream + '.write("x"*4096)'],
                    max_output=1024)

    def test_timeout_and_failed_process(self):
        self.assertRaises(guard.Unavailable, guard.bounded_run,
            [sys.executable, '-c', 'import time;time.sleep(10)'], timeout=0.1)
        self.assertRaises(guard.Unavailable, guard.bounded_run,
            [sys.executable, '-c', 'raise SystemExit(1)'])


if __name__ == '__main__':
    unittest.main()

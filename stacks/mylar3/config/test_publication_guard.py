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



class RegistryTests(unittest.TestCase):
    def setUp(self):
        import workflow_store
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.store = workflow_store.Store(self.root)
        from media_writer import Writer
        self.writer = Writer(self.root / 'media-writer', create=True)
        self.state = guard.RegistryState(self.store.path, self.writer)
        self.marker = self.state.marker
        self.epoch = 'e' * 64
        self.initialization = self.state.prepare_bootstrap(dict(manifest_sha256='a'*64,
            restore_sha256='b'*64, description='Restored fixture'), epoch=self.epoch)
        self.state.initialize(self.initialization, accepted_token=self.initialization)

    def record(self, revision=0):
        owner = dict(table='annuals', issueid='123', parentcomicid='456', releasecomicid='789')
        rejected = dict(table='issues', issueid='999', parentcomicid='888', releasecomicid='888')
        row = dict(name='01.jpg', bytes=3, directory=False, sha256=hashlib.sha256(b'one').hexdigest())
        inventory = dict(version=1, members=[row], pages=['01.jpg'],
                         payload=guard.token([row], ['01.jpg']))
        return dict(version=1, epoch=self.epoch, prior_revision=revision,
            inventory=inventory, allowed=[owner], rejected=[rejected],
            evidence=dict(sha256='a' * 64, description='Explicitly reviewed fixture'),
            observed=[dict(owner=owner, source_sha256='b' * 64, signature=[1]*9,
                           catalog=dict(Location='fixture.cbz', ComicLocation='/library'))],
            intent='c' * 64, created=1)

    def seed(self, values):
        keys = []
        for value in values:
            key = guard.canonical_digest(value)
            self.store.set('publication_attestation', key, value)
            keys.append(key)
        census = dict(version=1, epoch=self.epoch, revision=len(values), keys=sorted(keys),
                      digest=guard.canonical_digest(sorted(keys)))
        self.store.set('publication_census', 'v1', census)
        self.marker.write_bytes(guard.compact(self.state.final_marker(census, self.initialization)))
        self.marker.chmod(0o600)
        return census

    def read(self):
        return guard.registry_snapshot(self.store.path, self.marker)

    def test_existing_empty_registry_and_exact_annual_identity(self):
        expected = self.seed([])
        self.assertEqual(self.read(), (expected, {}))
        expected = self.seed([self.record()])
        census, records = self.read()
        self.assertEqual(census, expected)
        self.assertEqual(next(iter(records.values()))['allowed'][0]['releasecomicid'], '789')

    def test_missing_authority_does_not_recreate_database(self):
        self.seed([])
        self.store.path.unlink()
        with self.assertRaises(guard.Unavailable):self.read()
        self.assertFalse(self.store.path.exists())
        self.marker.unlink()
        with self.assertRaises(guard.Unavailable):self.read()
        self.assertFalse(self.store.path.exists())

    def test_marker_loss_prepared_revision_mismatch_and_database_replacement(self):
        self.seed([self.record()])
        original = self.marker.read_bytes()
        for mutation in ('missing', 'prepared', 'revision', 'foreign-epoch', 'identity'):
            with self.subTest(mutation=mutation):
                value = json.loads(original)
                if mutation == 'missing':self.marker.unlink()
                else:
                    if mutation == 'prepared':value['phase'] = 'prepared'
                    if mutation == 'revision':value['census']['revision'] += 1
                    if mutation == 'foreign-epoch':value['census']['epoch'] = 'f'*64
                    if mutation == 'identity':value['database_identity'][1] += 1
                    self.marker.write_bytes(guard.compact(value))
                with self.assertRaises(guard.Unavailable):self.read()
                self.marker.write_bytes(original)
                self.marker.chmod(0o600)
        old = self.root / 'old.sqlite'
        self.store.path.rename(old)
        self.store.path.write_bytes(old.read_bytes())
        self.store.path.chmod(0o600)
        with self.assertRaises(guard.Unavailable):self.read()

    def test_lost_changed_unknown_and_corrupt_records_hold(self):
        self.seed([self.record()])
        key = guard.canonical_digest(self.record())
        with self.store.connection() as db:
            db.execute("DELETE FROM records WHERE kind='publication_attestation'")
        with self.assertRaises(guard.Unavailable):self.read()
        self.seed([self.record()])
        value = self.record();value['evidence']['description'] = 'changed'
        self.store.set('publication_attestation', key, value)
        with self.assertRaises(guard.Unavailable):self.read()
        self.store.set('publication_attestation', key, self.record())
        self.store.set('publication_unknown', 'x', {})
        with self.assertRaises(guard.Unavailable):self.read()
        self.store.delete('publication_unknown', 'x')
        with self.store.connection() as db:
            db.execute("UPDATE records SET value='{' WHERE kind='publication_census'")
        with self.assertRaises(guard.Unavailable):self.read()

    def test_complete_coverage_ignores_recent_history_and_event_only_changes(self):
        self.seed([self.record()])
        for index in range(1005):self.store.set('unrelated', str(index), {})
        self.store.event('library', 'fixture observation')
        self.assertEqual(len(self.read()[1]), 1)
        with patch.object(guard, 'REGISTRY_LIMIT', 0):
            with self.assertRaises(guard.Unavailable):self.read()

    def test_contradictory_history_revision_loss_and_foreign_epoch(self):
        first = self.record();second = self.record(1)
        second['allowed'], second['rejected'] = second['rejected'], second['allowed']
        second['observed'][0]['owner'] = second['allowed'][0]
        self.seed([first, second])
        with self.assertRaises(guard.Unavailable):self.read()
        self.store.delete('publication_attestation', guard.canonical_digest(second))
        for mutation in ('gap', 'epoch'):
            second = self.record(1)
            if mutation == 'gap':second['prior_revision'] = 3
            else:second['epoch'] = 'f'*64
            key = guard.canonical_digest(second)
            self.seed([first, second])
            with self.assertRaises(guard.Unavailable):self.read()
            self.store.delete('publication_attestation', key)

    def test_blob_value_corrupt_database_and_marker_boolean_hold(self):
        import sqlite3
        self.seed([])
        with self.store.connection() as db:
            db.execute("UPDATE records SET value=? WHERE kind='publication_census'",
                       (sqlite3.Binary(b'{}'),))
        with self.assertRaises(guard.Unavailable):self.read()
        self.seed([])
        value = json.loads(self.marker.read_bytes());value['version'] = True
        self.marker.write_bytes(guard.compact(value))
        with self.assertRaises(guard.Unavailable):self.read()
        self.seed([])
        self.store.path.write_bytes(b'corrupt database')
        with self.assertRaises(guard.Unavailable):self.read()

    def test_blob_namespace_and_combined_owner_bound(self):
        import sqlite3
        self.seed([])
        with self.store.connection() as db:
            db.execute('INSERT INTO records VALUES (?,?,?,?)',
                (sqlite3.Binary(b'publication_attestation'), 'hidden', '{}', 0))
        with self.assertRaises(guard.Unavailable):self.read()
        value = self.record()
        value['rejected'] = [dict(table='issues', issueid=str(n), parentcomicid='1',
                                  releasecomicid='1') for n in range(1, 9)]
        with self.assertRaises(guard.Unavailable):guard.attestation(value)

    def test_wal_and_sidecar_paths_hold_without_creating_shm(self):
        import sqlite3
        self.seed([])
        original = self.marker.read_bytes()
        for suffix in ('-wal', '-shm', '-journal'):
            path = Path(str(self.store.path) + suffix)
            path.symlink_to(self.root / 'absent')
            with self.assertRaises(guard.Unavailable):self.read()
            self.assertTrue(path.is_symlink())
            path.unlink()
        db = sqlite3.connect(self.store.path)
        try:
            self.assertEqual(db.execute('PRAGMA journal_mode=WAL').fetchone(), ('wal',))
            db.execute("INSERT INTO records VALUES ('other','x','{}',0)");db.commit()
            clone = self.root / 'clone.sqlite'
            clone.write_bytes(self.store.path.read_bytes());clone.chmod(0o600)
            Path(str(clone)+'-wal').write_bytes(Path(str(self.store.path)+'-wal').read_bytes())
            value = json.loads(original)
            value['database_identity'] = guard.signature(clone.stat())[:2]
            self.marker.write_bytes(guard.compact(value))
            with self.assertRaises(guard.Unavailable):guard.registry_snapshot(clone, self.marker)
            self.assertFalse(Path(str(clone)+'-shm').exists())
        finally:
            db.close()

    def test_owner_strict_ascii_and_cross_table_shadow(self):
        for owner in (dict(table='issues', issueid='0', parentcomicid='1', releasecomicid='1'),
                      dict(table='issues', issueid='01', parentcomicid='1', releasecomicid='1'),
                      dict(table='issues', issueid='１２３', parentcomicid='1', releasecomicid='1'),
                      dict(table='issues', issueid='1', parentcomicid='2', releasecomicid='3')):
            with self.assertRaises(guard.Unavailable):guard.exact_owner(owner)
        value = self.record()
        value['rejected'] = [dict(value['allowed'][0])]
        with self.assertRaises(guard.Unavailable):guard.attestation(value)
        value['rejected'][0]['table'] = 'issues'
        value['rejected'][0]['releasecomicid'] = '456'
        guard.attestation(value)

    def test_private_marker_hardlink_symlink_and_duplicate_json_refusal(self):
        self.seed([])
        self.marker.chmod(0o644)
        with self.assertRaises(guard.Unavailable):self.read()
        self.marker.chmod(0o600)
        link = self.root / 'link';os.link(self.marker, link)
        with self.assertRaises(guard.Unavailable):self.read()
        link.unlink()
        original = self.marker.read_bytes()
        self.marker.unlink();self.marker.symlink_to(self.store.path)
        with self.assertRaises(guard.Unavailable):self.read()
        self.marker.unlink()
        self.marker.write_bytes(b'{"version":1,"version":1}')
        self.marker.chmod(0o600)
        with self.assertRaises(guard.Unavailable):self.read()
        self.marker.write_bytes(original)
        self.assertEqual(self.read()[0]['revision'], 0)



class JournalRecoveryTests(unittest.TestCase):
    def setUp(self):
        from media_writer import Writer
        from workflow_store import Store
        import subprocess
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.writer = Writer(self.root / 'writer', create=True)
        # Force real dirty-page spill, not only a cold journal left in cache.
        for index in range(12):self.store.set('pack', str(index), {'payload': 'x'*8192})
        self.state = guard.RegistryState(self.store.path, self.writer)
        self.token = self.state.prepare_bootstrap(dict(manifest_sha256='a'*64,
            restore_sha256='b'*64, description='Independent fixture restore'), epoch='e'*64)
        script = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[3])
import publication_guard as guard
from media_writer import Writer
state=guard.RegistryState(Path(sys.argv[1])/'workflow.sqlite',Writer(Path(sys.argv[1])/'writer'))
original=state._commit_census
def commit(db,*args):
    db.execute('PRAGMA cache_size=1')
    return original(db,*args)
state._commit_census=commit
def interrupt(stage):
    if stage=='sqlite-pending':os._exit(73)
state.initialize(sys.argv[2],accepted_token=sys.argv[2],boundary=interrupt)
'''
        result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root),
            self.token, str(Path(guard.__file__).parent)], timeout=20, capture_output=True)
        self.assertEqual(result.returncode, 73, result.stderr.decode())
        self.journal = Path(str(self.store.path)+'-journal')
        self.assertEqual(self.journal.read_bytes()[:8], bytes.fromhex('d9d505f920a163d7'))
        self.before = self.pair()

    def pair(self):
        return self.store.path.read_bytes(), self.journal.read_bytes(), self.state.marker.read_bytes()

    def recovery(self):
        return guard.JournalRecovery(self.store.path, self.writer)

    def test_verified_isolated_restore_and_explicit_acceptance(self):
        recovery = self.recovery()
        token = recovery.prepare(self.token)
        self.assertEqual(self.pair(), self.before)
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token='f'*64)
        self.assertEqual(self.pair(), self.before)
        recovery.commit(token, accepted_token=token)
        self.assertFalse(self.journal.exists())
        self.assertFalse(recovery.marker.exists())
        # The independent capture is retained and bootstrap is still held.
        self.assertTrue(list(self.writer.root.glob('publication-recovery-*/receipt.json')))
        restarted = guard.RegistryState(self.store.path, self.writer)
        with self.assertRaises(guard.Unavailable):restarted.snapshot()
        restarted.recover_bootstrap(self.token)
        self.assertEqual(restarted.snapshot()[0]['revision'], 0)
        for index in range(12):self.assertEqual(self.store.get('pack',str(index)), {'payload':'x'*8192})

    def test_changed_original_or_capture_refuses_without_recovery(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        original = self.journal.read_bytes()
        with self.journal.open('ab') as stream:stream.write(b'foreign')
        changed = self.pair()
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), changed)
        self.journal.write_bytes(original)
        # Even restoring the bytes does not restore the reviewed file signature.
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), self.before)

    def test_corrupt_journal_and_missing_marker_preserve_originals(self):
        with self.journal.open('r+b') as stream:stream.write(b'INVALID!')
        changed = self.pair()
        with self.assertRaises(guard.Unavailable):self.recovery().prepare(self.token)
        self.assertEqual(self.pair(), changed)
        self.state.marker.unlink()
        with self.assertRaises(guard.Unavailable):self.recovery().prepare(self.token)

    def test_backup_tampering_blocks_application(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        capture = next(self.writer.root.glob('publication-recovery-*/original.sqlite'))
        with capture.open('ab') as stream:stream.write(b'tamper')
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), self.before)

    def test_restart_after_each_real_recovery_process_exit(self):
        import subprocess
        script = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[4])
import publication_guard as guard
from media_writer import Writer
root=Path(sys.argv[1])
recovery=guard.JournalRecovery(root/'workflow.sqlite',Writer(root/'writer'))
def interrupt(stage):
    if stage==sys.argv[2]:os._exit(74)
if sys.argv[2] in ('capture-copied','restore-verified','recovery-plan'):
    recovery.prepare(sys.argv[3],boundary=interrupt)
else:
    recovery.commit(sys.argv[3],accepted_token=sys.argv[3],boundary=interrupt)
'''
        # Copy the captured hot state while retaining the original bound inode
        # by restoring its contents between cases, before reviewing each plan.
        for stage in ('capture-copied', 'restore-verified', 'recovery-plan',
                      'recovery-accepted', 'original-recovered', 'completion-receipt', 'recovery-cleared'):
            with self.subTest(stage=stage):
                recovery = self.recovery()
                token = self.token if stage in ('capture-copied','restore-verified','recovery-plan') else recovery.prepare(self.token)
                result = subprocess.run([sys.executable, '-B', '-c', script, str(self.root),
                    stage, token, str(Path(guard.__file__).parent)], timeout=20, capture_output=True)
                self.assertEqual(result.returncode, 74, result.stderr.decode())
                if recovery.marker.exists():
                    current = guard.private_json(recovery.marker)
                    token = guard.canonical_digest(current['plan'])
                    recovery.commit(token, accepted_token=token)
                elif stage != 'recovery-cleared':
                    token = recovery.prepare(self.token)
                    recovery.commit(token, accepted_token=token)
                self.assertFalse(recovery.marker.exists())
                self.assertFalse(self.journal.exists())
                # Keep exact original identities for the next independently
                # reviewed fixture. Retained captures from prior cases remain.
                self.store.path.write_bytes(self.before[0]);self.store.path.chmod(0o600)
                self.journal.write_bytes(self.before[1]);self.journal.chmod(0o600)
                self.state.marker.write_bytes(self.before[2]);self.state.marker.chmod(0o600)

    def test_changed_marker_fence_and_malformed_receipt_hold(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        marker = self.state.marker.read_bytes()
        self.state.marker.write_bytes(marker + b' ')
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertTrue(self.journal.exists())
        self.state.marker.write_bytes(marker)
        recovery.marker.write_bytes(b'[]');recovery.marker.chmod(0o600)
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertTrue(self.journal.exists())

    def test_pending_fences_retained_and_changed_fence_blocks(self):
        # An existing fence cannot be invented after bootstrap preparation.
        self.writer.create_file(self.writer.pending)
        original = self.pair()
        with self.assertRaises(guard.Unavailable):self.recovery().prepare(self.token)
        self.assertEqual(self.pair(), original)
        self.assertTrue(self.writer.pending.exists())

    def test_accepted_recovery_holds_ordinary_bootstrap_before_replay(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        def interrupt(stage):
            if stage == 'original-recovered':raise RuntimeError('Interrupted after rollback')
        with self.assertRaises(RuntimeError):recovery.commit(token, accepted_token=token, boundary=interrupt)
        restarted = guard.RegistryState(self.store.path, self.writer)
        with self.assertRaises(guard.Unavailable):restarted.recover_bootstrap(self.token)
        with self.assertRaises(guard.Unavailable):restarted.snapshot()
        recovery.commit(token, accepted_token=token)
        restarted.recover_bootstrap(self.token)
        self.assertEqual(restarted.snapshot()[0]['revision'], 0)

    def test_real_exit_during_rollback_requires_new_verified_plan(self):
        import subprocess
        recovery = self.recovery();token = recovery.prepare(self.token)
        script = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[3])
import publication_guard as guard
from media_writer import Writer
root=Path(sys.argv[1]);recovery=guard.JournalRecovery(root/'workflow.sqlite',Writer(root/'writer'))
def interrupt(stage):
    if stage=='rollback-pending':os._exit(75)
recovery.commit(sys.argv[2],accepted_token=sys.argv[2],boundary=interrupt)
'''
        result = subprocess.run([sys.executable,'-B','-c',script,str(self.root),token,
            str(Path(guard.__file__).parent)], timeout=20, capture_output=True)
        self.assertEqual(result.returncode, 75, result.stderr.decode())
        self.assertTrue(self.journal.exists())
        interrupted = self.pair()
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), interrupted)
        replacement = recovery.prepare(self.token, parent_token=token)
        self.assertNotEqual(replacement, token)
        self.assertEqual(self.pair(), interrupted)
        with self.assertRaises(guard.Unavailable):recovery.commit(replacement, accepted_token=token)
        recovery.commit(replacement, accepted_token=replacement)
        self.assertFalse(self.journal.exists())
        self.assertEqual(len(list(self.writer.root.glob('publication-recovery-*/receipt.json'))), 2)
        guard.RegistryState(self.store.path,self.writer).recover_bootstrap(self.token)
        self.assertEqual(self.state.snapshot()[0]['revision'], 0)

    def test_tampered_retained_receipt_blocks_before_original_sqlite_open(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        path = next(self.writer.root.glob('publication-recovery-*/receipt.json'))
        path.write_text('{}');path.chmod(0o600)
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), self.before)

    def test_replacement_database_and_linked_capture_hold(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        old = self.root/'old.sqlite';self.store.path.rename(old)
        self.store.path.write_bytes(old.read_bytes());self.store.path.chmod(0o600)
        changed = self.pair()
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)
        self.assertEqual(self.pair(), changed)
        capture = next(self.writer.root.glob('publication-recovery-*/original.sqlite'))
        os.link(capture,self.root/'linked.sqlite')
        with self.assertRaises(guard.Unavailable):recovery.commit(token, accepted_token=token)

    def test_contradictory_zero_header_journal_preserves_originals(self):
        # The bootstrap has not committed its census. SQLite may legitimately
        # leave a zero-header journal before dirty pages have been flushed.
        with self.journal.open('r+b') as stream:stream.write(b'\0'*8)
        # A zero-header journal with dirty database pages is contradictory and
        # must hold on the independent copy, never mutate the originals.
        original = self.pair()
        with self.assertRaises(guard.Unavailable):self.recovery().prepare(self.token)
        self.assertEqual(self.pair(), original)

    def test_valid_cold_journal_has_independent_restore_and_recovery(self):
        import subprocess
        from media_writer import Writer
        from workflow_store import Store
        root = self.root/'cold';root.mkdir()
        store = Store(root);writer = Writer(root/'writer',create=True)
        state = guard.RegistryState(store.path,writer)
        token = state.prepare_bootstrap(dict(manifest_sha256='a'*64,restore_sha256='b'*64,
            description='Independent cold-journal fixture restore'),epoch='e'*64)
        script = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[3])
import publication_guard as guard
from media_writer import Writer
root=Path(sys.argv[1]);state=guard.RegistryState(root/'workflow.sqlite',Writer(root/'writer'))
def interrupt(stage):
    if stage=='sqlite-pending':os._exit(76)
state.initialize(sys.argv[2],accepted_token=sys.argv[2],boundary=interrupt)
'''
        result = subprocess.run([sys.executable,'-B','-c',script,str(root),token,
            str(Path(guard.__file__).parent)],timeout=20,capture_output=True)
        self.assertEqual(result.returncode,76,result.stderr.decode())
        journal = Path(str(store.path)+'-journal')
        self.assertEqual(journal.read_bytes()[:8],b'\0'*8)
        before = store.path.read_bytes(),journal.read_bytes()
        recovery = guard.JournalRecovery(store.path,writer)
        reviewed = recovery.prepare(token)
        self.assertEqual((store.path.read_bytes(),journal.read_bytes()),before)
        recovery.commit(reviewed,accepted_token=reviewed)
        self.assertFalse(journal.exists())
        state.recover_bootstrap(token)
        self.assertEqual(state.snapshot()[0]['revision'],0)

    def test_forged_restoration_claims_never_open_original_sqlite(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        original = guard.private_json(recovery.marker)
        retained = self.writer.root/original['plan']['directory']/'receipt.json'
        for change in ({'records':'1'}, {'records':True}, {'events':5001},
                       {'digest':'f'*64}, {'sha256':'invalid'}):
            with self.subTest(change=change):
                forged = json.loads(json.dumps(original))
                forged['plan']['restored'].update(change)
                raw = guard.compact(forged)
                recovery.marker.write_bytes(raw);recovery.marker.chmod(0o600)
                retained.write_bytes(raw);retained.chmod(0o600)
                accepted = guard.canonical_digest(forged['plan'])
                with self.assertRaises(guard.Unavailable):recovery.commit(accepted,accepted_token=accepted)
                self.assertEqual(self.pair(),self.before)
                self.assertEqual(guard.private_json(recovery.marker)['outcome'],'verified')
        forged = json.loads(json.dumps(original));del forged['plan']['restored']['records']
        raw = guard.compact(forged);recovery.marker.write_bytes(raw);retained.write_bytes(raw)
        accepted = guard.canonical_digest(forged['plan'])
        with self.assertRaises(guard.Unavailable):recovery.commit(accepted,accepted_token=accepted)
        self.assertEqual(self.pair(),self.before)

    def test_malformed_capture_and_oversized_history_hold_before_modification(self):
        recovery = self.recovery();token = recovery.prepare(self.token)
        original = guard.private_json(recovery.marker)
        retained = self.writer.root/original['plan']['directory']/'receipt.json'
        for name, change in (('database', {'signature':[1,2]}),
                             ('journal', {'sha256':False}),
                             ('marker', {'signature':[0]*9})):
            with self.subTest(name=name):
                forged = json.loads(json.dumps(original));forged['plan']['capture'][name].update(change)
                raw = guard.compact(forged);recovery.marker.write_bytes(raw);retained.write_bytes(raw)
                accepted = guard.canonical_digest(forged['plan'])
                with self.assertRaises(guard.Unavailable):recovery.commit(accepted,accepted_token=accepted)
                self.assertEqual(self.pair(),self.before)
        recovery.marker.unlink()
        for index in range(guard.INTENT_LIMIT):
            (self.writer.root/('publication-recovery-test-'+str(index))).mkdir()
        with self.assertRaises(guard.Unavailable):recovery.prepare(self.token)
        self.assertEqual(self.pair(),self.before)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        from media_writer import Writer
        from workflow_store import Store
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)
        self.writer = Writer(self.root / 'media-writer', create=True)
        self.state = guard.RegistryState(self.store.path, self.writer)
        self.backup = dict(manifest_sha256='a'*64, restore_sha256='b'*64,
                           description='Independently restored isolated fixture')

    def prepare(self):
        return self.state.prepare_bootstrap(self.backup, epoch='e'*64)

    def test_explicit_acceptance_and_restart(self):
        token = self.prepare()
        self.assertFalse(self.state.marker.exists())
        with self.assertRaises(guard.Unavailable):self.state.snapshot()
        with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token='f'*64)
        census = self.state.initialize(token, accepted_token=token)
        self.assertEqual(census['revision'], 0)
        self.assertEqual(census['epoch'], 'e'*64)
        restarted = guard.RegistryState(self.store.path, self.writer)
        self.assertEqual(restarted.snapshot(), (census, {}))
        self.assertEqual(restarted.initialize(token, accepted_token=token), census)
        with self.assertRaises(guard.Unavailable):self.prepare()

    def test_stale_protected_facts_and_event_only_drift(self):
        token = self.prepare()
        self.store.set('pack', 'changed', {'phase': 'downloaded'})
        with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token=token)
        self.store.delete('pack', 'changed')
        self.store.event('library', 'Observed', key='volatile')
        self.store.set('meta', 'library_seen', ['123'])
        self.assertEqual(self.state.initialize(token, accepted_token=token)['revision'], 0)

    def test_crashes_at_every_durability_boundary(self):
        stages = ('intent-accepted', 'prepared-file', 'prepared-marker',
                  'sqlite-pending', 'sqlite-committed', 'final-file', 'final-marker')
        for stage in stages:
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                from media_writer import Writer
                from workflow_store import Store
                store = Store(directory);writer = Writer(Path(directory)/'writer', create=True)
                state = guard.RegistryState(store.path, writer)
                token = state.prepare_bootstrap(self.backup, epoch='e'*64)
                def interrupt(point):
                    if point == stage:raise RuntimeError('Injected interruption')
                with self.assertRaises(RuntimeError):state.initialize(token, accepted_token=token, boundary=interrupt)
                restarted = guard.RegistryState(store.path, writer)
                if stage in ('intent-accepted', 'prepared-file'):
                    with self.assertRaises(guard.Unavailable):restarted.snapshot()
                    restarted.initialize(token, accepted_token=token)
                elif stage == 'final-marker':restarted.snapshot()
                else:
                    with self.assertRaises(guard.Unavailable):restarted.snapshot()
                    restarted.recover_bootstrap(token)
                self.assertEqual(restarted.snapshot()[0]['revision'], 0)

    def test_abort_keeps_receipt_and_uninitialized_state(self):
        token = self.prepare()
        def interrupt(stage):
            if stage == 'prepared-marker':raise RuntimeError('Injected interruption')
        with self.assertRaises(RuntimeError):self.state.initialize(token, accepted_token=token, boundary=interrupt)
        self.state.recover_bootstrap(token, abort=True)
        self.assertFalse(self.state.marker.exists())
        self.assertEqual(self.store.get('publication_intent', token)['outcome'], 'aborted')
        with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token=token)
        with self.assertRaises(guard.Unavailable):self.state.snapshot()

    def test_missing_marker_or_census_never_rebootstraps(self):
        token = self.prepare();self.state.initialize(token, accepted_token=token)
        self.state.marker.unlink()
        with self.assertRaises(guard.Unavailable):self.prepare()
        with self.assertRaises(guard.Unavailable):self.state.recover_bootstrap(token)
        self.store.delete('publication_census', 'v1')
        with self.assertRaises(guard.Unavailable):self.prepare()

    def test_review_receipt_and_current_writer_identity_required(self):
        for backup in ({}, dict(self.backup, restore_sha256='invalid')):
            with self.assertRaises(guard.Unavailable):self.state.prepare_bootstrap(backup, epoch='e'*64)
        token = self.prepare()
        original = self.writer.lock.read_bytes();self.writer.lock.rename(self.root/'old.lock')
        self.writer.lock.write_bytes(original);self.writer.lock.chmod(0o600)
        with self.assertRaises((guard.Unavailable, ValueError)):
            self.state.initialize(token, accepted_token=token)


    def test_real_process_death_at_durable_boundaries(self):
        import subprocess
        script = '''import os,sys
from pathlib import Path
sys.path.insert(0,sys.argv[4])
import publication_guard as guard
from media_writer import Writer
state=guard.RegistryState(Path(sys.argv[1])/'workflow.sqlite',Writer(Path(sys.argv[1])/'writer'))
def interrupt(stage):
    if stage==sys.argv[2]:os._exit(73)
state.initialize(sys.argv[3],accepted_token=sys.argv[3],boundary=interrupt)
'''
        from media_writer import Writer
        from workflow_store import Store
        for stage in ('intent-accepted', 'prepared-file', 'prepared-marker',
                      'sqlite-pending', 'sqlite-committed', 'final-file', 'final-marker'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                store = Store(directory);writer = Writer(Path(directory)/'writer', create=True)
                state = guard.RegistryState(store.path, writer)
                token = state.prepare_bootstrap(self.backup, epoch='e'*64)
                result = subprocess.run([sys.executable, '-B', '-c', script, directory,
                    stage, token, str(Path(guard.__file__).parent)], timeout=20, capture_output=True)
                self.assertEqual(result.returncode, 73, result.stderr.decode())
                if stage == 'sqlite-pending':
                    journal = Path(str(store.path)+'-journal')
                    self.assertTrue(journal.exists())
                    before = store.path.read_bytes(), journal.read_bytes()
                    with self.assertRaises(guard.Unavailable):guard.RegistryState(store.path, writer)
                    with self.assertRaises(guard.Unavailable):guard.registry_snapshot(store.path, state.marker)
                    self.assertEqual((store.path.read_bytes(), journal.read_bytes()), before)
                    continue  # Explicit backup/journal recovery seam remains pending.
                restarted = guard.RegistryState(store.path, writer)
                if stage in ('intent-accepted', 'prepared-file'):
                    restarted.initialize(token, accepted_token=token)
                elif stage == 'final-marker':restarted.snapshot()
                else:restarted.recover_bootstrap(token)
                self.assertEqual(restarted.snapshot()[0]['revision'], 0)

    def test_interrupted_abort_and_new_review(self):
        token = self.prepare()
        def interrupt(stage):
            if stage in ('prepared-marker', 'abort-committed'):raise RuntimeError('Interrupted')
        with self.assertRaises(RuntimeError):self.state.initialize(token, accepted_token=token, boundary=interrupt)
        with self.assertRaises(RuntimeError):self.state.recover_bootstrap(token, abort=True, boundary=interrupt)
        with self.assertRaises(guard.Unavailable):self.state.snapshot()
        self.state.recover_bootstrap(token)
        with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token=token)
        new = self.state.prepare_bootstrap(self.backup, epoch='f'*64)
        self.assertNotEqual(token, new)
        self.assertEqual(self.state.initialize(new, accepted_token=new)['epoch'], 'f'*64)

    def test_foreign_writer_database_marker_and_malformed_marker_hold(self):
        token = self.prepare()
        for raw in (b'[]', b'null', b'{"phase":"prepared"}'):
            self.state.marker.write_bytes(raw);self.state.marker.chmod(0o600)
            with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token=token)
            self.state.marker.unlink()
        old = self.root/'old.sqlite';self.store.path.rename(old)
        self.store.path.write_bytes(old.read_bytes());self.store.path.chmod(0o600)
        replacement = guard.RegistryState(self.store.path, self.writer)
        with self.assertRaises(guard.Unavailable):replacement.initialize(token, accepted_token=token)

    def test_existing_fences_are_preserved_and_bound_without_media_replay(self):
        with self.writer.hold(allow_pending=True):self.writer.mark_pending()
        before = self.writer.pending.read_bytes(), guard.signature(self.writer.pending.stat())
        token = self.prepare()
        self.state.initialize(token, accepted_token=token)
        self.assertEqual((self.writer.pending.read_bytes(), guard.signature(self.writer.pending.stat())), before)
        self.assertEqual(self.state.snapshot()[0]['revision'], 0)

    def test_schema_and_committed_initialization_witness_loss_hold(self):
        token = self.prepare();self.state.initialize(token, accepted_token=token)
        with self.store.connection() as db:db.execute('DROP INDEX events_issue')
        with self.assertRaises(guard.Unavailable):self.state.snapshot()
        with self.store.connection() as db:db.execute('CREATE INDEX events_issue ON events(issueid,id)')
        self.store.delete('publication_intent', token)
        with self.assertRaises(guard.Unavailable):self.state.snapshot()
        with self.assertRaises(guard.Unavailable):self.prepare()


    def test_marker_loss_before_final_does_not_recreate_authority(self):
        token = self.prepare()
        def interrupt(stage):
            if stage == 'sqlite-committed':self.state.marker.unlink()
        with self.assertRaises(guard.Unavailable):
            self.state.initialize(token, accepted_token=token, boundary=interrupt)
        self.assertFalse(self.state.marker.exists())
        with self.assertRaises(guard.Unavailable):self.state.snapshot()
        with self.assertRaises(guard.Unavailable):self.state.recover_bootstrap(token)

    def test_abort_cannot_clear_mixed_or_new_committed_authority(self):
        token = self.prepare()
        def interrupt(stage):
            if stage == 'sqlite-committed':raise RuntimeError('Interrupted')
        with self.assertRaises(RuntimeError):self.state.initialize(token, accepted_token=token, boundary=interrupt)
        before = self.state.marker.read_bytes()
        with self.assertRaises(guard.Unavailable):self.state.recover_bootstrap(token, abort=True)
        self.assertEqual(self.state.marker.read_bytes(), before)
        self.state.recover_bootstrap(token)
        self.assertEqual(self.state.snapshot()[0]['revision'], 0)

    def test_event_writer_finishes_without_lock_inversion(self):
        import threading
        token = self.prepare()
        held, release, finished = threading.Event(), threading.Event(), threading.Event()
        errors = []
        def event_writer():
            try:
                with self.store.connection() as db:
                    held.set()
                    if not release.wait(3):raise RuntimeError('Fixture timeout')
                    db.execute("INSERT INTO events(at,stage,outcome) VALUES (0,'library','Observed')")
            except BaseException as error:errors.append(error)
        def initializer():
            try:self.state.initialize(token, accepted_token=token)
            except BaseException as error:errors.append(error)
            finally:finished.set()
        first = threading.Thread(target=event_writer);second = threading.Thread(target=initializer)
        first.start();self.assertTrue(held.wait(1));second.start()
        try:self.assertFalse(finished.wait(.05))
        finally:release.set();first.join(3);second.join(3)
        self.assertFalse(first.is_alive());self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.state.snapshot()[0]['revision'], 0)

    def test_oversized_receipt_and_unknown_authority_hold(self):
        token = self.prepare()
        with self.store.connection() as db:
            db.execute("UPDATE records SET value=? WHERE kind='publication_intent' AND key=?",
                       (' '*65537, token))
        with self.assertRaises(guard.Unavailable):self.state.initialize(token, accepted_token=token)
        self.assertFalse(self.state.marker.exists())
        self.store.delete('publication_intent', token)
        self.store.set('publication_unknown', 'foreign', {})
        with self.assertRaises(guard.Unavailable):self.prepare()

if __name__ == '__main__':
    unittest.main()

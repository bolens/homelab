"""Real archive cleanup, preservation, and interrupted recovery checks."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from maintenance import Maintenance, CorruptArchive
from normalize import digest, identity
from test_normalize import PNG, TOOL, Reader


class ConversionIdentityTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'; self.state.mkdir()
        self.library = self.root / 'library'; self.library.mkdir()
        self.database = self.root / 'mylar.db'
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executescript('CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT);'
                             'CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);')
            db.execute('INSERT INTO comics VALUES (?,?)', ('20', str(self.library)))
            db.execute('INSERT INTO issues VALUES (?,?,?)', ('10', '20', 'Comic.cbz'))
        self.m = Maintenance.__new__(Maintenance)
        self.m.worker = SimpleNamespace(state=self.state, config={'mylar': {'config_dir': str(self.root)}})

    def report(self, source, destination=None):
        job = self.state / 'jobs' / 'fixture'; job.mkdir(parents=True, exist_ok=True)
        (job/'receipt.json').write_text(json.dumps({'source':str(source), 'destination':str(destination) if destination else None, 'phase':'done'}))
        return self.m.conversion_report()[0]

    def test_exact_destination_or_source_retains_issue_identity_without_archive_scan(self):
        row = self.report(self.library/'Comic.cb7', self.library/'Comic.cbz')
        self.assertEqual((row['issueid'], row['comicid']), ('10', '20'))
        self.assertNotIn(str(self.root), json.dumps(row))
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('UPDATE issues SET Location=?', (str(self.library/'Comic.cb7'),))
        row = self.report(self.library/'Comic.cb7', self.library/'Comic.cbz')
        self.assertEqual(row['issueid'], '10')
        self.assertFalse((self.library/'Comic.cb7').exists())

    def test_same_filename_elsewhere_and_conflicting_path_identities_stay_global(self):
        self.assertNotIn('issueid', self.report(self.root/'other'/'Comic.cbz'))
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('INSERT INTO issues VALUES (?,?,?)', ('11', '20', 'Comic.cb7'))
        self.assertNotIn('issueid', self.report(self.library/'Comic.cb7', self.library/'Comic.cbz'))
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('INSERT INTO issues VALUES (?,?,?)', ('12', '20', 'Comic.cbz'))
        self.assertNotIn('issueid', self.report(self.library/'Comic.cbz'))

    def test_failed_conversion_path_can_be_attributed_without_receipt(self):
        (self.state/'status.json').write_text(json.dumps({'errors':[{'path':str(self.library/'Comic.cbz')}]}))
        row = self.m.conversion_report()[0]
        self.assertEqual((row['issueid'], row['comicid'], row['phase']), ('10', '20', 'failed'))

    def test_missing_database_or_schema_does_not_suppress_conversion(self):
        self.database.unlink()
        row = self.report(self.library/'Comic.cb7', self.library/'Comic.cbz')
        self.assertNotIn('issueid', row)
        self.assertEqual(row['original_format'], 'CB7')
        self.assertFalse(self.database.exists())
        self.database.write_bytes(b'not sqlite')
        self.assertEqual(self.report(self.library/'Comic.cb7')['phase'], 'done')


@unittest.skipUnless(TOOL, 'Set ARCHIVING_UTILS_BIN')
class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.downloads, self.library, self.state = [root / n for n in ('downloads', 'library', 'state')]
        for path in (self.downloads, self.library, self.state):
            path.mkdir()
        self.reader = Reader(self.library)
        self.worker = SimpleNamespace(state=self.state, roots=[self.library], tool=TOOL, reader=self.reader,
                                      config={'maintenance': {'completed': str(self.downloads), 'settle_seconds': 0}})
        self.m = Maintenance(self.worker)
        self.m.idle = Mock(return_value=True)
        self.m.import_match = Mock(return_value=None)
        self.m.issue_match = Mock(return_value={'issueid': '1', 'comicid': '2'})
        self.m.mylar = Mock(return_value={'mode': 'retry'})

    def test_conversion_report_contains_formats_without_private_paths(self):
        job=self.state/'jobs'/'one';job.mkdir(parents=True)
        (job/'receipt.json').write_text(json.dumps({'source':'/private/Comic.cbt.tar.zst','phase':'done'}))
        rows=self.m.conversion_report()
        self.assertEqual(rows,[{'name':'Comic.cbt.tar.zst','original_format':'CBT.TAR.ZST','original_container':'Unknown','phase':'done'}])
        self.assertNotIn('/private',json.dumps(rows))

    def comic(self, root, extra=False, page=PNG):
        path = root / 'Comic 001.cbz'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('001.png', page)
            if extra:
                archive.writestr('ComicInfo.xml', '<ComicInfo/>')
        return path

    def receipts(self):
        return [json.loads(p.read_text()) for p in self.m.receipts.glob('*.json')]

    def test_exact_pages_with_added_library_metadata_cleanup(self):
        source = self.comic(self.downloads)
        target = self.comic(self.library, extra=True)
        checksum = digest(target)
        self.assertTrue(self.m.remove_duplicate(source, target))
        self.assertFalse(source.exists())
        self.assertEqual(digest(target), checksum)
        self.assertEqual(self.receipts()[0]['phase'], 'removed')

    def test_different_pages_and_source_extras_retained(self):
        source = self.comic(self.downloads, extra=True)
        target = self.comic(self.library)
        self.assertFalse(self.m.remove_duplicate(source, target))
        self.comic(self.library, extra=True, page=PNG + b'different')
        self.assertFalse(self.m.remove_duplicate(source, target))
        self.assertTrue(source.exists())

    def test_busy_worker_and_mutation_block_deletion(self):
        source, target = self.comic(self.downloads), self.comic(self.library)
        self.m.idle.return_value = False
        self.assertFalse(self.m.remove_duplicate(source, target))
        def change():
            source.write_bytes(b'changed')
            return True
        self.m.idle.side_effect = change
        with self.assertRaises(RuntimeError):
            self.m.remove_duplicate(source, target)
        self.assertTrue(source.exists())

    def test_parent_symlink_rejected(self):
        source = self.comic(self.downloads)
        self.comic(self.library)
        link = self.library / 'linked'
        link.symlink_to(self.downloads, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            self.m.remove_duplicate(source, link / source.name)
        self.assertTrue(source.exists())

    def test_quarantine_preserves_copy_and_never_retries_same_delivery_twice(self):
        source = self.comic(self.downloads)
        source.write_bytes(b'corrupt')
        checksum = digest(source)
        self.m.quarantine(source, identity(source))
        row = self.receipts()[0]
        self.assertFalse(source.exists())
        self.assertEqual(digest(Path(row['destination'])), checksum)
        source.write_bytes(b'corrupt')
        self.m.quarantine(source, identity(source))
        self.m.mylar.assert_called_once()
        self.assertFalse(source.exists())

    def test_changed_archive_is_never_quarantined(self):
        source = self.comic(self.downloads)
        previous = identity(source)
        source.write_bytes(b'new download')
        with self.assertRaises(RuntimeError):
            self.m.quarantine(source, previous)
        self.assertTrue(source.exists())

    def test_ambiguous_retry_and_stop_are_not_repeated(self):
        source = self.comic(self.downloads)
        self.m.mylar.side_effect = TimeoutError
        with self.assertRaises(TimeoutError):
            self.m.quarantine(source, identity(source))
        receipt = next(self.m.receipts.glob('*.json'))
        row = json.loads(receipt.read_text())
        self.assertEqual(row['phase'], 'retry_unconfirmed')
        self.m.finish_quarantine(receipt, row)
        self.m.mylar.assert_called_once()
        row['phase'] = 'quarantined'
        self.m.mylar.side_effect = None
        self.m.mylar.return_value = {'mode': 'stop'}
        self.m.finish_quarantine(receipt, row)
        self.m.finish_quarantine(receipt, row)
        self.assertEqual(self.m.mylar.call_count, 2)
        self.assertEqual(row['phase'], 'retry_stopped')

    def test_decoder_failure_during_file_mutation_is_not_corruption(self):
        source = self.comic(self.downloads)
        def decode(*args, **kwargs):
            source.write_bytes(b'new file')
            return SimpleNamespace(returncode=1, stdout=json.dumps({'failures': [{'error': 'CRC check failed'}]}))
        with patch('maintenance.subprocess.run', side_effect=decode):
            with self.assertRaisesRegex(RuntimeError, 'changed'):
                self.m.info(source)

    def test_cycle_requires_stability_and_reader_ready(self):
        source, target = self.comic(self.downloads), self.comic(self.library)
        self.reader.record(target)
        self.m.cycle(force=True)
        self.assertTrue(source.exists())
        self.m.cycle(force=True)
        self.assertFalse(source.exists())
        self.assertFalse(json.loads((self.state / 'maintenance-status.json').read_text())['errors'])

    def test_ddl_cache_is_scanned_but_active_download_is_retained(self):
        cache = self.downloads.parent / 'ddl-cache'
        cache.mkdir()
        self.worker.config['maintenance']['ddl_cache'] = str(cache)
        source, target = self.comic(cache), self.comic(self.library)
        self.reader.record(target)
        self.m = Maintenance(self.worker)
        self.m.idle = Mock(return_value=True)
        self.m.pending_ddl_names = Mock(return_value={source.name})
        self.m.cycle(force=True)
        self.m.cycle(force=True)
        self.assertTrue(source.exists())
        self.m.pending_ddl_names.return_value = set()
        self.m.cycle(force=True)
        self.m.cycle(force=True)
        self.assertFalse(source.exists())

    def test_html_saved_as_comic_is_quarantined_as_invalid_content(self):
        source = self.downloads / 'Comic.cbz'
        source.write_bytes(b'<!DOCTYPE html><html>Download unavailable</html>')
        with self.assertRaises(CorruptArchive):
            self.m.info(source)
        self.assertTrue(source.exists())

    def test_stable_unmatched_file_is_reported_without_mutation(self):
        source = self.comic(self.downloads)
        checksum = digest(source)
        self.m.issue_match.return_value = None
        self.m.cycle(force=True)
        self.m.cycle(force=True)
        self.assertEqual(self.m.mylar.call_args.args[0], 'reportImportProblems')
        report = json.loads(self.m.mylar.call_args.kwargs['report'])
        self.assertEqual(report, [{'name': source.name, 'kind': 'unmatched', 'issueid': '', 'comicid': ''}])
        self.assertEqual(digest(source), checksum)

    def test_unpack_staging_is_not_treated_as_completed_download(self):
        stage = self.downloads / '.mylar-unpack-example'
        stage.mkdir()
        source = self.comic(stage)
        self.m.cycle(force=True)
        self.m.cycle(force=True)
        report = json.loads(self.m.mylar.call_args.kwargs['report'])
        self.assertEqual(report, [])
        self.assertTrue(source.exists())

    def test_real_crc_failure_detected(self):
        source = self.comic(self.downloads)
        data = source.read_bytes()
        self.assertIn(PNG, data)
        source.write_bytes(data.replace(PNG, b'X' + PNG[1:], 1))
        with self.assertRaises(CorruptArchive):
            self.m.info(source)


if __name__ == '__main__':
    unittest.main()

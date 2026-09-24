"""Real archive cleanup, preservation, and interrupted recovery checks."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from maintenance import Maintenance, CorruptArchive
from normalize import digest, identity
from test_normalize import PNG, TOOL, Reader


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

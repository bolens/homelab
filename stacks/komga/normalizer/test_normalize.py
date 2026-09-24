"""Real archive fixtures plus reader API state-machine regression tests."""

import base64
import copy
import json
import os
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from normalize import Normalizer, digest, identity

TOOL = os.environ.get('ARCHIVING_UTILS_BIN') or shutil.which('archiving-utils')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9ZkAAAAASUVORK5CYII=')


class Reader:
    def __init__(self, root):
        self.root = root
        self.index = {}
        self.submissions = 0
        self.fail_submission = False

    def books(self):
        return copy.deepcopy(self.index)

    def record(self, path, book_id=None, progress=None):
        self.index[str(path)] = {'id': book_id or path.name, 'seriesId': 'series',
                                'media': {'status': 'READY', 'pagesCount': 2},
                                'readProgress': progress}

    def scan(self):
        for path in self.root.glob('*.cbz'):
            if str(path) not in self.index:
                self.record(path)

    def analyze(self, book_id):
        for book in self.index.values():
            if book['id'] == book_id:
                book['media']['status'] = 'READY'

    def upgrade(self, job):
        self.submissions += 1
        if self.fail_submission:
            raise RuntimeError('Ambiguous API timeout')
        source, target = Path(job['source']), Path(job['destination'])
        before = self.index.pop(str(source))
        shutil.copyfile(job['prepared'], target)
        source.unlink()
        self.record(target, 'replacement', before['readProgress'])


@unittest.skipUnless(TOOL, 'Set ARCHIVING_UTILS_BIN to a validated archiving-utils executable')
class NormalizerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.state = self.root / 'state'
        self.pages = self.root / 'pages'
        for path in (self.library, self.state, self.pages):
            path.mkdir()
        (self.pages / 'page 01.png').write_bytes(PNG)
        (self.pages / 'page 02.png').write_bytes(PNG)
        (self.pages / 'ComicInfo.xml').write_text('<ComicInfo><Title>Fixture</Title></ComicInfo>')
        self.reader = Reader(self.library)
        self.config = {'roots': [str(self.library)], 'state': str(self.state),
                       'converter': TOOL, 'settle_seconds': 0}
        self.worker = Normalizer(self.config, self.reader)

    def archive(self, suffix='.cb7', format_name='cb7'):
        output = self.library / ('Unusual [name] ü' + suffix)
        result = subprocess.run([TOOL, 'folder-to-' + format_name, '--apply',
                                 '--output', str(output), str(self.pages)],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        return output

    def receipts(self):
        return [json.loads(p.read_text()) for p in self.worker.jobs.glob('*/receipt.json')]

    def test_real_cb7_and_compressed_tar_formats(self):
        for suffix, format_name in (('.cb7', 'cb7'), ('.cbt', 'cbt'),
                                   ('.cbt.gz', 'cbt-gz'), ('.cbt.bz2', 'cbt-bz2'),
                                   ('.cbt.xz', 'cbt-xz'), ('.cbt.zst', 'cbt-zst')):
            with self.subTest(format=format_name):
                source = self.archive(suffix, format_name)
                original_hash = digest(source)
                receipt = self.worker.prepare(source, {})
                self.worker.advance(receipt, {})
                self.worker.advance(receipt, self.reader.books())
                job = json.loads(receipt.read_text())
                self.assertEqual(job['phase'], 'done')
                self.assertEqual(digest(Path(job['original'])), original_hash)
                self.assertEqual(self.worker.info(Path(job['destination'])), job['inventory'])
                self.assertFalse(source.exists())
                Path(job['destination']).unlink()
                self.reader.index.clear()

    def test_mislabeled_cbz_keeps_reader_identity(self):
        source = self.archive('.cbz')
        self.reader.record(source, 'existing-book', {'page': 1, 'completed': False})
        self.reader.index[str(source)]['media']['status'] = 'UNSUPPORTED'
        self.worker.cycle()
        self.worker.cycle()
        self.assertEqual(self.reader.index[str(source)]['id'], 'existing-book')
        self.assertEqual(self.receipts()[0]['phase'], 'done')
        self.assertEqual(self.reader.submissions, 0)

    def test_indexed_archive_uses_upgrade_and_preserves_progress(self):
        source = self.archive('.cbr')  # Valid 7z payload with a reader-recognized extension.
        self.reader.record(source, 'old', {'page': 1, 'completed': False})
        self.worker.cycle()
        self.worker.cycle()
        job = self.receipts()[0]
        self.assertEqual(job['phase'], 'done')
        self.assertEqual(job['replacement_id'], 'replacement')
        self.assertEqual(self.reader.submissions, 1)
        self.assertEqual(self.reader.index[job['destination']]['readProgress']['page'], 1)

    def test_ambiguous_submission_is_not_repeated_after_restart(self):
        source = self.archive('.cbr')
        self.reader.record(source, 'old')
        self.reader.fail_submission = True
        self.worker.cycle()
        self.assertEqual(self.receipts()[0]['phase'], 'submitted')
        restarted = Normalizer(self.config, self.reader)
        restarted.cycle()
        self.assertEqual(self.reader.submissions, 1)
        self.assertTrue(source.exists())

    def test_restart_after_atomic_publication_does_not_reconvert(self):
        source = self.archive()
        receipt = self.worker.prepare(source, {})
        job = json.loads(receipt.read_text())
        self.worker.publish(job)
        restarted = Normalizer(self.config, self.reader)
        restarted.cycle()
        restarted.cycle()
        self.assertEqual(json.loads(receipt.read_text())['phase'], 'done')

    def test_collision_and_changed_source_are_preserved(self):
        source = self.archive()
        destination = source.with_suffix('.cbz')
        destination.write_bytes(b'existing content')
        with self.assertRaises(FileExistsError):
            self.worker.prepare(source, {})
        self.assertEqual(destination.read_bytes(), b'existing content')
        destination.unlink()
        receipt = self.worker.prepare(source, {})
        source.write_bytes(b'changed source')
        with self.assertRaises(RuntimeError):
            self.worker.advance(receipt, {})
        self.assertEqual(source.read_bytes(), b'changed source')
        self.assertFalse(destination.exists())

    def test_corrupt_archive_is_reported_and_not_retried_each_poll(self):
        source = self.library / 'broken.cb7'
        source.write_bytes(b'not an archive')
        self.worker.cycle()
        self.assertTrue(self.worker.errors)
        with patch.object(self.worker, 'prepare', side_effect=AssertionError('retried')):
            self.worker.cycle()
        self.assertEqual(source.read_bytes(), b'not an archive')
        self.assertFalse(source.with_suffix('.cbz').exists())

    def test_unstable_and_symlinked_sources_are_skipped(self):
        source = self.archive()
        self.worker.config['settle_seconds'] = 120
        self.assertEqual(list(self.worker.candidates()), [])
        self.worker.observed[str(source)] = (identity(source), 0)
        self.assertEqual(list(self.worker.candidates()), [source])
        source.write_bytes(b'changed')
        self.assertEqual(list(self.worker.candidates()), [])
        source.unlink()
        source.symlink_to(self.pages / 'page 01.png')
        self.assertEqual(list(self.worker.candidates()), [])

    def test_missing_root_is_not_created(self):
        self.library.rmdir()
        with self.assertRaises(ValueError):
            Normalizer(self.config, self.reader)
        self.assertFalse(self.library.exists())

    def test_mylar_rechecks_only_the_affected_series(self):
        config_dir = self.root / 'mylar'
        config_dir.mkdir()
        (config_dir / 'config.ini').write_text('[API]\napi_key = fixture-key\n')
        with closing(sqlite3.connect(config_dir / 'mylar.db')) as db, db:
            db.execute('CREATE TABLE comics (ComicID TEXT, ComicLocation TEXT)')
            db.executemany('INSERT INTO comics VALUES (?,?)', [
                ('affected', str(self.library)), ('unrelated', '/different/library')])
        self.worker.config['mylar'] = {'url': 'http://mylar.invalid', 'config_dir': str(config_dir)}
        with patch('normalize.request', return_value={'success': True}) as api:
            self.worker.refresh_mylar({'destination': str(self.library / 'comic.cbz')})
        api.assert_called_once_with('http://mylar.invalid', '/api', form={
            'apikey': 'fixture-key', 'cmd': 'recheckFiles', 'id': 'affected'})


if __name__ == '__main__':
    unittest.main()

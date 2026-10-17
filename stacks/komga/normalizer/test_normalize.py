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

from normalize import Normalizer, api_path, digest, identity

TOOL = os.environ.get('ARCHIVING_UTILS_BIN') or shutil.which('archiving-utils')
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j9ZkAAAAASUVORK5CYII=')


class ReaderPathTest(unittest.TestCase):
    def test_raw_reader_paths_keep_literal_punctuation(self):
        path = '/data/comics/RWBY 2019-11-27 (#07) 100%20?!.cbz'
        self.assertEqual(api_path(path), Path(path))

    def test_file_uri_paths_decode_encoded_punctuation(self):
        self.assertEqual(api_path('file:///data/comics/RWBY%20(%2307).cbz'), Path('/data/comics/RWBY (#07).cbz'))


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


class DigestOriginalTest(unittest.TestCase):
    """Real filesystem/FD reads; no archive backend or application initialization."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / 'source.cbz'
        self.raw = b'original'
        self.source.write_bytes(self.raw)

    def trace(self, change, *, before_read=False):
        import contextlib
        original_read, original_open = os.read, Path.open
        facts = {'read': 0, 'requests': [], 'changed': False}
        def act():
            if not facts['changed']:
                facts['changed'] = True
                change()
        def read(fd, size):
            facts['requests'].append(size)
            if before_read:act()
            raw = original_read(fd, size)
            facts['read'] += len(raw)
            if not before_read:act()
            return raw
        class Stream:
            def __init__(self, stream):self.stream = stream
            def __enter__(self):return self
            def __exit__(self, *args):return self.stream.__exit__(*args)
            def __getattr__(self, name):return getattr(self.stream, name)
            def readinto(self, buffer):
                facts['requests'].append(len(buffer))
                if before_read:act()
                count = self.stream.readinto(buffer)
                facts['read'] += count
                if not before_read:act()
                return count
        def opened(path, mode='r', *args, **kwargs):
            stream = original_open(path, mode, *args, **kwargs)
            return Stream(stream) if path == self.source and mode == 'rb' else stream
        @contextlib.contextmanager
        def contexts():
            with patch('os.read', side_effect=read), patch.object(Path, 'open', opened):yield facts
        return contexts()

    def test_growth_refuses_after_only_declared_bytes(self):
        def grow():
            with self.source.open('ab') as stream:stream.write(b'x' * 64)
        with self.trace(grow) as facts:
            with self.assertRaises(ValueError):digest(self.source)
        self.assertEqual(facts['read'], len(self.raw))
        self.assertLessEqual(max(facts['requests']), len(self.raw))

    def test_truncation_refuses_without_extra_probe(self):
        with self.trace(lambda:self.source.write_bytes(b'')) as facts:
            with self.assertRaises(ValueError):digest(self.source)
        self.assertEqual(facts['read'], len(self.raw))

    def test_short_original_refuses(self):
        with self.trace(lambda:self.source.write_bytes(b''), before_read=True) as facts:
            with self.assertRaises(ValueError):digest(self.source)
        self.assertEqual(facts['read'], 0)

    def test_same_bytes_replacement_refuses(self):
        other = self.root / 'replacement';other.write_bytes(self.raw)
        with self.trace(lambda:other.replace(self.source)):
            with self.assertRaises(ValueError):digest(self.source)

    def test_metadata_change_refuses(self):
        with self.trace(lambda:self.source.chmod(0o600)):
            with self.assertRaises(ValueError):digest(self.source)

    def test_stable_regular_empty_and_hardlinks_keep_SHA(self):
        import hashlib
        expected = hashlib.sha256(self.raw).hexdigest()
        self.assertEqual(digest(self.source), expected)
        linked = self.root / 'linked.cbz';os.link(self.source, linked)
        self.assertEqual(digest(linked), expected)
        self.assertEqual(digest(self.source), expected)
        empty = self.root / 'empty';empty.touch()
        with patch('os.read', side_effect=AssertionError('empty file needs no read')):
            self.assertEqual(digest(empty), hashlib.sha256(b'').hexdigest())

    def test_leaf_symlink_directory_and_FIFO_refuse_before_open(self):
        import normalize
        linked = self.root / 'link';linked.symlink_to(self.source)
        fifo = self.root / 'fifo';os.mkfifo(fifo)
        for path in (linked, self.root, fifo):
            with patch.object(normalize.os, 'open', side_effect=AssertionError('nonregular opened')):
                with self.assertRaises(ValueError):digest(path)

    def test_replacement_between_stat_and_open_refuses(self):
        import normalize
        original = os.open;other = self.root / 'replacement';other.write_bytes(self.raw)
        def opened(path, flags, *args, **kwargs):
            if path == self.source:other.replace(self.source)
            return original(path, flags, *args, **kwargs)
        with patch.object(normalize.os, 'open', side_effect=opened):
            with self.assertRaises(ValueError):digest(self.source)

    def test_partial_reads_have_exact_total(self):
        import hashlib
        original = os.read;amount = []
        def short(fd, size):
            value = original(fd, min(size, 3));amount.append(len(value));return value
        with patch('os.read', side_effect=short):
            self.assertEqual(digest(self.source), hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(sum(amount), len(self.raw))

    def test_read_exception_closes_original_FD(self):
        original_close = os.close
        with patch('os.read', side_effect=RuntimeError('fixture')), patch('os.close', wraps=original_close) as closed:
            with self.assertRaisesRegex(RuntimeError, 'fixture'):digest(self.source)
        self.assertEqual(closed.call_count, 1)


if __name__ == '__main__':
    unittest.main()

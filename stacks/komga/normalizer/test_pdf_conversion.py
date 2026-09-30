"""Real Poppler page rendering, recovery and native import staging fixtures."""
import hashlib
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from normalize import Normalizer, archive_suffix, digest
from pdf_conversion import derivative, page_count, policy
from test_normalize import Reader, TOOL


def document(path):
    """Small valid PDF with distinct colored pages, text, rotation and mixed sizes."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 100] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>',
               b'', b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 200] /Rotate 90 /Resources << >> /Contents 6 0 R >>', b'',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    for index, content in ((3, b'1 0 0 rg 0 0 200 100 re f 0 0 0 rg BT /F1 16 Tf 10 40 Td (Page one) Tj ET'),
                           (5, b'0 0 1 rg 0 0 100 200 re f')):
        objects[index] = b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream'
    value = b'%PDF-1.4\n'
    offsets = [0]
    for index, content in enumerate(objects, 1):
        offsets.append(len(value))
        value += str(index).encode() + b' 0 obj\n' + content + b'\nendobj\n'
    offset = len(value)
    value += b'xref\n0 8\n0000000000 65535 f \n'
    value += b''.join(('%010d 00000 n \n' % n).encode() for n in offsets[1:])
    value += b'trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n' + str(offset).encode() + b'\n%%EOF\n'
    path.write_bytes(value)


class PolicyTest(unittest.TestCase):
    def test_defaults_and_invalid_values(self):
        self.assertFalse(policy({})['enabled'])
        for value in (None, [], {'enabled': 1}, {'long_edge_pixels': True},
                      {'long_edge_pixels': 6001}, {'max_pages': 0}):
            with self.assertRaises(ValueError):
                policy({'pdf_conversion': value})
        self.assertEqual(archive_suffix(Path('Book.PDF')), '.pdf')
        self.assertIsNone(archive_suffix(Path('Book.pdf.part')))

    def test_encrypted_and_missing_page_count(self):
        for output in ('Pages: 2\nEncrypted: yes\n', 'Pages: 0\nEncrypted: no\n', 'Encrypted: no\n'):
            with patch('pdf_conversion.run', return_value=output), self.assertRaises(ValueError):
                page_count(Path('fixture.pdf'), 1000)


@unittest.skipUnless(TOOL and shutil.which('pdftoppm'), 'Actual archiving-utils and Poppler required')
class PDFTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.library, self.state = self.root / 'library', self.root / 'state'
        self.library.mkdir(); self.state.mkdir()
        self.source = self.library / 'Art [__100__] ü.pdf'
        document(self.source)
        self.checksum = digest(self.source)
        self.config = {'roots': [str(self.library)], 'state': str(self.state), 'converter': TOOL,
                       'settle_seconds': 0, 'pdf_conversion': {'enabled': True, 'long_edge_pixels': 512}}
        self.reader = Reader(self.library)
        self.worker = Normalizer(self.config, self.reader)

    def test_render_pages_and_verified_reuse(self):
        from PIL import Image
        output = derivative(self.worker, self.source)
        record = json.loads(output.with_name('receipt.json').read_text())
        self.assertEqual(len(record['pages']), 2)
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(archive.namelist(), ['page-00001.png', 'page-00002.png'])
            for index, name in enumerate(archive.namelist()):
                with archive.open(name) as stream, Image.open(stream) as image:
                    image.load()
                    self.assertEqual(image.size, (512, 256))
                    self.assertEqual(image.getpixel((1, 1))[:3], (255, 0, 0) if index == 0 else (0, 0, 255))
                self.assertEqual(hashlib.sha256(archive.read(name)).hexdigest(), record['pages'][index]['sha256'])
        with patch('pdf_conversion.run', side_effect=AssertionError('must reuse verified derivative')):
            self.assertEqual(derivative(self.worker, self.source), output)
        self.assertEqual(digest(self.source), self.checksum)
        self.assertEqual(digest(Path(record['original'])), self.checksum)

    def test_corrupt_input_and_limits_publish_nothing(self):
        for change in ('corrupt', 'pages', 'bytes'):
            with self.subTest(change=change):
                self.source.write_bytes(b'%PDF-broken') if change == 'corrupt' else document(self.source)
                self.worker.config['pdf_conversion']['max_pages'] = 1 if change == 'pages' else 1000
                self.worker.config['max_expanded_bytes'] = 1500 if change == 'bytes' else 2147483648
                with self.assertRaises(ValueError): derivative(self.worker, self.source)
                self.assertFalse(list(self.state.rglob('pages.cbz')))
                self.assertTrue(self.source.exists())

    def test_disabled_and_partial_are_not_candidates(self):
        self.worker.config['pdf_conversion']['enabled'] = False
        disabled = Normalizer(self.worker.config, self.reader)
        self.assertEqual(list(disabled.candidates()), [])
        with self.assertRaises(ValueError): derivative(disabled, self.source)
        self.source.rename(self.source.with_suffix('.pdf.part'))
        self.assertEqual(list(self.worker.candidates()), [])

    def test_interrupted_derivative_commit_regenerates_from_verified_pdf(self):
        from normalize import save
        def fail_receipt(path, value):
            if Path(path).name == 'receipt.json':
                raise OSError('fixture interruption before receipt commit')
            return save(path, value)
        with patch('normalize.save', side_effect=fail_receipt), self.assertRaises(OSError):
            derivative(self.worker, self.source)
        output = next(self.state.rglob('pages.cbz'))
        self.assertFalse(output.with_name('receipt.json').exists())
        recovered = derivative(self.worker, self.source)
        self.assertEqual(self.worker.info(recovered)['page_count'], 2)
        self.assertEqual(digest(self.source), self.checksum)

    def test_cache_tampering_does_not_overwrite(self):
        output = derivative(self.worker, self.source)
        output.write_bytes(b'changed')
        with self.assertRaises(ValueError): derivative(self.worker, self.source)
        self.assertEqual(output.read_bytes(), b'changed')
        self.assertEqual(digest(self.source), self.checksum)

    def test_library_upgrade_preserves_reader_progress(self):
        self.reader.record(self.source, progress={'page': 1, 'completed': False})
        receipt = self.worker.prepare(self.source, self.reader.books())
        for _ in range(6): self.worker.advance(receipt, self.reader.books())
        job = json.loads(receipt.read_text())
        self.assertEqual(job['phase'], 'done')
        self.assertEqual(digest(Path(job['original'])), self.checksum)
        self.assertEqual(self.reader.books()[job['destination']]['readProgress']['page'], 1)

    def test_collision_and_changed_source(self):
        destination = self.source.with_suffix('.cbz')
        destination.write_bytes(b'unrelated')
        with self.assertRaises(FileExistsError): self.worker.prepare(self.source, {})
        self.assertEqual(destination.read_bytes(), b'unrelated')
        from pdf_conversion import run
        def changing(*args, **kwargs):
            result = run(*args, **kwargs)
            if args[0][0] == 'pdftoppm': self.source.write_bytes(b'changed')
            return result
        with patch('pdf_conversion.run', side_effect=changing), self.assertRaises(ValueError):
            derivative(self.worker, self.source)
        self.assertFalse(list(self.state.rglob('pages.cbz')))

    def test_live_render_is_deferred_to_preserved_source_outside_writer_cycle(self):
        from pdf_conversion import Pending, render_pending
        self.worker.pdf_defer = True
        with self.assertRaises(Pending): derivative(self.worker, self.source)
        saved = self.worker.pdf_pending[1]
        self.assertEqual(digest(saved), self.checksum)
        self.assertFalse(list(self.state.rglob('pages.cbz')))
        render_pending(self.worker)
        self.assertTrue(self.worker.pdf_defer)
        self.assertIsNone(self.worker.pdf_pending)
        output = derivative(self.worker, self.source)
        self.assertEqual(self.worker.info(output)['page_count'], 2)

    def test_interrupted_prepared_copy_retries_without_partial_destination(self):
        derivative(self.worker, self.source)
        target = self.library / 'prepared.cbz'
        with patch('normalize.shutil.copyfileobj', side_effect=OSError('fixture disk full')):
            with self.assertRaises(OSError):
                self.worker.convert_tool('comic-to-cbz', '--apply', '--output', target, self.source)
        self.assertFalse(target.exists())
        self.worker.convert_tool('comic-to-cbz', '--apply', '--output', target, self.source)
        self.assertEqual(self.worker.info(target)['page_count'], 2)
        self.assertEqual(digest(self.source), self.checksum)

    def test_maximum_page_space_check_precedes_rendering(self):
        self.worker.config['pdf_conversion']['long_edge_pixels'] = 6000
        with patch('pdf_conversion.shutil.disk_usage', return_value=SimpleNamespace(free=200 * 1024**2)):
            with self.assertRaisesRegex(ValueError, 'rendering storage'):
                derivative(self.worker, self.source)
        self.assertFalse(list(self.state.rglob('pages.cbz')))
        self.assertEqual(digest(self.source), self.checksum)

    def test_cached_pdf_import_stages_cbz_and_retains_pdf(self):
        from import_recovery import submit
        from import_match import match
        database = self.root / 'mylar.db'
        with closing(sqlite3.connect(database)) as db, db:
            db.executescript("CREATE TABLE comics(ComicID TEXT,ComicName TEXT,ComicYear TEXT);"
                             "CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);"
                             "INSERT INTO comics VALUES('10','Art','2020');"
                             "INSERT INTO issues VALUES('100','10','Snatched','1','2020-01-01','');")
        self.worker.config['mylar'] = {'config_dir': str(self.root)}
        cache = self.root / 'cache'; cache.mkdir()
        maintenance = SimpleNamespace(worker=self.worker, roots=[self.library, cache], state=self.state,
                    settings={'auto_import': True, 'ddl_cache': str(cache), 'mylar_ddl_cache': '/config/mylar/cache'},
                    idle=Mock(return_value=True), mylar=Mock(return_value=True), info=self.worker.info)
        matched = match(self.source, database)
        output = derivative(self.worker, self.source)
        with patch('import_recovery.shutil.disk_usage', return_value=SimpleNamespace(free=output.stat().st_size * 2 + 128 * 1024**2 - 1)):
            with self.assertRaisesRegex(RuntimeError, 'recovery storage'):
                submit(maintenance, self.source, matched)
        self.assertFalse(list(cache.glob('.mylar-recovery-*')))
        with patch.object(self.worker, 'convert_tool', side_effect=OSError('fixture disk full')):
            with self.assertRaises(OSError): submit(maintenance, self.source, matched)
        self.assertFalse(list(cache.glob('.mylar-recovery-*')))
        self.assertEqual(submit(maintenance, self.source, matched), 'import_queued')
        self.assertEqual(submit(maintenance, self.source, matched), 'import_queued')
        maintenance.mylar.assert_called_once()
        staged = list(cache.glob('.mylar-recovery-*/*.cbz'))
        self.assertEqual(len(staged), 1)
        self.assertEqual(self.worker.info(staged[0])['page_count'], 2)
        self.assertEqual(digest(self.source), self.checksum)


if __name__ == '__main__':
    unittest.main()

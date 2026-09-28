"""Offline acceptance against the real pinned console command, not a mocked CLI."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import shutil
import struct
import tempfile
import unittest
import zipfile
import zlib

from tagger_cli import EXECUTABLE, VERSION, save, version_supported, saved_result
from tagger_metadata import overrides, parse, reconcile
from tagger_runtime import ProcessResult, run


def png():
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', 2, 2, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\xff\0\0' * 2) * 2)) + chunk(b'IEND', b''))


def contents(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        return {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist() if n != 'ComicInfo.xml'}, archive.comment


class ModernTaggerTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.original = self.root/'original.cbz'
        self.stage = self.root/'stage'
        self.stage.mkdir()
        self.archive = self.stage/'Étoile #1.cbz'

    def fixture(self, xml=None):
        with zipfile.ZipFile(self.original, 'w') as archive:
            archive.writestr('001.png', png())
            archive.writestr('002.png', png())
            archive.writestr('extras/credit.txt', 'Fixture credit: preserve verbatim')
            archive.comment = json.dumps({'ComicBookInfo/1.0': {'title': 'Legacy title'}}).encode()
            if xml is not None:
                archive.writestr('ComicInfo.xml', xml)
        self.original.chmod(0o640)
        shutil.copy2(self.original, self.archive)
        return hashlib.sha256(self.original.read_bytes()).hexdigest(), contents(self.archive)

    def test_pinned_version_and_headless_dependencies(self):
        self.assertEqual(metadata.version('comictagger'), VERSION)
        import icu
        self.assertEqual(icu.ICU_VERSION, '70.1')
        installed = {d.metadata['Name'].lower() for d in metadata.distributions()}
        self.assertFalse(installed & {'pyqt6', 'pyqt6-webengine', 'pyside6', 'setuptools', 'wheel', 'pip'})
        result = run([EXECUTABLE, '--config', str(self.root/'config'), '--version'], cwd=self.root, timeout=10)
        self.assertEqual(result.returncode, 1)
        self.assertTrue(version_supported(result))

    def test_legacy_tagger_remains_independent(self):
        result = run(['/lsiopy/bin/python3', '/app/mylar3/comictagger.py', '--configfolder', str(self.root/'legacy'), '--version'], cwd=self.root, timeout=10)
        self.assertEqual(result.state, 'ok')
        self.assertIn(b'ComicTagger 1.3.5', result.stdout)

    def test_wrong_version_and_error_banner_rejected(self):
        for result in (ProcessResult('failed', 1, b'ComicTagger 1.5.5:  Copyright x'),
                       ProcessResult('failed', 2, b'ComicTagger '+VERSION.encode()+b':  Copyright x'),
                       ProcessResult('timed_out', -9, b'ComicTagger '+VERSION.encode()+b':  Copyright x')):
            self.assertFalse(version_supported(result))

    def test_regular_annual_variant_and_unicode_archives(self):
        for extra in ({'volume':1}, {'format':'Annual'}, {'scan_info':'Variant B'}, {'title':'Étoile & 月'}):
            with self.subTest(extra=extra):
                original, before = self.fixture()
                value = dict(series='Fixture', issue='1', **extra)
                result = save(self.archive, value, workdir=self.stage)
                self.assertEqual(result.state, 'saved')
                self.assertEqual(contents(self.archive), before)
                self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), original)
                self.assertEqual(self.original.stat().st_mode & 0o777, 0o640)
                with zipfile.ZipFile(self.archive) as archive:
                    root = parse(archive.read('ComicInfo.xml'))
                self.assertEqual(root.findtext('Series'), 'Fixture')
                self.assertEqual(root.findtext('Number'), '1')
                field = {'volume':'Volume', 'format':'Format', 'scan_info':'ScanInformation', 'title':'Title'}
                for key, expected in extra.items():self.assertEqual(root.findtext(field[key]), str(expected))
                self.assertFalse(list(self.stage.glob('.tagger-*')))

    def test_existing_metadata_and_arcs_reconcile_after_real_write(self):
        old = b'<ComicInfo><Series>Original</Series><Notes>Keep notes</Notes><Web>https://example.org/comic</Web><StoryArc>Old</StoryArc><StoryArcNumber>9</StoryArcNumber><Pages><Page Image="0" Bookmark="Cover"/></Pages><Extension keep="yes">Extra</Extension></ComicInfo>'
        original, before = self.fixture(old)
        result = save(self.archive, {'series':'Fixture','issue':'1','story_arcs':['First','Second']}, workdir=self.stage)
        self.assertEqual(result.state, 'saved')
        with zipfile.ZipFile(self.archive) as archive:tagged = archive.read('ComicInfo.xml')
        # The actual built-in writer does not supply the new sequence numbers.
        self.assertNotEqual(parse(tagged).findtext('StoryArcNumber'), '1,2')
        merged = reconcile(old, tagged, updates=overrides(volume=1, reading_order=[('First',1),('Second',2)]))
        root = parse(merged)
        self.assertEqual(root.findtext('Notes'), 'Keep notes')
        self.assertEqual(root.findtext('Web'), 'https://example.org/comic')
        self.assertEqual(root.findtext('StoryArc'), 'First,Second')
        self.assertEqual(root.findtext('StoryArcNumber'), '1,2')
        self.assertEqual(root.find('Pages/Page').get('Bookmark'), 'Cover')
        self.assertEqual(root.findtext('Extension'), 'Extra')
        self.assertEqual(contents(self.archive), before)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), original)

    def test_repeated_tagging_with_preservation_policy_is_unchanged(self):
        self.fixture()
        fields = {'series':'Fixture','issue':'1','volume':1}
        self.assertEqual(save(self.archive, fields, workdir=self.stage).state, 'saved')
        with zipfile.ZipFile(self.archive) as archive:first = archive.read('ComicInfo.xml')
        self.assertEqual(save(self.archive, fields, workdir=self.stage).state, 'saved')
        with zipfile.ZipFile(self.archive) as archive:second = archive.read('ComicInfo.xml')
        normalized = reconcile(first, second)
        self.assertEqual(reconcile(first, normalized), normalized)
        self.assertEqual(parse(normalized).findtext('Notes'), parse(first).findtext('Notes'))

    def test_corrupt_archive_is_not_success(self):
        self.archive.write_bytes(b'not a comic archive')
        self.assertEqual(save(self.archive, {'series':'Fixture'}, workdir=self.stage).state, 'failed')
        self.assertEqual(self.archive.read_bytes(), b'not a comic archive')

    def test_unavailable_executable_preserves_staged_and_original(self):
        original, before = self.fixture()
        self.assertEqual(save(self.archive, {'series':'Fixture'}, workdir=self.stage, executable='/no/such/tagger').state, 'unavailable')
        self.assertEqual(contents(self.archive), before)
        self.assertEqual(hashlib.sha256(self.original.read_bytes()).hexdigest(), original)

    def test_malformed_or_wrong_target_result_is_not_success(self):
        self.fixture()
        cases = ('not-json', '[]', json.dumps({'action':'save','status':'success','tags_written':['cr'],'original_path':'/wrong.cbz','renamed_path':None}))
        for output in cases:
            self.assertFalse(saved_result(ProcessResult('ok', 0, output.encode()), self.archive))

    def test_corresponding_sources_match_installed_distributions(self):
        sources = Path('/opt/comictagger/sources')
        manifest = json.loads((sources/'manifest.json').read_text())
        self.assertEqual({row['name'] for row in manifest}, {'comicfn2dict','chardet','isocodes'})
        self.assertEqual(len(manifest), 3)
        for row in manifest:
            self.assertEqual(row['version'], metadata.version(row['name']))
            self.assertEqual(hashlib.sha256((sources/row['filename']).read_bytes()).hexdigest(), row['sha256'])

    def test_symlink_non_cbz_and_outside_workspace_rejected(self):
        self.fixture()
        link = self.stage/'link.cbz'
        link.symlink_to(self.original)
        for path in (link, self.original):
            with self.assertRaises(ValueError):save(path, {'series':'Fixture'}, workdir=self.stage)
        renamed = self.stage/'comic.cbr'
        renamed.write_bytes(self.archive.read_bytes())
        with self.assertRaises(ValueError):save(renamed, {'series':'Fixture'}, workdir=self.stage)


if __name__ == '__main__':
    unittest.main()

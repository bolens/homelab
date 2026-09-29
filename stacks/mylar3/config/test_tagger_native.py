"""Native policy, automatic placement lifetime and startup recovery fixtures."""
from importlib import import_module
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile


class NativeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        mylar = ModuleType('mylar'); mylar.__path__ = [str(Path(__file__).parent)]
        mylar.DATA_DIR = str(self.root); mylar.logger = Mock()
        mylar.CONFIG = SimpleNamespace(ENABLE_META=True, CT_TAG_CR=True, CT_TAG_CBL=False,
            CBR2CBZ_ONLY=False, CT_CBZ_OVERWRITE=True, COMICVINE_API='fixture',
            COMICVINE_URL='https://example.invalid/api/', CVAPI_RATE=2,
            CMTAG_VOLUME=True, CMTAG_START_YEAR_AS_VOLUME=False, SETDEFAULTVOLUME=True)
        self.db = sqlite3.connect(':memory:'); self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE issues(IssueID TEXT, ComicID TEXT);
            CREATE TABLE annuals(IssueID TEXT, ReleaseComicID TEXT, Deleted INT);
            CREATE TABLE storyarcs(IssueID TEXT, ComicID TEXT);
            CREATE TABLE comics(ComicID TEXT, ComicVersion TEXT, ComicYear TEXT);
            INSERT INTO issues VALUES('123','456');
            INSERT INTO comics VALUES('456','v1','2017');
            INSERT INTO annuals VALUES('124','457',0);
            INSERT INTO comics VALUES('457','v2','2018');''')
        mylar.db = SimpleNamespace(DBConnection=lambda: SimpleNamespace(select=lambda sql,args:self.db.execute(sql,args).fetchall()))
        context = patch.dict(sys.modules, {'mylar':mylar}); context.start(); self.addCleanup(context.stop)
        self.mylar = mylar
        self.native = import_module('mylar.tagger_native')
        self.writers = import_module('mylar.native_writers'); mylar.native_writers = self.writers
        self.handoff = import_module('mylar.tagger_handoff'); mylar.tagger_handoff = self.handoff
        self.base = import_module('mylar.tagger_adapter')
        self.lookup = import_module('mylar.tagger_lookup')
        self.cli = import_module('mylar.tagger_cli')
        self.writers.initialize()
        self.source = self.root/'comic.cbz'
        with zipfile.ZipFile(self.source, 'w') as archive: archive.writestr('001.png', b'page')
        self.source.chmod(0o640); os.setxattr(self.source, 'user.fixture', b'original')
        self.before = self.source.read_bytes()
        self.lookup_mock = Mock(return_value=self.lookup.LookupResult('ok', {'series':'Fixture','issue':'1'}))
        lookup_patch = patch.object(self.lookup, 'lookup', self.lookup_mock)
        lookup_patch.start(); self.addCleanup(lookup_patch.stop)
        def save(path, metadata, **kwargs):
            with zipfile.ZipFile(path, 'a') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series></ComicInfo>')
            return self.cli.TagResult('saved')
        cli_patch = patch.object(self.base, 'save', side_effect=save)
        cli_patch.start(); self.addCleanup(cli_patch.stop)

    def test_manual_annual_uses_release_volume_and_canonical_handoff(self):
        result = self.native.run(str(self.root), filename=str(self.source), issueid='124', comversion='v99', manualmeta=True)
        self.assertIsInstance(result, self.handoff.Published); self.assertTrue(result.valid_for(self.source))
        self.assertEqual(self.lookup_mock.call_args.kwargs['volumeid'], '457')
        with zipfile.ZipFile(self.source) as archive:
            self.assertIn(b'<Volume>2</Volume>', archive.read('ComicInfo.xml'))
        self.assertEqual(os.getxattr(self.source, 'user.fixture'), b'original')
        self.assertFalse(self.writers.owner().fenced(tagger=True))

    def test_automatic_stage_survives_until_native_placement_and_is_cleaned_after(self):
        with self.writers.operation():
            result = self.native.run(str(self.root), filename=str(self.source), issueid='123')
            self.assertIs(type(result), str)
            target = Path(result); self.assertTrue(target.exists())
            self.assertEqual(self.source.read_bytes(), self.before)
            # Automatic input retains legacy native destination ownership policy.
            # Only in-place publication promises exact filesystem ACL preservation.
            self.assertEqual(os.listxattr(target), [])
            self.assertEqual(os.getxattr(self.source, 'user.fixture'), b'original')
        self.assertFalse(target.parent.exists()); self.assertTrue(self.source.exists())

    def test_link_placement_never_receives_disposable_staging(self):
        for mode in ('softlink','hardlink'):
            self.mylar.CONFIG.FILE_OPTS=mode
            with self.writers.operation():
                result=self.native.run(str(self.root),filename=str(self.source),issueid='123')
            self.assertIsInstance(result,self.handoff.Failure)
        self.lookup_mock.assert_not_called();self.assertEqual(self.source.read_bytes(),self.before)

    def test_automatic_without_complete_processing_owner_is_rejected(self):
        result = self.native.run(str(self.root), filename=str(self.source), issueid='123')
        self.assertIsInstance(result, self.handoff.Failure)
        self.lookup_mock.assert_not_called()

    @unittest.skipUnless(Path('/opt/comictagger/bin/comictagger').exists(), 'Pinned runtime image required')
    def test_real_cli_through_native_manual_and_automatic_callers(self):
        backend = import_module('mylar.tagger_backend')
        self.mylar.CONFIG.TAGGER_BACKEND = 'modern'
        legacy = Mock(side_effect=AssertionError('Unexpected legacy fallback'))
        with patch.object(self.base, 'save', self.cli.save):
            with self.writers.operation():
                result = backend.dispatch(legacy, str(self.root), filename=str(self.source), issueid='123')
                self.assertIs(type(result), str)
                with zipfile.ZipFile(result) as archive:
                    self.assertIsNone(archive.testzip()); self.assertEqual(archive.read('001.png'), b'page')
                    self.assertIn(b'<Volume>1</Volume>', archive.read('ComicInfo.xml'))
            result = backend.dispatch(legacy, str(self.root), filename=str(self.source), issueid='124', manualmeta=True)
            self.assertTrue(result.valid_for(self.source))
            self.assertEqual(os.getxattr(self.source, 'user.fixture'), b'original')

    def test_backend_routes_once_only_when_code_gate_is_open(self):
        backend=import_module('mylar.tagger_backend')
        legacy=Mock(return_value='legacy')
        self.mylar.CONFIG.TAGGER_BACKEND='legacy'
        self.assertEqual(backend.dispatch(legacy,'folder'),'legacy')
        self.mylar.CONFIG.TAGGER_BACKEND='modern'
        with patch.object(self.native,'run',return_value='modern') as modern:
            with patch.object(backend,'status',return_value={'modern_available':False}):
                self.assertIsInstance(backend.dispatch(legacy,'folder'),self.handoff.Failure)
            modern.assert_not_called()
            self.assertEqual(backend.dispatch(legacy,'folder',issueid='123'),'modern')
            modern.assert_called_once_with('folder',issueid='123')
        legacy.assert_called_once()

    def test_deleted_ambiguous_unknown_and_untracked_annual_are_safe(self):
        self.db.execute("UPDATE annuals SET Deleted=1 WHERE IssueID='124'")
        with self.assertRaises(ValueError): self.native.catalog('124')
        self.db.execute("INSERT INTO annuals VALUES('123','999',0)")
        with self.assertRaises(ValueError): self.native.catalog('123')
        with self.assertRaises(ValueError): self.native.catalog('999')
        self.db.execute("INSERT INTO annuals VALUES('125','458',0)")
        self.assertEqual(self.native.catalog('125'), ('125','458',{}))
        self.db.execute("INSERT INTO storyarcs VALUES('126','459')")
        self.assertEqual(self.native.catalog('126'), ('126','459',{}))

    def test_missing_bound_state_and_invalid_receipts_block_scanners(self):
        journal = self.root/'modern-tagger-v2'/'journal-v2'
        (journal/('c'*32+'.json')).write_text('invalid')
        with self.writers.owner().hold(allow_tagger_pending=True) as writer:
            writer.mark_tagger_pending()
        ran = Mock()
        with self.assertRaises(ValueError): self.writers.guard(ran)()
        ran.assert_not_called(); self.assertTrue(self.writers.owner().fenced(tagger=True))
        (journal/('c'*32+'.json')).unlink(); journal.rename(journal.with_name('old-journal'))
        with self.assertRaises(FileNotFoundError): self.writers.initialize()
        self.assertTrue(self.writers.owner().fenced(tagger=True))

    def test_startup_restores_missing_name_before_native_reader_enters_even_in_legacy(self):
        code = '''import os,sys,types
from pathlib import Path
m=types.ModuleType('mylar');m.__path__=[sys.argv[2]];m.DATA_DIR=sys.argv[1]
sys.modules['mylar']=m
from mylar import native_writers,tagger_native,tagger_adapter,tagger_cli
import zipfile
def saved(path, metadata, **kwargs):
 with zipfile.ZipFile(path,'a') as archive:archive.writestr('ComicInfo.xml','<ComicInfo><Series>Fixture</Series></ComicInfo>')
 return tagger_cli.TagResult('saved')
tagger_adapter.save=saved
tagger_adapter._checkpoint=lambda value:os._exit(71) if value=='after_displace' else None
with native_writers.operation() as writer:
 publisher,staging=tagger_native.state(writer)
 writer.mark_tagger_pending()
 publisher.tag(Path(sys.argv[1])/'comic.cbz',{'series':'Fixture'},token='d'*32)
'''
        result = subprocess.run([sys.executable, '-c', code, str(self.root), str(Path(__file__).parent)], timeout=20)
        self.assertEqual(result.returncode, 71); self.assertFalse(self.source.exists())
        self.assertTrue(self.writers.owner().fenced(tagger=True))
        self.mylar.CONFIG.TAGGER_BACKEND = 'legacy'
        self.writers.initialize()
        @self.writers.guard
        def scan(): self.assertEqual(self.source.read_bytes(), self.before)
        scan(); self.assertFalse(self.writers.owner().fenced(tagger=True))


if __name__ == '__main__': unittest.main()

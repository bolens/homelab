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

    def test_automatic_in_place_honors_enable_and_backend(self):
        self.mylar.CONFIG.TAGGER_BACKEND = 'modern'
        self.mylar.CONFIG.ENABLE_META = False
        result = self.native.run(str(self.root), filename=str(self.source), issueid='123',
                                 manualmeta=True, automatic_in_place=True)
        self.assertFalse(result.valid_for(self.source))
        self.mylar.CONFIG.ENABLE_META = True
        self.mylar.CONFIG.TAGGER_BACKEND = 'legacy'
        result = self.native.run(str(self.root), filename=str(self.source), issueid='123',
                                 manualmeta=True, automatic_in_place=True)
        self.assertFalse(result.valid_for(self.source))
        self.lookup_mock.assert_not_called()
        self.assertEqual(self.source.read_bytes(), self.before)

    def test_persistent_token_reconciles_without_second_lookup(self):
        self.mylar.CONFIG.TAGGER_BACKEND = 'modern'
        args = dict(filename=str(self.source), issueid='123', manualmeta=True,
                    automatic_in_place=True, publication_token='a'*32)
        first = self.native.run(str(self.root), **args)
        self.assertTrue(first.valid_for(self.source))
        second = self.native.run(str(self.root), **args)
        self.assertTrue(second.valid_for(self.source))
        self.assertEqual(self.lookup_mock.call_count, 1)

    def conversion_queue(self):
        import json
        converted = import_module('mylar.converted_tagging')
        store = import_module('mylar.workflow_store').Store(self.root)
        self.mylar.CONFIG.POST_PROCESSING = True
        self.mylar.CONFIG.TAGGER_BACKEND = 'modern'
        for table in ('issues', 'annuals'):
            self.db.execute('ALTER TABLE '+table+' ADD COLUMN Location TEXT')
            self.db.execute('ALTER TABLE '+table+' ADD COLUMN Status TEXT')
        self.db.execute('ALTER TABLE annuals ADD COLUMN ComicID TEXT')
        self.db.execute('ALTER TABLE comics ADD COLUMN ComicLocation TEXT')
        self.db.execute('ALTER TABLE comics ADD COLUMN AgeRating TEXT')
        self.db.execute('ALTER TABLE storyarcs ADD COLUMN StoryArc TEXT')
        self.db.execute('ALTER TABLE storyarcs ADD COLUMN ReadingOrder TEXT')
        self.db.execute('UPDATE comics SET ComicLocation=? WHERE ComicID="456"', [str(self.root)])
        self.db.execute('UPDATE issues SET Location=?,Status="Downloaded"', [self.source.name])
        payload = json.dumps(dict(version=1, path=str(self.source), sha256=self.base.fingerprint(self.source)))
        key = converted.admit(payload, store)['key']
        queue = converted.Queue(store, converted.catalog, self.writers.operation, converted.inspect_archive,
                                converted.tag, converted.recover, converted.settings)
        return converted, store, key, queue

    def test_converted_file_publishes_and_restart_recovers_real_receipt(self):
        converted, store, key, queue = self.conversion_queue()
        def crash(job):
            result = converted.tag(job)
            self.assertEqual(result, 'added')
            raise KeyboardInterrupt()
        queue.tag = crash
        with self.assertRaises(KeyboardInterrupt): queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'tagging')
        queue.tag = Mock(side_effect=AssertionError('must not tag again'))
        queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'completed')
        self.assertEqual(self.lookup_mock.call_count, 1)
        self.assertEqual(os.getxattr(self.source, 'user.fixture'), b'original')
        with zipfile.ZipFile(self.source) as archive:
            self.assertEqual(archive.read('001.png'), b'page')
        queue.tag.assert_not_called()

    def conversion_repairs_stale_location_then_tags_and_survives_rescan(self, suffix):
        converted, store, key, queue = self.conversion_queue()
        for table in ('issues', 'annuals'):
            self.db.execute('ALTER TABLE '+table+' ADD COLUMN ComicName TEXT')
        self.mylar.db = SimpleNamespace(DBConnection=lambda: SimpleNamespace(
            select=lambda sql,args:self.db.execute(sql,args).fetchall(),
            action=lambda sql,args:self.db.execute(sql,args)))
        self.db.execute('UPDATE issues SET Location=?,Status="Archived"',[self.source.with_suffix(suffix).name])
        queue.tick()
        self.assertEqual(store.get('converted_tag',key)['phase'],'completed')
        self.assertEqual(tuple(self.db.execute('SELECT Location,Status FROM issues').fetchone()),(self.source.name,'Downloaded'))
        self.mylar.workflow=SimpleNamespace(store=lambda:store)
        reconcile=import_module('mylar.converted_catalog')
        @self.writers.guard
        @reconcile.rescan
        def filename_rescan(comicid):
            self.db.execute('UPDATE issues SET Status="Archived"')
        filename_rescan('456')
        self.assertEqual(self.db.execute('SELECT Status FROM issues').fetchone()[0],'Downloaded')
        self.assertEqual(self.lookup_mock.call_count,1)
        with zipfile.ZipFile(self.source) as archive:
            self.assertEqual(archive.read('001.png'),b'page')
            self.assertIn('ComicInfo.xml',archive.namelist())

    def test_conversion_repairs_stale_location_then_tags_and_survives_rescan(self):
        self.conversion_repairs_stale_location_then_tags_and_survives_rescan('.cbr')

    def test_pdf_conversion_repairs_then_tags_and_survives_rescan(self):
        self.conversion_repairs_stale_location_then_tags_and_survives_rescan('.pdf')

    def test_conversion_changed_during_lookup_is_not_published(self):
        converted, store, key, queue = self.conversion_queue()
        def external_change(**kwargs):
            with zipfile.ZipFile(self.source, 'w') as archive:
                archive.writestr('001.png', b'external replacement')
            return self.lookup.LookupResult('ok', {'series':'Fixture', 'issue':'1'})
        self.lookup_mock.side_effect = external_change
        queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'review')
        with zipfile.ZipFile(self.source) as archive:
            self.assertEqual(archive.read('001.png'), b'external replacement')
            self.assertNotIn('ComicInfo.xml', archive.namelist())

    def test_conversion_annual_matches_parent_path_but_uses_release_metadata(self):
        converted, store, key, queue = self.conversion_queue()
        self.db.execute('DELETE FROM issues')
        self.db.execute('UPDATE annuals SET ComicID="456",Location=?,Status="Downloaded"', [self.source.name])
        queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'completed')
        self.assertEqual(self.lookup_mock.call_args.kwargs['volumeid'], '457')

    def test_conversion_normalizes_trailing_slash_in_catalog_directory(self):
        converted, store, key, queue = self.conversion_queue()
        self.db.execute('UPDATE comics SET ComicLocation=? WHERE ComicID="456"', [str(self.root)+'/'])
        queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'completed')
        self.assertEqual(self.lookup_mock.call_count, 1)

    def test_conversion_rejects_ambiguous_exact_location(self):
        converted, store, key, queue = self.conversion_queue()
        self.db.execute('UPDATE annuals SET ComicID="456",Location=?,Status="Downloaded"', [self.source.name])
        queue.tick()
        self.assertEqual(store.get('converted_tag', key)['phase'], 'review')
        self.lookup_mock.assert_not_called()
        self.assertEqual(self.source.read_bytes(), self.before)

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

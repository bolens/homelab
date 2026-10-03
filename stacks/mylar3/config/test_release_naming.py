"""Native name publication retains content, owner and a recoverable journal."""
import importlib
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch, Mock


class NamingTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'Old 001 (2020).cbz'
        self.source.write_bytes(b'unchanged archive fixture')
        self.db = sqlite3.connect(':memory:'); self.db.row_factory = sqlite3.Row; self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE comics (ComicID,ComicLocation);
          CREATE TABLE issues (IssueID,ComicID,Location,Status,ComicSize,ComicName);
          CREATE TABLE annuals (IssueID,ComicID,Location,Status,Deleted,ComicName);
        ''')
        self.db.execute('INSERT INTO comics VALUES (?,?)', ('2',str(self.root)))
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?,?,?)', ('1','2',self.source.name,'Downloaded',self.source.stat().st_size,'Old')); self.db.commit()
        def action(sql, args):
            result = self.db.execute(sql,args); self.db.commit(); return result
        self.database = SimpleNamespace(select=lambda sql,args:self.db.execute(sql,args).fetchall(),action=action)
        self.mylar = ModuleType('mylar'); self.mylar.__path__=[str(Path(__file__).parent)]; self.mylar.DATA_DIR=str(self.root)
        context=patch.dict(sys.modules,{'mylar':self.mylar});context.start();self.addCleanup(context.stop)
        self.native = importlib.import_module('mylar.release_naming')
        from mylar import native_writers, tagger_adapter, workflow_store
        from mylar.media_writer import Writer
        self.writer=Writer(self.root/'media-writer',create=True)
        self.store=workflow_store.Store(self.root)
        self.request=dict(version=1,source=str(self.source),target='Old.001.(2020).cbz',issueid='1',comicid='2',sha256=tagger_adapter.fingerprint(self.source))
        self.info=dict(self.request,table='issues',status='Downloaded',year='2020')
        self.addCleanup(patch.stopall)
        patch.object(self.native,'services',return_value=(self.database,self.store)).start()
        patch.object(self.native,'proposal',return_value=self.info).start()
        patch.object(self.native,'parsed',return_value=({'IssueYear':'2020'},'Print')).start()
        patch.object(native_writers,'owner',return_value=self.writer).start()
        self.target=self.source.with_name(self.request['target'])

    def test_commit_and_idempotent_acknowledgement_preserve_inode(self):
        inode=self.source.stat().st_ino; original=self.source.read_bytes()
        result=self.native.rename(self.request)
        self.assertEqual(result['phase'],'committed'); self.assertFalse(self.source.exists())
        self.assertEqual(self.target.stat().st_ino,inode); self.assertEqual(self.target.read_bytes(),original)
        row=self.db.execute('SELECT * FROM issues').fetchone()
        self.assertEqual(row['Location'],self.target.name);self.assertEqual(row['Status'],'Downloaded')
        self.assertEqual(self.native.rename(self.request)['key'],result['key'])
        self.assertFalse(self.writer.fenced(release=True))

    def test_catalog_failure_recovers_without_old_source_path(self):
        with patch.object(self.database,'action',return_value=None):
            with self.assertRaises(ValueError):self.native.rename(self.request)
        self.assertFalse(self.source.exists());self.assertTrue(self.target.exists())
        self.assertTrue(self.writer.fenced(release=True))
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertFalse(self.writer.fenced(release=True))
        self.assertEqual(self.native.rename(self.request)['phase'],'committed')

    def test_unowned_collision_and_stale_proposal_do_not_mutate(self):
        self.target.write_bytes(b'other')
        with self.assertRaises(ValueError):self.native.rename(self.request)
        self.assertEqual(self.target.read_bytes(),b'other'); self.assertTrue(self.source.exists())
        self.target.unlink()
        with self.assertRaises(ValueError):self.native.rename(dict(self.request,sha256='a'*64))
        self.assertFalse(self.writer.fenced(release=True))

    def test_invalid_new_name_rolls_back_only_owned_link(self):
        with patch.object(self.native,'parsed',side_effect=ValueError('wrong name')):
            with self.assertRaises(ValueError):self.native.rename(self.request)
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertFalse(self.writer.fenced(release=True))
        self.assertEqual(self.store.get('release_name',self.native.key(self.request))['phase'],'rejected')

    def test_changed_target_keeps_recovery_fence(self):
        with patch.object(self.database,'action',return_value=None):
            with self.assertRaises(ValueError):self.native.rename(self.request)
        self.target.write_bytes(b'changed')
        with self.writer.hold(allow_release_pending=True):
            with self.assertRaises(ValueError):self.native.recover(self.writer)
        self.assertTrue(self.writer.fenced(release=True))

    def test_worker_admission_waits_for_release_fence(self):
        from mylar.media_writer import Busy
        with self.writer.hold(allow_release_pending=True):
            self.native.bind_store(self.writer, self.store)
            self.writer.mark_release_pending()
            with self.assertRaises(ValueError):
                with self.writer.hold(allow_pending=True):pass
        with self.assertRaises(Busy):
            with self.writer.hold(timeout=0):pass
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        with self.writer.hold(timeout=0):pass

    def test_crash_after_link_and_after_catalog_commit_reconciles(self):
        import os
        original_link=os.link
        def interrupted_link(*args,**kwargs):
            original_link(*args,**kwargs);raise KeyboardInterrupt()
        with patch('mylar.release_naming.os.link',side_effect=interrupted_link):
            with self.assertRaises(KeyboardInterrupt):self.native.rename(self.request)
        self.assertTrue(self.source.exists());self.assertTrue(self.target.exists())
        original_action=self.database.action
        def interrupted_catalog(*args,**kwargs):
            original_action(*args,**kwargs);raise KeyboardInterrupt()
        with self.writer.hold(allow_release_pending=True):
            with patch.object(self.database,'action',side_effect=interrupted_catalog):
                with self.assertRaises(KeyboardInterrupt):self.native.recover(self.writer)
        self.assertFalse(self.source.exists());self.assertTrue(self.writer.fenced(release=True))
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertEqual(self.native.rename(self.request)['phase'],'committed')

    def test_missing_journal_binding_never_clears_pending_fence(self):
        with self.writer.hold(allow_release_pending=True):
            self.writer.mark_release_pending()
            with self.assertRaises(ValueError):self.native.recover(self.writer)
        self.assertTrue(self.writer.fenced(release=True));self.assertTrue(self.source.exists())

    def test_number_identity_keeps_fraction_and_letter_variants_distinct(self):
        self.assertEqual(self.native.number_key('1½'),self.native.number_key('01.50'))
        self.assertEqual(self.native.number_key('1 MU'),self.native.number_key('001.MU'))
        self.assertNotEqual(self.native.number_key('1 MU'),self.native.number_key('1 AU'))

    def test_release_volume_uses_annual_owner_and_holds_conflicting_evidence(self):
        import xml.etree.ElementTree as ET
        database=SimpleNamespace(select=Mock(return_value=[{'ComicVersion':'v2','ComicYear':'2020'}]))
        owner=dict(table='annuals',row={'ReleaseComicID':'3'},parent={'ComicVersion':'v1'})
        root=ET.fromstring('<ComicInfo><Volume>2</Volume></ComicInfo>')
        self.assertEqual(self.native.release_volume(database,owner,root,Path('Series Annual v2 001 (2020).cbz')),'2')
        database.select.assert_called_with('SELECT ComicVersion,ComicYear FROM comics WHERE ComicID=?',['3'])
        root.find('Volume').text='2020'
        self.assertEqual(self.native.release_volume(database,owner,root,Path('Series Annual v2 001 (2020).cbz')),'2')
        regular=dict(table='issues',parent={'ComicVersion':'v2','ComicYear':'2020'})
        self.assertEqual(self.native.release_volume(database,regular,root,Path('Series v2 001 (2021).cbz')),'2')
        root.find('Volume').text='2019'
        with self.assertRaises(ValueError):self.native.release_volume(database,regular,root,Path('Series v2 001 (2021).cbz'))
        root.find('Volume').text='1'
        with self.assertRaises(ValueError):self.native.release_volume(database,owner,root,Path('Series Annual v2 001 (2020).cbz'))

    def test_collected_issue_volume_is_independent_of_series_run(self):
        import xml.etree.ElementTree as ET
        root=ET.fromstring('<ComicInfo><Volume>2</Volume></ComicInfo>')
        owner=dict(table='issues',row={'Issue_Number':'5'},parent={'ComicVersion':'v2','ComicYear':'2020','Type':'GN'})
        for name in ('Series v5 (GN) (2020).cbz','Series.v2.v005.(GN).(2020).cbz'):
            self.assertEqual(self.native.release_volume(None,owner,root,Path(name)),'2')
        with self.assertRaises(ValueError):
            self.native.release_volume(None,owner,root,Path('Series.v3.v005.(GN).(2020).cbz'))

    def test_run_tokens_exclude_catalog_title_labels_and_scanner_credit(self):
        import xml.etree.ElementTree as ET
        root=ET.fromstring('<ComicInfo><Series>Project V3</Series><Volume>2</Volume></ComicInfo>')
        owner=dict(table='issues',row={'Issue_Number':'1'},parent={'ComicName':'Project V3','ComicVersion':'v2','ComicYear':'2020','Type':'Print'})
        for name in ('Project.V3.v2.001.(2020).(Digital)-Group.cbz',
                     'Project.V3.v2.001.(2020).(Edition v4)-Empire-v3.cbz'):
            self.assertEqual(self.native.release_volume(None,owner,root,Path(name)),'2')
        with self.assertRaises(ValueError):
            self.native.release_volume(None,owner,root,Path('Project.V3.v4.001.(2020)-Empire-v3.cbz'))

    def test_explicit_collected_parser_requires_exact_series_and_type(self):
        checker=SimpleNamespace(comic_type='GN',watchcomic='Series Name',AlternateSearch=None)
        value='Series.Name.v2.v005.(GN).(2020).(Digital)-Group'
        self.assertEqual(self.native.collected(checker,value),dict(series='Series Name',number='005',year='2020',kind='GN'))
        self.assertIsNone(self.native.collected(checker,value.replace('Series.Name','Other.Name')))
        self.assertIsNone(self.native.collected(checker,value.replace('(GN)','(HC)')))
        self.assertIsNone(self.native.collected(checker,'Series.Name.v2.v005.(2020)'))

    def test_explicit_scanner_prefix_is_retained_and_legacy_source_is_split(self):
        self.assertEqual(self.native.release_group(Path('Series.001.(2020).(Digital)-Digital-Empire.cbz'),'Digital-Empire'),'Digital-Empire')
        self.assertEqual(self.native.release_group(Path('Series 001 (2020) (Digital-Empire).cbz'),'Digital-Empire'),'Empire')

    def test_scanner_suffix_leaves_real_filename_untouched(self):
        value='Old.001.(2020).(Digital)-Son.of.Ultron-Empire'
        self.assertEqual(self.native.scanner(value),('Old.001.(2020).(Digital)','Son.of.Ultron-Empire'))
        self.assertEqual(self.native.scanner('Old 001 (2020) (Empire)'),('Old 001 (2020) (Empire)',None))


class MissingYearTest(unittest.TestCase):
    def setUp(self):
        import zipfile
        self.zipfile = zipfile
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root / 'Fixture 001.cbz'
        self.db = sqlite3.connect(':memory:'); self.db.row_factory = sqlite3.Row; self.addCleanup(self.db.close)
        self.db.executescript("""CREATE TABLE comics(ComicID,ComicLocation,ComicName,ComicYear,ComicVersion,Type);
          CREATE TABLE issues(IssueID,ComicID,ComicName,Location,Status,Issue_Number,IssueDate);
          CREATE TABLE annuals(IssueID,ComicID,ComicName,Location,Status,Deleted);""")
        self.db.execute('INSERT INTO comics VALUES (?,?,?,?,?,?)', ('1',str(self.root),'Fixture','2020',None,'Print'))
        self.db.execute('INSERT INTO issues VALUES (?,?,?,?,?,?,?)', ('2','1','Fixture',self.source.name,'Downloaded','1','2020-02-01'))
        self.database = SimpleNamespace(select=lambda sql,args:self.db.execute(sql,args).fetchall())
        module = ModuleType('mylar'); module.__path__ = [str(Path(__file__).parent)]
        context = patch.dict(sys.modules, {'mylar':module}); context.start(); self.addCleanup(context.stop)
        self.native = importlib.import_module('mylar.release_naming')
        self.parsed = patch.object(self.native, 'parsed', return_value=({'IssueYear':None,'scangroup':None}, 'Print'))
        self.parsed.start(); self.addCleanup(self.parsed.stop)
        self.write_xml()

    def write_xml(self, *, year='2020', web='https://comicvine.gamespot.com/fixture/4000-2/'):
        with self.zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('page.jpg', b'preserved page')
            archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Fixture</Series><Number>1</Number><Volume>2020</Volume><Year>'+year+'</Year><Web>'+web+'</Web></ComicInfo>')

    def test_absent_filename_year_uses_exact_existing_identity_evidence(self):
        original = self.source.read_bytes()
        proposal = self.native.proposal(self.database, str(self.source))
        self.assertEqual((proposal['year'],proposal['issueid'],proposal['comicid']), ('2020','2','1'))
        self.assertEqual(self.source.read_bytes(), original)

    def test_missing_or_unrelated_catalog_links_cannot_supply_year(self):
        for web in ('', 'https://example.test/4000-2/', 'https://comicvine.gamespot.com/fixture/4000-3/',
                    'https://comicvine.gamespot.com/fixture/4000-2/ https://comicvine.gamespot.com/other/4000-3/'):
            with self.subTest(web=web):
                self.write_xml(web=web)
                with self.assertRaisesRegex(ValueError, 'year'):self.native.proposal(self.database, str(self.source))

    def test_metadata_catalog_and_explicit_filename_year_conflicts_stay_held(self):
        self.write_xml(year='2019')
        with self.assertRaisesRegex(ValueError, 'year'):self.native.proposal(self.database, str(self.source))
        self.write_xml()
        with patch.object(self.native,'parsed',return_value=({'IssueYear':'2019'},'Print')):
            with self.assertRaisesRegex(ValueError, 'year'):self.native.proposal(self.database, str(self.source))
        self.db.execute("UPDATE issues SET IssueDate='0000-00-00'")
        with self.assertRaisesRegex(ValueError, 'year'):self.native.proposal(self.database, str(self.source))


class ApiTest(unittest.TestCase):
    def test_primary_authority_and_sanitized_errors(self):
        from patch_release_naming import api
        source = "class Api:\n    allowed = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs): pass\n"
        patched = api(source); self.assertEqual(api(patched), patched)
        namespace = {'mylar':SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True, API_KEY='primary'))}
        exec(compile(patched, '<fixture>', 'exec'), namespace)
        endpoint = namespace['Api']()
        endpoint._failureResponse = lambda message:dict(success=False,error=message)
        endpoint._successResponse = lambda data:dict(success=True,data=data)
        functions = SimpleNamespace(get=Mock(return_value={'version':1}),rename=Mock(return_value={'version':1}),status=Mock(return_value={'version':1}))
        with patch.dict(sys.modules, {'mylar':SimpleNamespace(release_naming=functions)}):
            for method, function in [('_getReleaseNaming',functions.get),('_renameLibraryFile',functions.rename),('_releaseNamingStatus',functions.status)]:
                endpoint.apikey='read-only';getattr(endpoint,method)(source='path',naming='{}',token='token')
                function.assert_not_called();self.assertFalse(endpoint.data['success'])
                endpoint.apikey='primary';getattr(endpoint,method)(source='path',naming='{}',token='token')
                self.assertTrue(endpoint.data['success'])
                function.side_effect=RuntimeError('/private/path api-key')
                getattr(endpoint,method)(source='path',naming='{}',token='token')
                self.assertNotIn('/private',str(endpoint.data))


if __name__ == '__main__':unittest.main()

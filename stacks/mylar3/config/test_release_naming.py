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

    def test_verified_rename_preserves_all_overlapping_pack_confirmations(self):
        import base64
        import hashlib
        from mylar import pack_intake
        patch.object(pack_intake.workflow, 'store', return_value=self.store).start()
        info = self.source.stat()
        member = dict(id='d'*64, kind='issue', phase='confirmed', name=self.source.name,
                      issueid='1', comicid='2', destination=str(self.source),
                      destination_sha256=self.request['sha256'],
                      signature=[info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns])
        sidecar = dict(id='e'*64, kind='sidecar', phase='preserved',
                       sidecar=base64.b64encode(b'original credits').decode(),
                       sha256=hashlib.sha256(b'original credits').hexdigest())
        for key in ('a'*64, 'b'*64, 'c'*64):
            self.store.set('pack', key, dict(id=key, ddl_id=key[0], phase='confirmed',
                           name='Original pack', inventory_complete=True, cleanup_complete=True,
                           members=[dict(member), dict(sidecar)]))
        self.assertTrue(all(row['complete'] for row in pack_intake.snapshot()))
        self.native.rename(self.request)
        self.assertTrue(all(row['complete'] for row in pack_intake.snapshot()))
        for record in self.store.active('pack', {'confirmed'}):
            self.assertEqual(record['members'][0]['destination'], str(self.target))
            self.assertEqual(record['members'][1], sidecar)
            self.assertTrue(record['cleanup_complete'])
        self.native.rename(self.request)
        self.assertTrue(all(row['complete'] for row in pack_intake.snapshot()))

    def test_catalog_failure_recovers_without_old_source_path(self):
        with patch.object(self.database,'action',return_value=None):
            with self.assertRaises(ValueError):self.native.rename(self.request)
        self.assertFalse(self.source.exists());self.assertTrue(self.target.exists())
        self.assertTrue(self.writer.fenced(release=True))
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertFalse(self.writer.fenced(release=True))
        self.assertEqual(self.native.rename(self.request)['phase'],'committed')

    def test_interrupted_rejection_recovers_without_recreating_target_link(self):
        from mylar import pack_bindings
        member=dict(id='d'*64,kind='issue',phase='confirmed',issueid='1',comicid='2',
                    destination=str(self.source),destination_sha256=self.request['sha256'],
                    signature=pack_bindings.signature(self.source))
        self.store.set('pack','a'*64,dict(id='a'*64,phase='confirmed',members=[member]))
        setter=self.store.set
        def interrupted(kind,key,value):
            if kind=='release_name' and value['phase']=='rejected':raise SystemExit(71)
            return setter(kind,key,value)
        with patch.object(self.native,'parsed',side_effect=ValueError('wrong name')), patch.object(self.store,'set',side_effect=interrupted):
            with self.assertRaises(SystemExit):self.native.rename(self.request)
        self.assertEqual(self.store.get('release_name',self.native.key(self.request))['phase'],'rejecting')
        original_signature=pack_bindings.signature(self.source)
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertEqual(pack_bindings.signature(self.source),original_signature)
        self.assertEqual(self.store.get('pack','a'*64)['members'][0]['signature'],original_signature)
        self.assertFalse(self.target.exists());self.assertFalse(self.writer.fenced(release=True))

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

    def rejected_request(self):
        with patch.object(self.native,'parsed',side_effect=ValueError('wrong name')):
            with self.assertRaises(ValueError):self.native.rename(self.request)
        return dict(self.request,version=2,retry_of=self.native.key(self.request))

    def test_explicit_replacement_retains_rejected_predecessor_and_is_idempotent(self):
        retry=self.rejected_request(); parent=self.store.get('release_name',retry['retry_of'])
        with self.assertRaises(ValueError):self.native.rename(self.request)
        result=self.native.rename(retry)
        self.assertEqual(result['phase'],'committed');self.assertNotEqual(result['key'],retry['retry_of'])
        self.assertEqual(self.store.get('release_name',retry['retry_of']),parent)
        self.assertEqual(self.native.rename(retry)['phase'],'committed')
        self.assertEqual(self.target.read_bytes(),b'unchanged archive fixture')

    def test_replacement_requires_rejected_matching_unchanged_source(self):
        retry=self.rejected_request()
        for changed in (dict(retry,retry_of='a'*64),dict(retry,issueid='9'),dict(retry,sha256='a'*64)):
            with self.assertRaises(ValueError):self.native.rename(changed)
        self.source.write_bytes(b'changed')
        with self.assertRaises(ValueError):self.native.rename(retry)
        self.assertFalse(self.target.exists());self.assertFalse(self.writer.fenced(release=True))

    def test_replacement_revalidates_year_and_predecessor_evidence(self):
        retry=self.rejected_request();self.info['year']='2021'
        with self.assertRaises(ValueError):self.native.rename(retry)
        self.info['year']='2020';self.native.rename(retry)
        parent=self.store.get('release_name',retry['retry_of']);parent['extra']='changed'
        self.store.set('release_name',retry['retry_of'],parent)
        with self.assertRaises(ValueError):self.native.rename(retry)

    def test_replacement_catalog_failure_recovers_without_replaying_predecessor(self):
        retry=self.rejected_request();parent=self.store.get('release_name',retry['retry_of'])
        with patch.object(self.database,'action',return_value=None):
            with self.assertRaises(ValueError):self.native.rename(retry)
        self.assertFalse(self.source.exists());self.assertTrue(self.writer.fenced(release=True))
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertEqual(self.native.rename(retry)['phase'],'committed')
        self.assertEqual(self.store.get('release_name',retry['retry_of']),parent)

    def test_interrupted_replacement_keeps_fence_on_parent_evidence_drift(self):
        retry=self.rejected_request();parent=self.store.get('release_name',retry['retry_of'])
        with patch.object(self.database,'action',return_value=None):
            with self.assertRaises(ValueError):self.native.rename(retry)
        changed=dict(parent,year='2021');self.store.set('release_name',retry['retry_of'],changed)
        with self.writer.hold(allow_release_pending=True):
            with self.assertRaises(ValueError):self.native.recover(self.writer)
        self.assertTrue(self.writer.fenced(release=True))
        self.assertEqual(self.store.get('release_name',self.native.key(retry))['phase'],'published')
        self.store.set('release_name',retry['retry_of'],parent)
        with self.writer.hold(allow_release_pending=True):self.native.recover(self.writer)
        self.assertEqual(self.native.rename(retry)['phase'],'committed')

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

    def test_explicit_print_fields_require_verified_series_and_shape(self):
        checker=SimpleNamespace(comic_type='Print',watchcomic='Detective Comics',AlternateSearch=None)
        value='Detective.Comics.v3.1019.(2020).(Webrip)-The.Last.Kryptonian-DCP'
        self.assertEqual(self.native.print_fields(checker,value),dict(series='Detective Comics',number='1019',year='2020',volume='3'))
        self.assertEqual(self.native.print_fields(checker,value.replace('.1019.','.1020.'))['year'],'2020')
        self.assertIsNone(self.native.print_fields(checker,value.replace('Detective.Comics','Other.Series')))
        self.assertIsNone(self.native.print_fields(checker,value.replace('.v3.','.v2020.')))
        self.assertIsNone(self.native.print_fields(checker,value.replace('(2020)','(1019)')))
        self.assertIsNone(self.native.print_fields(checker,value.replace('(Webrip)','(2021).(Webrip)')))
        self.assertEqual(self.native.print_fields(checker,value.replace('(Webrip)','(2020).(Webrip)'))['year'],'2020')
        self.assertIsNone(self.native.print_fields(checker,value.replace('.1019.','.19.')))
        self.assertIsNone(self.native.print_fields(checker,value.replace('(Webrip)','(#1020).(Webrip)')))
        checker.comic_type='GN'
        self.assertIsNone(self.native.print_fields(checker,value))

    def test_explicit_print_fields_preserve_numeric_titles_and_variants(self):
        checker=SimpleNamespace(comic_type='Print',watchcomic='Series 2025',AlternateSearch='Other Series')
        for number in ('001.5','001.MU','-001'):
            value='Series.2025.'+number+'.(2020).(Digital)-Group'
            self.assertEqual(self.native.print_fields(checker,value),dict(series='Series 2025',number=number,year='2020',volume=None))
        self.assertEqual(self.native.print_fields(checker,'Other.Series.v2.001.(2020)')['series'],'Other Series')
        checker.AlternateSearch='Other Series!!42'
        self.assertIsNone(self.native.print_fields(checker,'Other.Series.v2.001.(2020)'))

    def test_padded_number_excludes_verified_numeric_title_prefix(self):
        checker=SimpleNamespace(watchcomic='Gargoyles Winter Special 2025', AlternateSearch=None)
        self.assertEqual(self.native.release_number('Gargoyles.Winter.Special.2025.001.(2025)',checker),'001')
        checker.watchcomic='Gargoyles'
        checker.AlternateSearch='Gargoyles Winter Special 2025!!42'
        self.assertEqual(self.native.release_number('Gargoyles.Winter.Special.2025.001.(2025)',checker),'001')
        checker.watchcomic='Series 2025'
        checker.AlternateSearch=None
        self.assertEqual(self.native.release_number('Series.2025.001.5.(2020)',checker),'001.5')
        self.assertEqual(self.native.release_number('Series.2025.001.MU.(2020)',checker),'001.MU')

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

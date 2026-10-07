"""Mixed-pack preservation, annual recovery and repeat-run fixtures."""
from contextlib import closing
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
import zipfile

from normalize import Normalizer
from maintenance import Maintenance
from pack_recovery import Packs, evidence, kind, source_state
from import_match import catalog, match
from test_normalize import PNG, TOOL
from test_publication_guard import AuthorityFixture


class PackEvidenceTest(unittest.TestCase):
    def test_reused_source_cannot_reuse_a_previous_inventory_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'pack.zip';source.write_bytes(b'first')
            state=root/'records';state.mkdir();owned=state/'fixture';owned.mkdir()
            previous={'id':'fixture','members':[{'id':'old','phase':'confirmed'}],
                      'source_generation':source_state(source,content=True)}
            receipt=owned/'receipt.json';receipt.write_text(json.dumps(previous))
            fake=SimpleNamespace(root=state,local=lambda value:source)
            record={'id':'fixture','source':'/cache/pack.zip','source_generation':previous['source_generation']}
            self.assertEqual(Packs.inventory(fake,record)[1],previous)
            source.write_bytes(b'second')
            with self.assertRaisesRegex(ValueError,'generation changed'):Packs.inventory(fake,record)
            self.assertEqual(json.loads(receipt.read_text()),previous)
            self.assertEqual(source.read_bytes(),b'second')
            record['source_generation']=source_state(source,content=True)
            with self.assertRaisesRegex(ValueError,'receipt generation differs'):
                Packs.inventory(fake,record)

    def test_legacy_directory_receipt_rejects_new_members(self):
        from normalize import digest, identity
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'pack';source.mkdir()
            member=source/'one.cbz';member.write_bytes(b'first')
            state=root/'records';state.mkdir();owned=state/'fixture';owned.mkdir()
            previous={'id':'fixture','outer':None,'members':[{'source':str(member),
                       'sha256':digest(member),'identity':identity(member)}]}
            receipt=owned/'receipt.json';receipt.write_text(json.dumps(previous))
            fake=SimpleNamespace(root=state,local=lambda value:source)
            record={'id':'fixture','source':'/cache/pack'}
            self.assertEqual(Packs.inventory(fake,record)[1],previous)
            (source/'two.cbz').write_bytes(b'new member')
            with self.assertRaisesRegex(ValueError,'inventory changed'):Packs.inventory(fake,record)
            self.assertEqual(json.loads(receipt.read_text()),previous)
            previous['cleanup_verified_at']=1;receipt.write_text(json.dumps(previous));member.unlink()
            self.assertEqual(Packs.inventory(fake,record)[1],previous)

    def test_generation_manifest_matches_shared_portable_vector(self):
        # The native suite asserts this same literal vector independently.
        # Worker images contain only flat /app files, without sibling Mylar code.
        expected='aa2a03cd127c3fbf56c9a89092535ff441a31c94ce628135619bc74f9c4e2fcd'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'pack.zip';source.write_bytes(b'archive')
            companion=source.with_suffix('');companion.mkdir();(companion/'extra.txt').write_bytes(b'credit')
            self.assertEqual(source_state(source,content=True),expected)
            other=root/'mounted';other.mkdir();import shutil
            shutil.copyfile(source,other/source.name);shutil.copytree(companion,other/companion.name)
            self.assertEqual(source_state(other/source.name,content=True),expected)

    def test_full_issue_with_cover_count_is_not_a_supplement(self):
        self.assertEqual(kind(Path('Grimm Tales of Terror v2 005 (2016) (2 covers).cbz'),
                              {'page_count': 27}), 'issue')
        self.assertEqual(kind(Path('Story 005 (2016) (2 covers).cbz'),
                              {'page_count': 2}), 'supplement')
        self.assertEqual(kind(Path('Story 005 (2016) (Cover Collection).cbz'),
                              {'page_count': 27}), 'supplement')

    def test_catalog_version_disambiguates_same_title_and_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Grimm Tales of Terror v2 001 (2015).cbz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('001.png', PNG)
            rows = [('100', '10', 'Wanted', '1', '2015-10-31', 'Grimm Tales of Terror', '2015', 'v2'),
                    ('200', '20', 'Wanted', '1', '2015-09-30', 'Grimm Tales of Terror', '2015', None)]
            self.assertEqual(match(path, None, rows), {'issueid': '100', 'comicid': '10'})
            self.assertIsNone(match(path, None, [rows[1]]))
            self.assertIsNone(match(path, None, rows + [tuple(['300', '30'] + list(rows[0][2:]))]))
            self.assertIsNone(match(path.with_name('Grimm Tales of Terror v3 001 (2015).cbz'), None, rows))

    def test_catalog_reads_explicit_version_and_supports_older_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / 'catalog.db'
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.executescript("CREATE TABLE comics(ComicID,ComicName,ComicYear);"
                    "CREATE TABLE issues(IssueID,ComicID,Status,Issue_Number,IssueDate);"
                    "INSERT INTO comics VALUES('10','Story','2015');"
                    "INSERT INTO issues VALUES('100','10','Wanted','1','2015-10-31');")
                self.assertEqual(catalog(database)[0][7], '')
                connection.execute('ALTER TABLE comics ADD COLUMN ComicVersion')
                connection.execute("UPDATE comics SET ComicVersion='v2'")
            self.assertEqual(catalog(database)[0][7], 'v2')

    def test_ordinal_metadata_agrees_only_after_unique_current_catalog_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Grimm Tales of Terror v2 001 (2015).cbz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Grimm Tales of Terror</Series>'
                                 '<Number>1</Number><Volume>2015</Volume></ComicInfo>')
            row = ('503788', '85478', 'Wanted', '1', '2015-10-01', 'Grimm Tales of Terror', '2015', 'v2')
            self.assertEqual(evidence(path, [row])['series'], 'Grimm Tales of Terror')
            for rows in (None, [], [row[:-1] + ('v3',)], [row, ('999', '888') + row[2:]]):
                with self.subTest(rows=rows), self.assertRaisesRegex(ValueError, 'Filename and metadata disagree'):
                    evidence(path, rows)

    def test_cleaned_pack_revalidation_preserves_history_without_sources(self):
        record={'id':'a'*64,'source':'/cache/removed.zip','phase':'confirmed',
                'cleanup_complete':True,'inventory_complete':True,
                'members':[{'id':'b'*64,'kind':'issue','phase':'confirmed',
                            'destination':'/library/Test.cbz','destination_sha256':'c'*64}]}
        api=Mock(side_effect=lambda command,**kwargs:{'enabled':True,'packs':[record]}
                 if command=='packWork' else {'phase':'confirmed'})
        packs=SimpleNamespace(m=SimpleNamespace(settings={'pack_import':True},mylar=api,worker=SimpleNamespace(config={})),
                              local=lambda value:Path(value),inventory=Mock(),changed=False)
        packs.report=lambda value:Packs.report(packs,value)
        packs.refresh_cleaned=lambda value:Packs.refresh_cleaned(packs,value)
        Packs.cycle(packs)
        packs.inventory.assert_not_called()
        payload=json.loads(api.call_args.kwargs['report'])
        self.assertEqual(payload['members'],record['members'])
        self.assertTrue(payload['cleaned_at'])
        self.assertEqual(api.call_args.args,('packReport',))

    def test_rejected_cleaned_pack_revalidation_keeps_original_proof(self):
        record={'id':'a'*64,'source':'/cache/removed.zip','phase':'confirmed',
                'cleanup_complete':True,'members':[{'id':'b'*64,'phase':'confirmed'}]}
        def api(command,**kwargs):
            if command=='packWork':return {'enabled':True,'packs':[record]}
            raise RuntimeError('Destination proof rejected')
        calls=Mock(side_effect=api)
        packs=SimpleNamespace(m=SimpleNamespace(settings={'pack_import':True},mylar=calls,worker=SimpleNamespace(config={})),
                              local=lambda value:Path(value),inventory=Mock(),changed=False)
        packs.report=lambda value:Packs.report(packs,value)
        packs.refresh_cleaned=lambda value:Packs.refresh_cleaned(packs,value)
        Packs.cycle(packs)
        self.assertEqual(calls.call_count,2)
        self.assertEqual(record['members'][0]['phase'],'confirmed')
        packs.inventory.assert_not_called()

    def test_failed_member_refresh_retains_verified_history_and_never_cleans(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt=Path(directory)/'receipt.json'
            original=dict(id='b'*64,kind='issue',phase='confirmed',issueid='123',comicid='456',
                destination='/library/verified.cbz',destination_sha256='c'*64,reason='Library content verified')
            value=dict(id='a'*64,members=[dict(original)])
            record=dict(id='a'*64,source='/cache/retained.zip',phase='review',members=[dict(original)])
            api=Mock(return_value={'enabled':True,'packs':[record]})
            def failed(member,directory):
                member['destination']='/foreign/replacement.cbz'
                raise ValueError('Current proof unavailable')
            packs=SimpleNamespace(m=SimpleNamespace(settings={'pack_import':True},mylar=api,
                worker=SimpleNamespace(config={}),import_submitted=False),local=lambda p:Path(p),
                inventory=lambda r:(receipt,value),member=failed,
                report=Mock(side_effect=ValueError('Native report holds missing proof')),cleanup=Mock(),changed=False)
            Packs.cycle(packs)
            saved=json.loads(receipt.read_text())['members'][0]
            self.assertEqual({key:saved[key] for key in original},original)
            self.assertIn('verification_review',saved)
            packs.cleanup.assert_not_called()
            self.assertEqual(record['members'][0],original)

    def test_disabled_pdf_keeps_page_archive_with_pdf_extra_as_single_comic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'comic.cbz'
            with zipfile.ZipFile(source, 'w') as archive:
                archive.writestr('001.png', PNG)
                archive.writestr('bonus.pdf', b'%PDF fixture')
            fake = SimpleNamespace(root=root, local=lambda remote:source,
                m=SimpleNamespace(info=lambda path:{'page_count':1,'other_files':[{'name':'bonus.pdf'}]}),
                worker=SimpleNamespace(pdf_policy={'enabled':False},convert_tool=Mock()))
            receipt, result = Packs.inventory(fake, {'id':'fixture','source':'/cache/comic.cbz'})
            fake.worker.convert_tool.assert_not_called()
            self.assertEqual(len(result['members']),1)
            self.assertEqual(result['members'][0]['source'],str(source))

    def test_conflicting_volume_year_never_reaches_catalog_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Test Comic 001 (2017).cbz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Test Comic</Series>'
                                 '<Number>1</Number><Volume>2020</Volume></ComicInfo>')
            worker = SimpleNamespace(prepared=Mock(return_value=(path, {})), db=None,
                                     parent=Mock(return_value=None), m=SimpleNamespace(mylar=Mock(return_value={'phase': 'review'})))
            with patch('pack_recovery.catalog', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'Filename and metadata disagree'):
                    Packs.member(worker, {'phase': 'discovered', 'kind': 'issue', 'source': str(path),
                                          'catalog_attempted': True}, Path(directory))
            worker.m.mylar.assert_not_called()
            self.assertTrue(path.is_file())

    def test_publication_year_does_not_conflict_with_series_start_year(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Test Comic 001 (2017).cbz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Test Comic</Series>'
                                 '<Number>1</Number><Volume>2017</Volume><Year>2020</Year></ComicInfo>')
            self.assertEqual(evidence(path)['year'], '2017')

    def test_filename_publication_year_preserves_metadata_series_start(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Test Comic 052 (2026) (digital-mobile-Empire).cbz'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('ComicInfo.xml', '<ComicInfo><Series>Test Comic</Series>'
                                 '<Number>52</Number><Volume>2024</Volume><Year>2026</Year></ComicInfo>')
            self.assertEqual(evidence(path)['year'], '2024')


@unittest.skipUnless(TOOL, 'Set ARCHIVING_UTILS_BIN')
class PackTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache, self.library, self.state, self.completed = [self.root / n for n in ('cache', 'library', 'state', 'completed')]
        for p in (self.cache, self.library, self.state, self.completed):
            p.mkdir()
        self.folder = self.library / 'Test Comic (2017)'
        self.folder.mkdir()
        self.db = self.root / 'mylar.db'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.executescript('''CREATE TABLE comics(ComicID TEXT,ComicName TEXT,ComicYear TEXT,ComicLocation TEXT);
                CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT);
                CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Status TEXT,Issue_Number TEXT,IssueDate TEXT,Location TEXT,ReleaseComicName TEXT,Deleted INTEGER);
                INSERT INTO issues VALUES('100','10','Downloaded','1','2017-01-01','Test Comic 001 (2017).cbz');
                INSERT INTO annuals VALUES('200','10','Wanted','1','2017-05-01','','Test Comic Annual',0);''')
            db.execute('INSERT INTO comics VALUES(?,?,?,?)', ('10','Test Comic','2017',str(self.folder)))
        config = {'state': str(self.state), 'roots': [str(self.library)], 'converter': TOOL,
                  'mylar': {'config_dir': str(self.root)},
                  'maintenance': {'completed':str(self.completed), 'ddl_cache':str(self.cache),
                                  'mylar_ddl_cache':'/cache','auto_import':True,'pack_import':True}}
        self.worker = Normalizer(config, reader=Mock())
        self.worker.reader.call.return_value=[]
        self.m = Maintenance(self.worker)
        self.m.idle=Mock(return_value=True)
        self.m.import_submitted=False
        self.m.mylar=Mock(return_value={'phase':'review'})
        self.packs=Packs(self.m)
        self.pack=self.cache/'pack';self.pack.mkdir()
        self.record={'id':'a'*64,'ddl_id':'1','source':'/cache/pack','name':'Test pack'}
        self.archive(self.folder/'Test Comic 001 (2017).cbz', 3)

    def archive(self, path, pages=3, meta=None, extra=True):
        with zipfile.ZipFile(path,'w') as z:
            for n in range(pages):z.writestr('%03d.png'%n,PNG)
            if extra:z.writestr('notes.txt','preserve this sidecar')
            if meta:z.writestr('ComicInfo.xml',meta)
        return path

    def test_catalog_retry_survives_receipt_reload_and_obeys_backoff(self):
        self.archive(self.pack/'Missing Comic 001 (2017).cbz')
        receipt,value=self.packs.inventory(self.record);member=value['members'][0]
        self.m.mylar.return_value={'phase':'retry','retry_at':1300,'attempts':1}
        with patch('pack_recovery.time.time',return_value=1000):
            self.packs.member(member,receipt.parent)  # durable request intent
            self.packs.member(member,receipt.parent)
        self.assertEqual(self.m.mylar.call_count,1)
        member=json.loads(json.dumps(member))  # simulate reloaded worker receipt
        with patch('pack_recovery.time.time',return_value=1299):self.packs.member(member,receipt.parent)
        self.assertEqual(self.m.mylar.call_count,1)
        self.m.mylar.return_value={'phase':'review','reason':'No unique match'}
        with patch('pack_recovery.time.time',return_value=1300):self.packs.member(member,receipt.parent)
        self.assertEqual(self.m.mylar.call_count,2)
        with patch('pack_recovery.time.time',return_value=9000):self.packs.member(member,receipt.parent)
        self.assertEqual(self.m.mylar.call_count,2)
        self.assertTrue(Path(member['source']).is_file())

    def test_ordinal_member_reaches_exact_existing_owner_without_catalog_request(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('ALTER TABLE comics ADD COLUMN ComicVersion')
            db.execute("UPDATE comics SET ComicName='Grimm Tales of Terror',ComicYear='2015',ComicVersion='v2'")
            db.execute("UPDATE issues SET IssueDate='2015-10-01'")
        source = self.archive(self.pack/'Grimm Tales of Terror v2 001 (2015).cbz', meta=
            '<ComicInfo><Series>Grimm Tales of Terror</Series><Number>1</Number><Volume>2015</Volume></ComicInfo>')
        receipt, value = self.packs.inventory(self.record)
        self.packs.member(value['members'][0], receipt.parent)
        member = value['members'][0]
        self.assertEqual((member['phase'], member['issueid'], member['comicid']), ('confirmed', '100', '10'))
        self.assertTrue(source.is_file())
        self.m.mylar.assert_not_called()

    def test_mixed_pack_keeps_cover_separate_and_cleans_only_verified_sources(self):
        issue=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        cover=self.archive(self.pack/'Test Comic 001 (2017) (Variant Cover).cbz',1,
                           '<ComicInfo><Series>Test Comic</Series><Number>1</Number><Web>https://comicvine.gamespot.com/a/4000-100/</Web></ComicInfo>')
        (self.pack/'credits.txt').write_text('pack credit')
        receipt,value=self.packs.inventory(self.record)
        for m in value['members']:self.packs.member(m,receipt.parent)
        self.assertEqual(sorted(m['kind'] for m in value['members']),['issue','sidecar','supplement'])
        self.assertTrue(all(m['phase'] in ('confirmed','preserved') for m in value['members']))
        extra=next(self.library.glob('* - Extras/*.cbz'))
        with zipfile.ZipFile(extra) as z:
            text=z.read('ComicInfo.xml').decode()
            self.assertNotIn('<Web>',text)
            self.assertIn('Extras',text)
        for m in value['members']:self.packs.member(m,receipt.parent)
        self.assertEqual(len(list(self.library.glob('* - Extras/*.cbz'))),1)
        self.packs.cleanup(receipt,value)
        self.assertFalse(issue.exists());self.assertFalse(cover.exists())
        self.assertFalse(list(self.cache.glob('.mylar-pack-*/*.cbz')))
        self.assertTrue((receipt.parent/('sidecar-'+next(m['id'] for m in value['members'] if m['kind']=='sidecar'))).exists())
        self.m.mylar.assert_called_once()
        intent=json.loads(self.m.mylar.call_args.kwargs['report'])
        self.assertTrue(intent['cleanup_verified_at'])
        self.assertNotIn('cleaned_at',intent)

    def test_cleanup_report_failure_preserves_all_source_files(self):
        issue=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        receipt,value=self.packs.inventory(self.record)
        for member in value['members']:self.packs.member(member,receipt.parent)
        def rejected(command,**kwargs):
            self.assertTrue(issue.exists())
            self.assertTrue(json.loads(kwargs['report'])['cleanup_verified_at'])
            raise RuntimeError('Cleanup intent rejected')
        self.m.mylar.side_effect=rejected
        with self.assertRaisesRegex(RuntimeError,'intent rejected'):self.packs.cleanup(receipt,value)
        self.assertTrue(issue.exists())
        self.assertNotIn('cleaned_at',json.loads(receipt.read_text()))

    def test_resumed_cleanup_rejects_new_uninventoried_sources(self):
        issue=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        receipt,value=self.packs.inventory(self.record)
        for member in value['members']:self.packs.member(member,receipt.parent)
        value['cleanup_verified_at']=1
        extra=self.pack/'new.txt';extra.write_bytes(b'new delivery')
        with self.assertRaisesRegex(ValueError,'uninventoried'):self.packs.cleanup(receipt,value)
        self.assertTrue(issue.exists());self.assertTrue(extra.exists())
        self.m.mylar.assert_not_called()

    def test_annual_matches_parent_and_submits_once(self):
        annual=self.archive(self.pack/'Test Comic Annual 001 (2017) [__200__].cbz')
        self.assertEqual(match(annual,self.db),{'issueid':'200','comicid':'10'})
        receipt,value=self.packs.inventory(self.record)
        member=value['members'][0]
        self.packs.member(member,receipt.parent)
        self.assertEqual(member['phase'],'submitted')
        self.m.import_submitted=False
        self.packs.member(member,receipt.parent)
        self.m.mylar.assert_called_once()
        self.assertTrue(annual.exists())

    def test_cover_is_not_blanket_short_comic_rejection(self):
        path=self.pack/'Short Story 001 (2017).cbz'
        self.assertEqual(kind(path,{'page_count':1}),'issue')
        self.assertEqual(kind(path.with_name('Story 001 (2017) (Variant Cover).cbz'),{'page_count':32}),'issue')
        self.assertEqual(kind(path.with_name('Story 001 (2017) (Variant Cover).cbz'),{'page_count':1}),'supplement')

    def test_publication_year_alternate_scan_uses_verified_catalog_parent(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute("UPDATE issues SET IssueDate='2026-01-01'")
        source = self.archive(self.pack/'Test Comic 001 (2026).cbz', 4)
        receipt, value = self.packs.inventory(self.record)
        member = value['members'][0]
        self.packs.member(member, receipt.parent)
        self.assertEqual(member['phase'], 'preserved')
        self.assertEqual(member['kind'], 'supplement')
        self.assertEqual(member['comicid'], '10')
        self.assertTrue(Path(member['destination']).parent.name.endswith(' - Extras'))
        self.assertTrue(source.is_file())
        self.assertTrue((self.folder/'Test Comic 001 (2017).cbz').is_file())
        self.m.mylar.assert_not_called()

    def test_changed_destination_prevents_all_source_cleanup(self):
        source=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        receipt,value=self.packs.inventory(self.record)
        self.packs.member(value['members'][0],receipt.parent)
        Path(value['members'][0]['destination']).write_bytes(b'changed')
        with self.assertRaises(ValueError):self.packs.cleanup(receipt,value)
        self.assertTrue(source.exists())

    def test_conflicting_identity_and_unsafe_paths_are_retained(self):
        source=self.archive(self.pack/'Test Comic 001 (2017) [__100__].cbz',meta='<ComicInfo><Web>https://comicvine.gamespot.com/a/4000-200/</Web></ComicInfo>')
        with self.assertRaises(ValueError):evidence(source)
        with self.assertRaises(ValueError):self.packs.local('/cache/../outside')
        (self.pack/'linked.cbz').symlink_to(source)
        with self.assertRaises(ValueError):self.packs.inventory(self.record)

    def test_outer_pack_uses_bounded_extractor_and_preserves_source(self):
        source=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        outer=self.cache/'outer.zip'
        with zipfile.ZipFile(outer,'w') as z:z.write(source,source.name)
        record=dict(self.record,source='/cache/outer.zip')
        receipt,value=self.packs.inventory(record)
        self.packs.member(value['members'][0],receipt.parent)
        self.assertEqual(value['members'][0]['phase'],'confirmed')
        self.packs.cleanup(receipt,value)
        self.assertFalse(outer.exists())
        self.assertTrue(source.exists())  # Outside the owned extraction, not an incidental cleanup.

    def test_existing_extracted_copy_is_also_verified_before_cleanup(self):
        folder=self.cache/'outer';folder.mkdir()
        duplicate=self.archive(folder/'Test Comic 001 (2017).cbz')
        outer=self.cache/'outer.zip'
        with zipfile.ZipFile(outer,'w') as z:z.write(duplicate,duplicate.name)
        receipt,value=self.packs.inventory(dict(self.record,source='/cache/outer.zip'))
        self.assertEqual(len(value['members']),2)
        self.assertEqual(len({m['id'] for m in value['members']}),2)
        for m in value['members']:self.packs.member(m,receipt.parent)
        self.packs.cleanup(receipt,value)
        self.assertFalse(outer.exists());self.assertFalse(duplicate.exists())

    def test_landscape_edition_conflict_is_retained(self):
        import struct
        source=self.pack/'Test Comic 001 (2017).cbz'
        with zipfile.ZipFile(source,'w') as z:
            for n in range(4):z.writestr('%03d.png'%n,PNG[:16]+struct.pack('>II',1200,800)+PNG[24:])
        # The header check is intentionally separate from archive decoding.
        from edition_evidence import landscape
        self.assertTrue(landscape(source))
        with patch('pack_recovery.Packs.prepared',return_value=(source,{'page_count':4})):
            member={'id':'c'*64,'phase':'discovered','source':str(source),'kind':'issue'}
            self.packs.member(member,self.state)
        self.assertEqual(member['phase'],'review')
        self.assertIn('Edition',member['reason'])
        self.assertTrue(source.exists())

    def test_restart_rebuilds_owned_extraction_from_verified_source(self):
        source=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        outer=self.cache/'restart.zip'
        with zipfile.ZipFile(outer,'w') as z:z.write(source,source.name)
        record=dict(self.record,source='/cache/restart.zip')
        import pack_recovery
        real_save=pack_recovery.save
        def interrupted(path,value):
            if path.name=='receipt.json':raise RuntimeError('crash after extraction')
            return real_save(path,value)
        with patch.object(pack_recovery,'save',side_effect=interrupted):
            with self.assertRaises(RuntimeError):self.packs.inventory(record)
        receipt,value=self.packs.inventory(record)
        self.assertTrue(receipt.exists());self.assertEqual(len(value['members']),1)

    def test_bad_outer_pack_does_not_block_later_pack(self):
        (self.cache/'bad.zip').write_bytes(b'not an archive')
        good=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        bad=dict(self.record,id='b'*64,source='/cache/bad.zip')
        work={'enabled':True,'packs':[bad,self.record]}
        self.m.mylar.side_effect=lambda cmd,**kw:work if cmd=='packWork' else {'phase':'confirmed'}
        self.packs.cycle()
        self.assertTrue((self.packs.root/self.record['id']/'receipt.json').exists())
        self.assertFalse(good.exists())

    def test_loose_cover_does_not_hide_nested_comic(self):
        comic=self.archive(self.pack/'Test Comic 001 (2017).cbz')
        outer=self.cache/'Test Comic 001 (2017).zip'
        with zipfile.ZipFile(outer,'w') as z:
            z.write(comic,comic.name);z.writestr('cover.png',PNG)
        receipt,value=self.packs.inventory(dict(self.record,source='/cache/'+outer.name))
        self.assertEqual(len(value['members']),2)
        for member in value['members']:self.packs.member(member,receipt.parent)
        self.assertEqual(sum(m['phase']=='confirmed' for m in value['members']),1)
        self.assertEqual(next(m for m in value['members'] if m['name']=='cover.png')['phase'],'review')
        self.m.mylar.assert_not_called()
        self.packs.cleanup(receipt,value)
        self.assertTrue(outer.exists())

    def test_single_comic_pack_does_not_extract_pages_as_members(self):
        source=self.archive(self.cache/'Test Comic 001 (2017).cbz')
        receipt,value=self.packs.inventory(dict(self.record,source='/cache/'+source.name))
        self.assertEqual(len(value['members']),1)
        self.packs.member(value['members'][0],receipt.parent)
        self.assertEqual(value['members'][0]['phase'],'confirmed')


class CleanedPackAuthorityTest(AuthorityFixture, unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        from normalize import digest
        state=self.root/'worker-state'
        state.mkdir()
        maintenance=state/'maintenance'
        maintenance.mkdir()
        cache=self.root/'shared-cache'
        cache.mkdir()
        worker=SimpleNamespace(state=state,roots=[self.library],config={
            'writer_state':str(self.writer.root),
            'publication_roots':[{'native':str(self.native_root),'worker':str(self.library)}],
            'mylar':{'config_dir':str(self.config)}})
        self.m=SimpleNamespace(worker=worker,state=maintenance,roots=[cache],
            settings={'ddl_cache':str(cache),'mylar_ddl_cache':'/native-cache'},mylar=Mock())
        self.record=dict(id='c'*64,ddl_id='1',source='/native-cache/removed.zip',phase='confirmed',
            inventory_complete=True,cleanup_complete=True,members=[dict(id='d'*64,kind='issue',phase='confirmed',
                issueid='123',comicid='456',destination=str(self.native_root/self.source.name),
                destination_sha256=digest(self.source),signature=[0,0,0,0,0])])
        from native_handoff import report
        self.packs=SimpleNamespace(m=self.m,report=lambda value:report(self.m,value))

    def refresh(self):
        from publication_guard import scope
        with self.writer.hold(),scope(self.m.worker,self.writer) as authority:
            authority.tool_root=self.tool
            return Packs.refresh_cleaned(self.packs,self.record)

    def test_cleaned_native_paths_prepare_report_only_with_actual_current_owner(self):
        before=json.dumps(self.record,sort_keys=True)
        self.assertIsNone(self.refresh())
        job=json.loads(next((self.m.state/'native-handoffs').glob('*.json')).read_text())
        self.assertEqual(job['phase'],'prepared')
        self.assertEqual(job['guards'][0]['source'],str(self.source))
        packet=json.loads(job['arguments']['report'])
        self.assertEqual(packet['members'][0]['destination'],self.record['members'][0]['destination'])
        self.assertEqual(json.dumps(self.record,sort_keys=True),before)
        self.m.mylar.assert_not_called()

    def test_cleaned_report_holds_wrong_owner_changed_archive_and_unmapped_path(self):
        from publication_guard import Unavailable
        original=self.record['members'][0].copy()
        for changes in ({'issueid':'999','comicid':'888'}, {'destination':'/foreign/correct.cbz'},
                        {'destination_sha256':'0'*64}):
            self.record['members'][0]=dict(original,**changes)
            with self.subTest(changes=changes),self.assertRaises((Unavailable,ValueError)):
                self.refresh()
        self.assertFalse((self.m.state/'native-handoffs').exists())
        self.m.mylar.assert_not_called()


if __name__=='__main__':unittest.main()

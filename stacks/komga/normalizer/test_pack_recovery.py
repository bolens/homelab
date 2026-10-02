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
from pack_recovery import Packs, evidence, kind
from import_match import match
from test_normalize import PNG, TOOL


class PackEvidenceTest(unittest.TestCase):
    def test_cleaned_pack_revalidation_preserves_history_without_sources(self):
        record={'id':'a'*64,'source':'/cache/removed.zip','phase':'confirmed',
                'cleanup_complete':True,'inventory_complete':True,
                'members':[{'id':'b'*64,'kind':'issue','phase':'confirmed',
                            'destination':'/library/Test.cbz','destination_sha256':'c'*64}]}
        api=Mock(side_effect=lambda command,**kwargs:{'enabled':True,'packs':[record]}
                 if command=='packWork' else {'phase':'confirmed'})
        packs=SimpleNamespace(m=SimpleNamespace(settings={'pack_import':True},mylar=api),
                              local=lambda value:Path(value),inventory=Mock(),changed=False)
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
        packs=SimpleNamespace(m=SimpleNamespace(settings={'pack_import':True},mylar=calls),
                              local=lambda value:Path(value),inventory=Mock(),changed=False)
        Packs.cycle(packs)
        self.assertEqual(calls.call_count,2)
        self.assertEqual(record['members'][0]['phase'],'confirmed')
        packs.inventory.assert_not_called()

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


if __name__=='__main__':unittest.main()

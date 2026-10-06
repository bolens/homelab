"""Native uncertainty is reconciled once and reader progress gates cleanup."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from naming_worker import Naming, token
from publication_guard import Unavailable
from normalize import digest, save


class NamingWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'Old 001 (2020).cbz';self.source.write_bytes(b'original')
        self.target=self.root/'Old.001.(2020).cbz'
        self.worker=SimpleNamespace(config={'mylar':{'config_dir':str(self.root)},'writer_state':str(self.root/'writer')},
                                     state=self.root,roots=[self.root],reader=Mock())
        from media_writer import Writer
        Writer(self.root/'writer',create=True)
        self.naming=Naming(self.worker)
        self.request=dict(version=1,source=str(self.source),target=self.target.name,sha256=digest(self.source),issueid='1',comicid='2')
        self.folder=self.naming.root/token(self.request);self.folder.mkdir(mode=0o700)
        self.book=dict(id='new',url=str(self.target),libraryId='library',seriesId='series',deleted=False,fileHash='hash',
                       media={'status':'READY','pagesCount':20},readProgress={'page':7,'completed':False})
        self.job=dict(source=str(self.source),phase='prepared',request=self.request,key=token(self.request),reader=dict(libraryid='library',hash='hash',pages=20,progress={'page':7,'completed':False}))
        save(self.folder/'receipt.json',self.job)
        (self.folder/'original.cbz').write_bytes(b'original');(self.folder/'restore.cbz').write_bytes(b'original')
        self.naming.publication=Mock(return_value=None)
        self.naming.scan=Mock(side_effect=lambda folder,job:self.worker.reader.call('/api/v1/libraries/'+job['reader']['libraryid']+'/scan', {}))
        self.naming.api=Mock()
        self.naming.catalog=Mock(return_value={'issues:1':dict(issueid='1',comicid='2',source=str(self.target))})

    def publish(self):self.source.rename(self.target)

    def test_uncertain_native_mutation_is_never_replayed(self):
        self.naming.api.side_effect=TimeoutError()
        self.assertEqual(self.naming.advance(self.folder)['phase'],'native-uncertain')
        self.naming.api.side_effect=None;self.naming.api.return_value={'phase':'absent','version':1,'key':self.job['key']}
        self.assertEqual(self.naming.advance(self.folder)['phase'],'review')
        self.assertEqual([c.args[0] for c in self.naming.api.call_args_list],['renameLibraryFile','releaseNamingStatus'])
        self.assertTrue((self.folder/'original.cbz').exists())

    def rejected_fixture(self):
        import shutil,zipfile
        self.naming.rules['enabled']=True
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('page.jpg',b'page')
        self.request['sha256']=digest(self.source)
        parent=token(self.request);folder=self.naming.root/parent;folder.mkdir(mode=0o700)
        reader=dict(id='old',hash='hash',pages=1,seriesid='series',libraryid='library',progress={'page':1})
        old=dict(self.job,phase='review',key=parent,request=self.request,reader=reader)
        save(folder/'receipt.json',old)
        for name in ('original.cbz','restore.cbz'):shutil.copy2(self.source,folder/name)
        proposal=dict(version=1,source=str(self.source),sha256=digest(self.source),issueid='1',comicid='2',
                      series='Old',number='1',year='2020',type='Print',volume=None,group=None)
        self.naming.reader_proof=Mock(return_value=reader)
        self.naming.api.side_effect=lambda command,**values: {'phase':'rejected'} if command=='releaseNamingStatus' else proposal
        return parent,folder,old

    def test_explicit_recovery_prepares_new_copies_and_keeps_parent_review(self):
        from media_writer import Writer
        parent,folder,old=self.rejected_fixture();Writer(self.root/'writer',create=True)
        before=(folder/'receipt.json').read_bytes()
        with patch('naming_worker.all_books',return_value=[]):
            entry=self.naming.recovery_entry(parent);child=self.naming.prepare(entry)
        self.assertEqual(entry['request']['version'],2);self.assertEqual(entry['request']['retry_of'],parent)
        self.assertNotEqual(child,folder)
        self.assertEqual((folder/'receipt.json').read_bytes(),before)
        self.assertEqual(digest(child/'restore.cbz'),old['request']['sha256'])
        self.assertFalse(self.target.exists());self.assertTrue(self.source.exists())

    def test_recovery_rejects_changed_or_linked_retained_copies(self):
        parent,folder,_=self.rejected_fixture()
        (folder/'restore.cbz').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.naming.recovery_entry(parent)
        (folder/'restore.cbz').unlink();(folder/'restore.cbz').symlink_to(self.source)
        with self.assertRaises(ValueError):self.naming.recovery_entry(parent)
        self.assertFalse(self.target.exists())

    def test_combined_linked_holds_require_explicit_detached_verified_copies(self):
        import os,shutil
        parent,folder,_=self.rejected_fixture()
        joint=self.root/'combined';joint.mkdir(mode=0o700)
        detached=self.root/'detached';detached.mkdir(mode=0o700)
        for name in ('original.cbz','restore.cbz'):
            os.link(folder/name,joint/name);shutil.copy2(joint/name,detached/name)
        with self.assertRaises(ValueError):self.naming.recovery_entry(parent)
        preservation=dict(original=str(detached/'original.cbz'),restore=str(detached/'restore.cbz'))
        with patch('naming_worker.all_books',return_value=[]):entry=self.naming.recovery_entry(parent,preservation)
        self.assertEqual(entry['preservation'],preservation)
        self.assertEqual((folder/'original.cbz').stat().st_nlink,2)
        self.assertEqual((detached/'original.cbz').stat().st_nlink,1)

    def test_recovery_rejects_preservation_traversal_outside_state(self):
        import shutil
        parent,folder,_=self.rejected_fixture()
        with tempfile.TemporaryDirectory(dir=self.root.parent) as outside:
            for name in ('original.cbz','restore.cbz'):shutil.copy2(folder/name,Path(outside)/name)
            traversal=self.root/'..'/Path(outside).name
            copies=dict(original=str(traversal/'original.cbz'),restore=str(traversal/'restore.cbz'))
            with self.assertRaises(ValueError):self.naming.recovery_entry(parent,copies)

    def test_recovery_rejects_absent_native_parent_or_reader_progress_loss(self):
        parent,_,_=self.rejected_fixture()
        self.naming.api.side_effect=lambda command,**values:{'phase':'absent'}
        with self.assertRaises(ValueError):self.naming.recovery_entry(parent)
        parent,_,_=self.rejected_fixture_again(parent)

    def rejected_fixture_again(self,parent):
        # Reuse the held fixture to check a fresh reader proof without replacing receipts.
        folder=self.naming.root/parent;old=json.loads((folder/'receipt.json').read_text())
        proposal=dict(version=1,source=str(self.source),sha256=digest(self.source),issueid='1',comicid='2',
                      series='Old',number='1',year='2020',type='Print',volume=None,group=None)
        self.naming.api.side_effect=lambda command,**values:{'phase':'rejected'} if command=='releaseNamingStatus' else proposal
        self.naming.reader_proof.return_value=dict(old['reader'],progress={'page':0})
        with patch('naming_worker.all_books',return_value=[]):
            with self.assertRaises(ValueError):self.naming.recovery_entry(parent)
        return parent,folder,old

    def test_committed_journal_reconciles_and_reader_proof_removes_only_copies(self):
        self.publish();self.job['phase']='native-uncertain';save(self.folder/'receipt.json',self.job)
        self.naming.api.return_value={'phase':'committed','version':1,'key':self.job['key']}
        with patch('naming_worker.all_books',return_value=[self.book]):
            result=self.naming.advance(self.folder)
        self.assertEqual(result['phase'],'done');self.assertEqual(self.target.read_bytes(),b'original')
        self.assertTrue((self.folder/'receipt.json').exists());self.assertFalse((self.folder/'original.cbz').exists())
        self.assertFalse((self.folder/'restore.cbz').exists())

    def test_lost_progress_retains_originals_and_pending_receipt(self):
        self.publish();self.job['phase']='reader-pending';save(self.folder/'receipt.json',self.job)
        self.book['readProgress']['page']=0
        with patch('naming_worker.all_books',return_value=[self.book]):
            with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.assertTrue((self.folder/'original.cbz').exists())
        self.assertEqual(json.loads((self.folder/'receipt.json').read_text())['phase'],'reader-pending')

    def test_stale_or_historical_duplicate_hash_prevents_reader_move(self):
        book=dict(self.book,url=str(self.source))
        with patch('naming_worker.reader_hash',return_value='hash'):
            self.assertEqual(self.naming.reader_proof(self.source,[book])['hash'],'hash')
            with self.assertRaises(ValueError):self.naming.reader_proof(self.source,[book,dict(book,id='old',deleted=True)])
            with self.assertRaises(ValueError):self.naming.reader_proof(self.source,[dict(book,fileHash='stale')])

    def test_baseline_and_bounded_pending_do_not_lose_later_entries(self):
        (self.folder/'receipt.json').unlink()
        rows={str(i):dict(source=str(self.root/(str(i)+'.cbz')),issueid=str(i),comicid='2') for i in range(3)}
        self.naming.catalog.return_value={};self.naming.tick()
        self.naming.catalog.return_value=rows
        self.naming.rules['batch_size']=1
        self.naming.api.side_effect=lambda command,**kwargs:dict(series='Old',number='1',year='2020',type='Print',volume=None,group=None,
                     source=kwargs['source'],issueid=Path(kwargs['source']).stem,comicid='2',version=1,sha256='a'*64)
        self.naming.reader_proof=Mock(return_value={});self.naming.prepare=Mock(return_value=self.folder)
        self.naming.advance=Mock(return_value={'phase':'done'})
        with patch('naming_worker.all_books',return_value=[]):self.naming.tick()
        self.assertEqual(len(self.naming.state['known']),1)
        with patch('naming_worker.all_books',return_value=[]):self.naming.tick()
        self.assertEqual(len(self.naming.state['known']),2)

    def test_ambiguous_arrival_does_not_starve_later_verified_publication(self):
        (self.folder/'receipt.json').unlink()
        self.naming.state = dict(version=1, known={})
        rows={str(i):dict(source=str(self.root/(str(i)+'.cbz')),issueid=str(i),comicid='2') for i in range(2)}
        self.naming.catalog.return_value=rows
        self.naming.rules['batch_size']=1
        def proposal(command, **kwargs):
            if Path(kwargs['source']).stem == '0':raise ValueError('Ambiguous identity')
            return dict(series='Old',number='1',year='2020',type='Print',volume=None,group=None,
                        source=kwargs['source'],issueid='1',comicid='2',version=1,sha256='a'*64)
        self.naming.api.side_effect=proposal
        self.naming.reader_proof=Mock(return_value={});self.naming.prepare=Mock(return_value=self.folder)
        self.naming.advance=Mock(return_value={'phase':'done'})
        with patch('naming_worker.all_books',return_value=[]):self.naming.tick()
        self.assertEqual(self.naming.state['known'],{'1':rows['1']})
        self.assertEqual(self.naming.state['waiting'][rows['0']['source']]['reason'],'Ambiguous identity')
        self.assertNotIn('0',self.naming.state['known'])
        self.naming.prepare.assert_called_once()

    def test_interrupted_copy_does_not_publish_an_incomplete_preparation(self):
        import zipfile
        from media_writer import Writer
        with zipfile.ZipFile(self.source,'w') as archive:
            archive.writestr('page.jpg',b'page fixture')
            archive.writestr('ComicInfo.xml','<ComicInfo/>')
        self.request['sha256']=digest(self.source)
        proposal=dict(version=1,source=str(self.source),sha256=digest(self.source),issueid='1',comicid='2',
                      series='Old',number='1',year='2020',type='Print',volume=None,group=None)
        self.naming.api.return_value=proposal;self.naming.reader_proof=Mock(return_value=self.job['reader'])
        Writer(self.root/'writer',create=True)
        entry=dict(source=str(self.source),proposal=proposal,request=self.request,reader=self.job['reader'])
        with patch('naming_worker.all_books',return_value=[]), patch('naming_worker.shutil.copy2',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.naming.prepare(entry)
        self.assertFalse((self.naming.root/token(self.request)).exists())
        with patch('naming_worker.all_books',return_value=[]):folder=self.naming.prepare(entry)
        self.assertEqual(json.loads((folder/'receipt.json').read_text())['phase'],'prepared')
        self.assertEqual(digest(folder/'restore.cbz'),digest(self.source))
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())

    def test_prepare_verifies_isolated_archive_copies_without_native_mutation(self):
        import zipfile
        from media_writer import Writer
        with zipfile.ZipFile(self.source,'w') as archive:
            archive.writestr('page.jpg',b'page fixture')
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Old</Series><Number>1</Number></ComicInfo>')
        self.request['sha256']=digest(self.source)
        proposal=dict(version=1,source=str(self.source),sha256=digest(self.source),issueid='1',comicid='2',
                      series='Old',number='1',year='2020',type='Print',volume=None,group=None)
        self.naming.api.return_value=proposal;self.naming.reader_proof=Mock(return_value=self.job['reader'])
        Writer(self.root/'writer',create=True)
        entry=dict(source=str(self.source),proposal=proposal,request=self.request,reader=self.job['reader'])
        with patch('naming_worker.all_books',return_value=[]):folder=self.naming.prepare(entry)
        for name in ('original.cbz','restore.cbz'):self.assertEqual(digest(folder/name),digest(self.source))
        self.assertEqual(json.loads((folder/'receipt.json').read_text())['phase'],'prepared')
        self.assertTrue(self.source.exists());self.assertFalse(self.target.exists())
        self.assertEqual([call.args[0] for call in self.naming.api.call_args_list],['getReleaseNaming'])

    def test_bulk_batches_one_scan_and_dispatches_after_later_preflight_failure(self):
        (self.folder/'receipt.json').unlink()
        entries=[dict(source=str(self.source),phase='planned',request=dict(self.request,issueid=str(n))) for n in (1,2)]
        self.naming.prepare=Mock(side_effect=[self.folder,ValueError('stale source')])
        self.naming.advance=Mock(return_value=dict(self.job,phase='reader-pending'))
        with self.assertRaises(ValueError):self.naming.apply(dict(version=1,entries=entries),2)
        self.worker.reader.call.assert_called_once_with('/api/v1/libraries/library/scan',{})
        self.assertEqual(self.naming.advance.call_count,1)

    def test_bulk_pending_batch_prevents_more_mutations_and_terminal_entries_skip(self):
        self.naming.advance=Mock(return_value=dict(self.job,phase='reader-pending'))
        self.naming.prepare=Mock()
        with patch('naming_worker.all_books',return_value=[]):
            self.assertEqual(self.naming.apply(dict(version=1,entries=[]))[0]['phase'],'reader-pending')
        self.naming.prepare.assert_not_called()
        job=dict(self.job,phase='done');save(self.folder/'receipt.json',job)
        destination=self.naming.root/token(self.request);destination.mkdir(mode=0o700,exist_ok=True);save(destination/'receipt.json',job)
        self.assertEqual(self.naming.apply(dict(version=1,entries=[dict(phase='planned',request=self.request)])),[])
        self.naming.prepare.assert_not_called()

    def test_stale_manifest_does_not_create_preservation_or_native_mutation(self):
        import shutil
        shutil.rmtree(self.folder)
        entry=dict(source=str(self.source),request=self.request,proposal={'old':'proposal'},reader={})
        self.naming.api.return_value=dict(version=1,source=str(self.source),sha256=digest(self.source),issueid='1',comicid='2',
                                          series='Changed',number='1',year='2020',type='Print',volume=None,group=None)
        with self.assertRaises(ValueError):self.naming.prepare(entry)
        self.assertFalse((self.naming.root/token(self.request)).exists())
        self.assertEqual([call.args[0] for call in self.naming.api.call_args_list],['getReleaseNaming'])

    def test_completed_release_manifest_is_idempotent(self):
        self.source.rename(self.target)
        self.naming.catalog.return_value={'issues:1':dict(source=str(self.target),issueid='1',comicid='2')}
        self.naming.api.return_value=dict(version=1,source=str(self.target),sha256=digest(self.target),issueid='1',comicid='2',
                                          series='Old',number='1',year='2020',type='Print',volume=None,group=None)
        with patch('naming_worker.all_books',return_value=[]):result=self.naming.plan()
        self.assertEqual(result['entries'][0]['phase'],'unchanged')

    def prepare_fixture(self):
        import zipfile
        with zipfile.ZipFile(self.source, 'w') as archive:
            archive.writestr('page.jpg', b'page')
        self.request['sha256'] = digest(self.source)
        proposal = dict(version=1, source=str(self.source), sha256=digest(self.source), issueid='1', comicid='2',
                        series='Old', number='1', year='2020', type='Print', volume=None, group=None)
        self.naming.api.return_value = proposal
        self.naming.reader_proof = Mock(return_value=self.job['reader'])
        return dict(source=str(self.source), request=self.request, proposal=proposal, reader=self.job['reader'])

    def test_wrong_current_owner_holds_before_any_preservation(self):
        entry = self.prepare_fixture()
        self.naming.publication.side_effect = ValueError('Rejected publication owner')
        with patch('naming_worker.all_books', return_value=[]):
            with self.assertRaises(ValueError):self.naming.prepare(entry)
        self.assertFalse((self.naming.root/token(self.request)).exists())
        self.assertEqual(list(self.naming.root.glob('*.preparing-*')), [])
        self.assertTrue(self.source.exists())

    def test_authority_drift_during_copy_keeps_source_and_incomplete_evidence(self):
        entry = self.prepare_fixture()
        before = {'census':'original'}
        self.naming.publication.side_effect = [before, before, {'census':'changed'}]
        with patch('naming_worker.all_books', return_value=[]):
            with self.assertRaises(ValueError):self.naming.prepare(entry)
        self.assertFalse((self.naming.root/token(self.request)).exists())
        self.assertTrue(self.source.exists())
        copies = list(self.naming.root.glob('*.preparing-*'))
        self.assertEqual(len(copies), 1)
        self.assertEqual(digest(copies[0]/'restore.cbz'), digest(self.source))

    def test_prepared_ownership_drift_never_submits_native_mutation(self):
        self.job['publication'] = {'census':'old'}
        save(self.folder/'receipt.json', self.job)
        self.naming.publication.return_value = {'census':'new'}
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.api.assert_not_called()
        self.assertEqual(json.loads((self.folder/'receipt.json').read_text())['phase'], 'prepared')

    def test_matching_bytes_cannot_replace_preservation_identity(self):
        self.job['preservation_facts'] = self.naming.copies(self.folder, self.request)
        save(self.folder/'receipt.json', self.job)
        kept = self.folder/'restore.cbz'
        kept.rename(self.folder/'foreign-before.cbz')
        kept.write_bytes(b'original')
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.api.assert_not_called()
        self.assertTrue((self.folder/'original.cbz').exists())

    def test_changed_or_linked_copy_blocks_reader_completion(self):
        self.publish();self.job['phase'] = 'reader-pending';save(self.folder/'receipt.json', self.job)
        kept = self.folder/'restore.cbz';kept.unlink();kept.symlink_to(self.target)
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.assertTrue(kept.is_symlink());self.assertTrue((self.folder/'original.cbz').exists())
        self.assertEqual(self.target.read_bytes(), b'original')

    def test_changed_catalog_before_cleanup_retains_both_copies(self):
        self.publish();self.job['phase'] = 'reader-pending';save(self.folder/'receipt.json', self.job)
        self.naming.publication.side_effect = [{'census':'old'}, {'census':'changed'}]
        with patch('naming_worker.all_books', return_value=[self.book]):
            with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.assertTrue((self.folder/'restore.cbz').exists());self.assertTrue((self.folder/'original.cbz').exists())
        self.assertEqual(json.loads((self.folder/'receipt.json').read_text())['phase'], 'reader-pending')

    def test_reader_library_or_duplicate_hash_blocks_cleanup(self):
        self.publish();self.job['phase'] = 'reader-pending';save(self.folder/'receipt.json', self.job)
        for books in ([dict(self.book, libraryId='foreign')], [self.book, dict(self.book,id='duplicate',deleted=True)]):
            with patch('naming_worker.all_books', return_value=books):
                with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.assertTrue((self.folder/'restore.cbz').exists())

    def test_unsafe_receipt_target_is_rejected_before_native_or_reader_calls(self):
        self.job['request']['target'] = '../foreign.cbz'
        self.job['key'] = token(self.job['request']);save(self.folder/'receipt.json', self.job)
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.api.assert_not_called();self.worker.reader.call.assert_not_called()

    def test_linked_receipt_and_boolean_protocol_never_recover(self):
        receipt = self.folder/'receipt.json';receipt.rename(self.folder/'saved.json');receipt.symlink_to(self.folder/'saved.json')
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        receipt.unlink();self.job['request']['version'] = True;self.job['key'] = token(self.job['request']);save(receipt,self.job)
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.api.assert_not_called()

    def test_interrupted_preparation_folders_are_never_removed_by_other_completion(self):
        self.publish();self.job['phase'] = 'reader-pending';save(self.folder/'receipt.json', self.job)
        orphan = self.naming.root/('.'+self.job['key']+'.preparing-foreign');orphan.mkdir(mode=0o700)
        (orphan/'original.cbz').write_bytes(b'foreign evidence')
        with patch('naming_worker.all_books', return_value=[self.book]):
            self.assertEqual(self.naming.advance(self.folder)['phase'], 'done')
        self.assertTrue((orphan/'original.cbz').exists())

    def test_scan_uses_exact_catalog_destination_in_durable_handoff(self):
        from contextlib import nullcontext
        import sys
        self.publish();self.job['phase'] = 'reader-pending'
        self.naming.authority = Mock(return_value=nullcontext())
        queue = Mock(return_value=None)
        with patch.dict(sys.modules, {'reader_handoff':SimpleNamespace(queue=queue)}):
            self.assertIsNone(Naming.scan(self.naming,self.folder,self.job))
        queue.assert_called_once_with(self.worker, 'library_scan', [dict(source=str(self.target), target=str(self.target),
            match={'issueid':'1','comicid':'2'})], folder=self.target.parent)
        self.assertNotIn('scan_at', self.job)
        self.worker.reader.call.assert_not_called()

    def test_reader_calls_are_refused_under_writer_before_receipt_transition(self):
        from media_writer import Writer
        with Writer(self.root/'writer').hold():
            with self.assertRaises(Unavailable):self.naming.advance(self.folder)
        self.assertEqual(json.loads((self.folder/'receipt.json').read_text())['phase'],'prepared')
        self.naming.api.assert_not_called();self.worker.reader.call.assert_not_called()

    def test_publication_requires_exact_target_owner_before_confirmation(self):
        from contextlib import nullcontext
        authority = Mock();authority.target_match.return_value = {'issueid':'9','comicid':'2'}
        self.naming.authority = Mock(return_value=nullcontext(authority))
        with self.assertRaises(ValueError):Naming.publication(self.naming,self.source,self.request)
        authority.confirmation_check.assert_not_called()
        authority.target_match.return_value = {'issueid':'1','comicid':'2'}
        expected = {'current':'complete-census-and-source'};authority.confirmation_check.return_value = expected
        self.assertEqual(Naming.publication(self.naming,self.source,self.request), expected)
        authority.confirmation_check.assert_called_once_with(self.source,self.source,{'issueid':'1','comicid':'2'})

    def test_catalog_maps_native_paths_before_source_admission(self):
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(self.root/'mylar.db')) as db:
            db.executescript("CREATE TABLE comics(ComicID TEXT,ComicLocation TEXT);"
                             "CREATE TABLE issues(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT);"
                             "CREATE TABLE annuals(IssueID TEXT,ComicID TEXT,Location TEXT,Status TEXT,Deleted INTEGER);")
            db.execute('INSERT INTO comics VALUES (?,?)',('2','/native/comics'))
            db.execute('INSERT INTO issues VALUES (?,?,?,?)',('1','2',self.source.name,'Downloaded'))
            db.commit()
        authority = Mock();authority.mapped.return_value = self.source
        result = self.naming.catalog_rows(authority)
        self.assertEqual(result, {'issues:1':dict(issueid='1',comicid='2',source=str(self.source))})
        authority.mapped.assert_called_once_with('/native/comics/'+self.source.name)

    def test_reader_catalog_bounds_and_false_protocol_do_not_truncate_proof(self):
        from naming_worker import all_books
        self.worker.reader.call.return_value = dict(content=[],last='false')
        with self.assertRaises(ValueError):all_books(self.worker.reader)
        self.worker.reader.call.return_value = dict(content=[{}]*501,last=True)
        with self.assertRaises(ValueError):all_books(self.worker.reader)

    def test_foreign_native_status_keeps_uncertain_attempt_and_originals(self):
        self.job['phase'] = 'native-uncertain';save(self.folder/'receipt.json',self.job)
        self.naming.api.return_value = dict(version=1,key='f'*64,phase='committed')
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.assertEqual(json.loads((self.folder/'receipt.json').read_text())['phase'],'native-uncertain')
        self.assertTrue((self.folder/'original.cbz').exists())

    def test_replacing_prepared_proof_without_its_original_binding_is_held(self):
        self.job.update(publication={'census':'old'}, preservation_facts=self.naming.copies(self.folder,self.request))
        self.job['preparation_binding'] = self.naming.preparation_binding(self.job)
        self.job['publication'] = {'census':'new'}
        save(self.folder/'receipt.json',self.job)
        self.naming.publication.return_value = {'census':'new'}
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.publication.assert_not_called();self.naming.api.assert_not_called()
        self.assertTrue((self.folder/'restore.cbz').exists())

    def test_legacy_publication_fields_without_preparation_binding_remain_held(self):
        self.job['publication'] = {'census':'old'};save(self.folder/'receipt.json',self.job)
        with self.assertRaises(ValueError):self.naming.advance(self.folder)
        self.naming.api.assert_not_called()


if __name__ == '__main__':unittest.main()

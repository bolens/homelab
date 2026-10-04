"""Native uncertainty is reconciled once and reader progress gates cleanup."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from naming_worker import Naming, token
from normalize import digest, save


class NamingWorkerTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'Old 001 (2020).cbz';self.source.write_bytes(b'original')
        self.target=self.root/'Old.001.(2020).cbz'
        self.worker=SimpleNamespace(config={'mylar':{'config_dir':str(self.root)},'writer_state':str(self.root/'writer')},
                                     state=self.root,roots=[self.root],reader=Mock())
        self.naming=Naming(self.worker);self.folder=self.naming.root/'job';self.folder.mkdir()
        self.request=dict(version=1,source=str(self.source),target=self.target.name,sha256=digest(self.source),issueid='1',comicid='2')
        self.book=dict(id='new',url=str(self.target),libraryId='library',seriesId='series',deleted=False,fileHash='hash',
                       media={'status':'READY','pagesCount':20},readProgress={'page':7,'completed':False})
        self.job=dict(source=str(self.source),phase='prepared',request=self.request,key=token(self.request),reader=dict(libraryid='library',hash='hash',pages=20,progress={'page':7,'completed':False}))
        save(self.folder/'receipt.json',self.job)
        (self.folder/'original.cbz').write_bytes(b'original');(self.folder/'restore.cbz').write_bytes(b'original')
        self.naming.api=Mock()
        self.naming.catalog=Mock(return_value={'issues:1':dict(issueid='1',comicid='2',source=str(self.target))})

    def publish(self):self.source.rename(self.target)

    def test_uncertain_native_mutation_is_never_replayed(self):
        self.naming.api.side_effect=TimeoutError()
        self.assertEqual(self.naming.advance(self.folder)['phase'],'native-uncertain')
        self.naming.api.side_effect=None;self.naming.api.return_value={'phase':'absent'}
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
        self.naming.api.return_value={'phase':'committed'}
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
        destination=self.naming.root/token(self.request);destination.mkdir();save(destination/'receipt.json',job)
        self.assertEqual(self.naming.apply(dict(version=1,entries=[dict(phase='planned',request=self.request)])),[])
        self.naming.prepare.assert_not_called()

    def test_stale_manifest_does_not_create_preservation_or_native_mutation(self):
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


if __name__ == '__main__':unittest.main()

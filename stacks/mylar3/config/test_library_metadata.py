"""Incremental discovery and durable repair queue fixtures."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
import zipfile
import library_metadata as library
from workflow_store import Store
from test_metadata_repair import fixture,NESTED
class MaintenanceTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'issue.cbz';self.now=1000
        with zipfile.ZipFile(self.source,'w') as z:z.writestr('page.jpg',b'page')
        self.store=Store(self.root,clock=lambda:self.now)
        self.next=Mock(return_value=('i:1:2',str(self.source)))
        self.catalog=Mock(return_value=dict(issueid='1',comicid='2'))
        self.repair=Mock(return_value='updated');self.recover=Mock(return_value=None)
        self.worker=library.Maintenance(self.store,self.next,self.catalog,self.repair,self.recover,clock=lambda:self.now)
    def test_missing_queued_once_and_cached(self):
        self.worker.tick(True,False);self.worker.tick(True,False)
        self.assertEqual(len(self.store.all('converted_tag')),1);self.assertEqual(self.catalog.call_count,1)
        self.assertEqual(self.store.get('library_scan','current')['cursor'],'i:1:2')
    def test_supplement_preserved(self):
        with zipfile.ZipFile(self.source,'a') as z:z.writestr('ComicInfo.xml','<ComicInfo><Series>Fixture</Series><Title>Extra</Title></ComicInfo>')
        before=self.source.read_bytes();self.worker.tick(True,True)
        self.assertFalse(self.store.all('converted_tag'));self.assertEqual(self.source.read_bytes(),before)
    def test_options_and_alternate_tags(self):
        self.worker.tick(False,False);self.next.assert_not_called()
        with zipfile.ZipFile(self.source,'a') as z:z.comment=b'{"ComicBookInfo/1.0":{}}'
        self.worker.tick(True,False);self.assertFalse(self.store.all('converted_tag'))
        self.assertEqual(self.store.all('library_observation')[0]['phase'],'review')
    def test_ambiguous_owner_and_source_race(self):
        self.catalog.side_effect=ValueError('private path');self.worker.tick(True,True)
        self.assertFalse(self.store.all('converted_tag'));self.catalog.side_effect=None
        with zipfile.ZipFile(self.source,'a') as z:z.writestr('extra',b'changed')
        with patch.object(library,'source_version',side_effect=[[1,2,3,4,5],[1,2,3,4,6]]):self.worker.tick(True,False)
        self.assertFalse(self.store.all('converted_tag'))
    def test_publication_review_does_not_spend_attempts_create_token_or_replay(self):
        fixture(self.source);self.worker.tick(False,True)
        with patch.object(library,'publication_review',side_effect=library.Review('fixture-held')):
            self.worker.tick(False,True)
        row=self.store.all('library_repair')[0]
        self.assertEqual(row['phase'],'review');self.assertEqual(row['attempts'],0)
        self.assertFalse(row.get('token'));self.repair.assert_not_called();self.recover.assert_not_called()

    def test_repair_resume_does_not_repeat_publication(self):
        fixture(self.source);self.worker.tick(False,True);self.assertEqual(len(self.store.all('library_repair')),1)
        self.repair.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.worker.tick(False,True)
        self.assertEqual(self.store.all('library_repair')[0]['phase'],'repairing')
        self.recover.return_value='updated';self.worker.tick(False,True)
        self.assertEqual(self.store.all('library_repair')[0]['phase'],'completed');self.assertEqual(self.repair.call_count,1)
    def test_disabled_repair_waits_and_changed_source_is_reviewed(self):
        fixture(self.source);self.worker.tick(False,True);self.worker.tick(True,False);self.repair.assert_not_called()
        fixture(self.source,NESTED.replace('1.00','2.00'));before=self.source.read_bytes();self.worker.tick(False,True)
        self.assertEqual(self.store.all('library_repair')[0]['phase'],'review');self.assertEqual(self.source.read_bytes(),before)
    def test_completed_sweep_delay_and_policy_change(self):
        self.next.return_value=None;self.worker.tick(True,False);self.worker.tick(True,False)
        self.assertEqual(self.next.call_count,1);self.worker.tick(False,True);self.assertEqual(self.next.call_count,2)
        self.now+=3601;self.worker.tick(False,True);self.assertEqual(self.next.call_count,3)
    def test_symlink_and_nested_only(self):
        other=self.root/'other.cbz';self.source.rename(other);self.source.symlink_to(other)
        self.worker.tick(True,True);self.assertFalse(self.store.all('converted_tag'));self.source.unlink()
        with zipfile.ZipFile(self.source,'w') as z:z.writestr('page.jpg',b'page');z.writestr('folder/ComicInfo.xml',NESTED)
        self.worker.tick(True,True);self.assertFalse(self.store.all('library_repair'))
    def test_review_rechecks_catalog_without_file_change(self):
        self.catalog.return_value=None;self.worker.tick(True,False)
        self.assertEqual(self.store.all('library_observation')[0]['phase'],'review')
        self.catalog.return_value=dict(issueid='1',comicid='2');self.worker.tick(True,False)
        self.assertEqual(len(self.store.all('converted_tag')),1)
    def test_unsupported_archive_does_not_stall_cursor(self):
        import struct
        raw=bytearray(self.source.read_bytes())
        local=raw.index(b'PK\x03\x04');central=raw.index(b'PK\x01\x02')
        struct.pack_into('<H',raw,local+8,99);struct.pack_into('<H',raw,central+10,99)
        self.source.write_bytes(raw);self.worker.tick(True,False)
        self.assertEqual(self.store.get('library_scan','current')['cursor'],'i:1:2')
        self.assertEqual(self.store.all('library_observation')[0]['phase'],'review')
        self.next.return_value=('i:2:2',str(self.root/'next.cbz'))
        with zipfile.ZipFile(self.root/'next.cbz','w') as z:z.writestr('page.jpg',b'page')
        self.worker.tick(True,False);self.assertEqual(len(self.store.all('converted_tag')),1)
    def test_owner_change_after_admission_can_be_rediscovered(self):
        fixture(self.source);self.worker.tick(False,True)
        self.catalog.return_value=dict(issueid='3',comicid='2');self.worker.tick(False,True)
        self.assertEqual(self.store.all('library_repair')[0]['phase'],'review')
        self.worker.tick(False,True)
        self.assertEqual(len(self.store.all('library_repair')),2)
        self.assertEqual(len(self.store.active('library_repair',('queued',))),1)
    def test_adapter_idempotence(self):
        import patch_library_metadata as adapter
        source='def worker():\n            converted_tagging.poll()\n'
        fixed=adapter.worker(source);self.assertEqual(adapter.worker(fixed),fixed)
        with self.assertRaises(ValueError):adapter.worker('def worker(): pass')
if __name__=='__main__':unittest.main()

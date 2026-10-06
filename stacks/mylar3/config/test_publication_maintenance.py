"""Direct maintenance cannot mutate before publication ownership is bound."""
import importlib
from pathlib import Path
import sys
import sqlite3
import queue
import threading
import tempfile
import types
import unittest
from unittest.mock import MagicMock, Mock, patch
import zipfile

import tagger_adapter
import test_publication_native as native_cases
import release_naming
import library_metadata
import publication_native
from tagger_nfs import Publisher
import tagger_supplement


class DirectMaintenanceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.source=self.root/'issue.cbz'
        with zipfile.ZipFile(self.source,'w') as archive:
            archive.writestr('001.jpg',b'preserved page')
            archive.writestr('ComicInfo.xml',b'<ComicInfo><Series>Fixture</Series><Number>1</Number></ComicInfo>')
        self.before=self.source.read_bytes()
        self.runtime=types.ModuleType('mylar');self.runtime.__path__=[str(Path(__file__).parent)]
        self.runtime.native_writers=types.SimpleNamespace(publication_mode=lambda:True,owner=Mock())
        context=patch.dict(sys.modules,{'mylar':self.runtime,'mylar.publication_native':publication_native});context.start();self.addCleanup(context.stop)
        self.review=importlib.import_module('mylar.publication_native').Review

    def test_supplement_dry_run_does_not_create_or_acquire_a_writer(self):
        with patch.object(tagger_supplement,'Writer',side_effect=AssertionError('Read-only plan must not create writer')):
            self.assertEqual(tagger_supplement.main([str(self.root)]),0)
        self.assertEqual(self.source.read_bytes(),self.before)

    def test_raw_adapter_and_nfs_entry_retain_before_receipt_or_workspace(self):
        for factory in (tagger_adapter.Publisher,Publisher):
            with self.subTest(factory=factory),tempfile.TemporaryDirectory() as directory:
                publisher=factory(Path(directory)/'receipts')
                with self.assertRaises(self.review):
                    publisher.tag(self.source,{},token='a'*32,repair_nested=True)
                self.assertEqual(self.source.read_bytes(),self.before)
                self.assertFalse(list(publisher.root.glob('*.json')))
                self.assertFalse(list(self.root.glob('.mylar-tag-*')))

    def test_direct_receipt_write_does_not_create_or_replace_a_journal(self):
        publisher=Publisher(self.root/'receipts')
        with self.assertRaises(self.review):publisher.write({'token':'a'*32})
        self.assertFalse(list(publisher.root.glob('*.json')))
        self.assertFalse(list(publisher.root.glob('*.new')))

    def test_direct_output_preparation_preserves_attributes(self):
        import os
        publisher=Publisher(self.root/'receipts');os.setxattr(self.source,'user.fixture',b'preserved')
        with self.assertRaises(self.review):publisher.prepare_output(self.source,{})
        self.assertEqual(os.getxattr(self.source,'user.fixture'),b'preserved')

    def test_direct_supplement_publication_does_not_mark_a_fence(self):
        writer=Mock();writer.root=self.root/'writer';writer.root.mkdir()
        with self.assertRaises(self.review):
            tagger_supplement._publish(self.source,{},writer,Mock(),Mock(),'a'*64,{},'b'*32)
        writer.mark_tagger_pending.assert_not_called()

    def test_raw_recovery_never_reads_or_advances_an_unbound_receipt(self):
        publisher=Publisher(self.root/'receipts')
        with patch.object(publisher,'read') as read,self.assertRaises(self.review):
            publisher.recover('a'*32)
        read.assert_not_called()

    def test_direct_nfs_restore_keeps_the_displaced_file_without_creating_a_name(self):
        displaced=self.root/'displaced.cbz';displaced.write_bytes(self.before)
        target=self.root/'missing.cbz'
        with self.assertRaises(self.review):Publisher.restore_name(displaced,target)
        self.assertFalse(target.exists());self.assertEqual(displaced.read_bytes(),self.before)

    def test_supplement_refuses_before_recovery_backup_or_fence(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        publisher=MagicMock();backup=self.root/'backups';backup.mkdir()
        with self.assertRaises(self.review):
            tagger_supplement.apply(self.source,{'AgeRating':'Teen'},writer,publisher,backup)
        publisher.recover_pending.assert_not_called();writer.mark_tagger_pending.assert_not_called()
        self.assertFalse(list(backup.iterdir()));self.assertEqual(self.source.read_bytes(),self.before)

    def test_nested_repair_refuses_before_state_preparation_or_fence(self):
        native=importlib.import_module('mylar.publication_native')
        library=importlib.import_module('mylar.library_metadata')
        tagger=importlib.import_module('mylar.tagger_native')
        with patch.object(native,'require',side_effect=native.Review('fixture-held')) as require,patch.object(tagger,'state') as state,self.assertRaises(self.review):
            library.repair({'path':str(self.source),'issueid':'1','comicid':'2','sha256':'a'*64,'token':'b'*32})
        require.assert_called_once_with(self.source,issueid='1',comicid='2')
        state.assert_not_called();self.runtime.native_writers.owner.assert_not_called()

    def test_library_poll_consumes_retained_review_and_releases_worker_exclusion(self):
        library=importlib.import_module('mylar.library_metadata')
        self.runtime.APILOCK=False;self.runtime.PP_QUEUE=queue.Queue();self.runtime.logger=Mock()
        self.runtime.workflow=types.SimpleNamespace(policy=lambda:{'library_missing_tags':False,'library_nested_metadata':True},store=Mock())
        self.runtime.native_writers.operation=MagicMock()
        exclusion=threading.Lock()
        with patch.object(library.converted_tagging,'settings',return_value=True),patch.object(library.converted_tagging,'RUN',exclusion),patch.object(library,'Maintenance') as maintenance:
            maintenance.return_value.tick.side_effect=library.Review('fixture-held')
            library.poll()
        self.assertFalse(exclusion.locked());self.runtime.logger.warn.assert_called_once()

    def test_standalone_supplement_cannot_bypass_an_existing_authority_marker(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        (writer.root/'publication-v1.json').write_text('{}')
        with patch.dict(sys.modules,{'mylar':None}),self.assertRaises(ValueError):
            tagger_supplement.recover(writer,Mock())
        writer.clear_tagger_pending.assert_not_called()

    def test_standalone_unreadable_history_holds_without_creating_or_recovering_state(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        database=self.root/'workflow.sqlite';database.write_bytes(b'not SQLite'.ljust(4096,b'!'))
        before=database.read_bytes()
        with patch.dict(sys.modules,{'mylar':None}),self.assertRaises(ValueError):
            tagger_supplement.recover(writer,Mock())
        writer.hold.assert_not_called();self.assertEqual(database.read_bytes(),before)
        self.assertFalse(Path(str(database)+'-journal').exists())

    def test_missing_marker_cannot_hide_existing_publication_history_from_standalone_apply(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        with sqlite3.connect(self.root/'workflow.sqlite') as database:
            database.execute('CREATE TABLE records (kind,key,value)')
            database.execute('INSERT INTO records VALUES (?,?,?)',('publication_census','current','{}'))
        with patch.dict(sys.modules,{'mylar':None}),self.assertRaises(ValueError):
            tagger_supplement.recover(writer,Mock())
        writer.hold.assert_not_called();writer.clear_tagger_pending.assert_not_called()



@unittest.skipUnless((Path(native_cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline archive verifier required; covered in the actual runtime gate')
class FreshMaintenanceProofTests(unittest.TestCase):
    call=native_cases.AdmissionTests.call
    bootstrap=native_cases.AdmissionTests.bootstrap
    prepare=native_cases.AdmissionTests.prepare
    registered=native_cases.AdmissionTests.registered
    sql=native_cases.AdmissionTests.sql

    def setUp(self):
        native_cases.AdmissionTests.setUp(self)
        self.mylar.publication_native=publication_native

    def test_wrong_owner_naming_retains_archive_catalog_and_workflow(self):
        self.registered();self.sql('INSERT INTO issues VALUES (?,?,?,?)',('999','888',None,'Snatched'))
        before=(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes())
        with self.writer.hold(),self.assertRaises(publication_native.Review):
            release_naming.publication_review(self.incoming,issueid='999',comicid='888')
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes()))
        self.assertFalse(self.writer.fenced(release=True))

    def test_stale_correct_archive_holds_nested_repair_before_fencing(self):
        self.registered()
        with zipfile.ZipFile(self.source,'w') as archive:archive.writestr('01.jpg',b'changed correct owner')
        before=(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes())
        job={'path':str(self.incoming),'issueid':'123','comicid':'456'}
        with self.writer.hold(),self.assertRaises(publication_native.Review):library_metadata.publication_review(job)
        self.assertEqual(before,(self.incoming.read_bytes(),self.database.read_bytes(),self.store.path.read_bytes()))
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_annual_shadow_cannot_supply_a_naming_owner(self):
        self.registered();self.sql('INSERT INTO annuals VALUES (?,?,?,?,?,?)',('123','456','789',None,'Wanted',1))
        before=self.incoming.read_bytes()
        with self.writer.hold(),self.assertRaises(publication_native.Review):
            release_naming.publication_review(self.incoming,issueid='123',comicid='456')
        self.assertEqual(self.incoming.read_bytes(),before);self.assertFalse(self.writer.fenced(release=True))


if __name__=='__main__':unittest.main()

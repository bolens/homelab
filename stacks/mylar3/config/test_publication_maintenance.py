"""Direct maintenance cannot mutate before publication ownership is bound."""
import importlib
from contextlib import closing
import os
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

    def test_read_access_time_does_not_change_supplement_authority(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        database=self.root/'workflow.sqlite'
        with closing(sqlite3.connect(database)) as connection,connection:
            connection.execute('CREATE TABLE records(kind,key,value)')
        before=database.stat()
        os.utime(database,ns=(0,before.st_mtime_ns))
        before=database.stat()
        with patch.dict(sys.modules,{'mylar':None}):
            tagger_supplement.publication_review(writer)
        after=database.stat()
        for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns',
                    'st_mode','st_uid','st_gid','st_nlink'):
            self.assertEqual(getattr(before,key),getattr(after,key))
        self.assertFalse(Path(str(database)+'-journal').exists())

    def test_supplement_history_mode_drift_still_holds(self):
        writer=MagicMock();writer.root=self.root/'writer';writer.root.mkdir()
        database=self.root/'workflow.sqlite'
        with closing(sqlite3.connect(database)) as connection,connection:
            connection.execute('CREATE TABLE records(kind,key,value)')
        connect=sqlite3.connect
        def changed(*args,**kwargs):
            connection=connect(*args,**kwargs)
            database.chmod(database.stat().st_mode ^ 0o100)
            return connection
        with patch.dict(sys.modules,{'mylar':None}), \
                patch.object(tagger_supplement.sqlite3,'connect',side_effect=changed), \
                self.assertRaisesRegex(ValueError,'changed during admission'):
            tagger_supplement.publication_review(writer)
        writer.hold.assert_not_called()

    def test_supplement_history_parent_replacement_after_close_holds(self):
        root=self.root/'config';root.mkdir()
        writer=MagicMock();writer.root=root/'writer';writer.root.mkdir()
        database=root/'workflow.sqlite'
        with closing(sqlite3.connect(database)) as connection,connection:
            connection.execute('CREATE TABLE records(kind,key,value)')
        connect=sqlite3.connect
        class Connection:
            def __init__(self,connection):self.connection=connection
            def __getattr__(self,name):return getattr(self.connection,name)
            def close(self):
                self.connection.close()
                moved=self_root/'moved';root.rename(moved);root.symlink_to(moved,target_is_directory=True)
        self_root=self.root
        def changed(*args,**kwargs):return Connection(connect(*args,**kwargs))
        with patch.dict(sys.modules,{'mylar':None}), \
                patch.object(tagger_supplement.sqlite3,'connect',side_effect=changed), \
                self.assertRaisesRegex(ValueError,'parents changed during admission'):
            tagger_supplement.publication_review(writer)
        writer.hold.assert_not_called()

    def test_supplement_transient_foreign_history_cannot_hide_publication_rows(self):
        root=self.root/'config';root.mkdir()
        writer=MagicMock();writer.root=root/'writer';writer.root.mkdir()
        database=root/'workflow.sqlite'
        with closing(sqlite3.connect(database)) as connection,connection:
            connection.execute('CREATE TABLE records(kind,key,value)')
            connection.execute("INSERT INTO records VALUES ('publication_census','current','{}')")
        foreign=self.root/'foreign';foreign.mkdir()
        with closing(sqlite3.connect(foreign/'workflow.sqlite')) as connection,connection:
            connection.execute('CREATE TABLE records(kind,key,value)')
        connect=sqlite3.connect
        def changed(*args,**kwargs):
            moved=self.root/'retained';root.rename(moved);root.symlink_to(foreign,target_is_directory=True)
            try:return connect(*args,**kwargs)
            finally:root.unlink();moved.rename(root)
        with patch.dict(sys.modules,{'mylar':None}), \
                patch.object(tagger_supplement.sqlite3,'connect',side_effect=changed), \
                self.assertRaises(ValueError):
            tagger_supplement.publication_review(writer)
        writer.hold.assert_not_called()

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
        self.rename_import=patch.dict(sys.modules,{'mylar.publication_rename':rename_cases.owned})
        self.rename_import.start();self.addCleanup(self.rename_import.stop)

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




# Genuine authority and Publisher controls for the explicitly bound combined pass.
from contextlib import contextmanager
import shutil
from tagger_archive import snapshot
import publication_guard as correction_guard
import publication_transaction as correction_transaction
import tagger_pack as native_pack
import test_publication_rename as rename_cases
import test_publication_tagging as tagging_cases


@unittest.skipUnless((Path(native_cases.fixtures.TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'offline native archive verifier required')
class PreservedSupplementTests(unittest.TestCase):
    call=rename_cases.RenameTests.call
    bootstrap=rename_cases.RenameTests.bootstrap
    prepare=rename_cases.RenameTests.prepare
    registered=rename_cases.RenameTests.registered
    connection=rename_cases.RenameTests.connection

    def setUp(self):
        rename_cases.RenameTests.setUp(self)
        @contextmanager
        def operation():
            with self.writer.hold(allow_tagger_pending=True,allow_release_pending=True):
                self.runtime.admission(self.writer)
                yield self.writer
        self.runtime.operation=operation
        self.mylar.tagger_pack=native_pack
        self.mylar.publication_transaction=correction_transaction
        self.mylar.publication_guard=correction_guard
        self.mylar.release_naming=release_naming
        aliases={'mylar.tagger_pack':native_pack,'mylar.publication_transaction':correction_transaction,
                 'mylar.publication_guard':correction_guard,'mylar.release_naming':release_naming}
        context=patch.dict(sys.modules,aliases);context.start();self.addCleanup(context.stop)
        paths,_=tagging_cases.TransactionTests.recovery_state(self)
        self.publisher=native_pack.Publisher(paths[1],self.root)
        with zipfile.ZipFile(self.source) as archive:
            members={name:archive.read(name) for name in archive.namelist() if name!='ComicInfo.xml'}
        with zipfile.ZipFile(self.source,'w') as archive:
            for name,value in members.items():archive.writestr(name,value)
            archive.writestr('ComicInfo.xml','<ComicInfo><Series>Publication</Series><Number>1</Number></ComicInfo>')
        copies=self.root/'combined-copies';copies.mkdir(mode=0o700)
        self.original=copies/'original.cbz';self.restored=copies/'restore.cbz'
        for copy in (self.original,self.restored):shutil.copy2(self.source,copy)
        self.before=tagger_adapter.fingerprint(self.source)
        self.policy={'AgeRating':'Teen'}

    def apply(self):
        return tagger_supplement.apply_preserved(self.source,self.policy,self.writer,self.publisher,
            self.original,self.restored,self.before,'a'*32)

    def test_unknown_current_owner_root_metadata_pass_preserves_exact_payload_and_pair(self):
        from tagger_archive import snapshot
        old=snapshot(self.source)
        result=self.apply();new=snapshot(self.source)
        self.assertEqual(result['state'],'committed');self.assertTrue(result['payloads_verified'])
        self.assertNotEqual(result['before'],result['after'])
        self.assertEqual((old.members,old.attributes,old.mode,old.uid,old.gid),
                         (new.members,new.attributes,new.mode,new.uid,new.gid))
        for copy in (self.original,self.restored):self.assertEqual(tagger_adapter.fingerprint(copy),self.before)
        self.assertFalse(self.writer.fenced(tagger=True));self.assertFalse(correction_transaction.present(self.writer))
        self.assertEqual(correction_guard.private_json(self.publisher.receipt('a'*32))['state'],'committed')

    def test_registered_allowed_metadata_pass_keeps_correction_census_and_members(self):
        prepared=self.prepare(self.call('status')['census']);self.call('register',token=prepared['token'])
        census=self.call('status')['census'];self.assertEqual(self.apply()['state'],'committed')
        self.assertEqual(self.call('status')['census'],census)
        self.assertEqual(tagger_adapter.fingerprint(self.original),self.before)

    def test_changed_or_linked_pair_prevents_producer_receipt_and_source_mutation(self):
        self.restored.write_bytes(b'changed retained archive')
        with self.assertRaises(publication_native.Review):self.apply()
        self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)
        self.assertEqual(list(self.publisher.root.glob('*.json')),[])
        self.assertFalse(self.writer.fenced(tagger=True))

    def test_pair_drift_during_producer_staging_holds_and_retains_original(self):
        def drift(point):
            if point=='staged':self.restored.write_bytes(b'changed retained archive')
        with patch('tagger_adapter._checkpoint',side_effect=drift),self.assertRaises(publication_native.Review):self.apply()
        self.assertTrue(self.original.exists());self.assertTrue(correction_transaction.present(self.writer))
        self.assertTrue(self.writer.fenced(tagger=True));self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)

    def test_caller_policy_drift_cannot_change_captured_supplement_output(self):
        def drift(point):
            if point=='staged':self.policy['AgeRating']='Mature 17+'
        with patch('tagger_adapter._checkpoint',side_effect=drift):self.assertEqual(self.apply()['state'],'committed')
        self.assertIn(b'<AgeRating>Teen</AgeRating>',snapshot(self.source).xml)
        self.assertTrue(self.original.exists());self.assertTrue(self.restored.exists())
        self.assertFalse(correction_transaction.present(self.writer))

    def test_catalog_status_drift_before_exchange_holds_without_false_completion(self):
        def drift(point):
            if point=='before_exchange':
                with self.connection() as db:db.execute('UPDATE issues SET Status=?',('Wanted',))
        with patch('tagger_adapter._checkpoint',side_effect=drift),self.assertRaises(publication_native.Review):self.apply()
        self.assertTrue(self.original.exists());self.assertTrue(correction_transaction.present(self.writer))
        self.assertTrue(self.writer.fenced(tagger=True))

    def test_terminal_clear_interruption_retains_pair_and_exact_native_intent(self):
        with (patch.object(correction_transaction.Tagging,'verify_completion',side_effect=publication_native.Review('interrupted terminal proof')),
              self.assertRaises(publication_native.Review)):self.apply()
        self.assertTrue(self.original.exists());self.assertTrue(self.restored.exists())
        self.assertTrue(correction_transaction.present(self.writer));self.assertTrue(self.writer.fenced(tagger=True))

    def test_foreign_registered_owner_payload_is_held_before_supplement_intent(self):
        prepared=self.prepare(self.call('status')['census']);self.call('register',token=prepared['token'])
        with self.connection() as db:
            db.execute('INSERT INTO comics(ComicID,ComicLocation) VALUES (?,?)',('888',str(self.library)))
            db.execute('UPDATE issues SET ComicID=?',('888',))
        with self.assertRaises(publication_native.Review):self.apply()
        self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)
        self.assertFalse(correction_transaction.present(self.writer));self.assertTrue(self.original.exists())

    def test_replaced_pending_fence_during_staging_is_held_without_exchange(self):
        def drift(point):
            if point=='staged':
                moved=self.writer.root/'captured-pending';self.writer.tagger_pending.rename(moved)
                self.writer.tagger_pending.write_bytes(b'foreign fence')
        with patch('tagger_adapter._checkpoint',side_effect=drift),self.assertRaises(publication_native.Review):self.apply()
        self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)
        self.assertTrue(correction_transaction.present(self.writer));self.assertEqual(self.writer.tagger_pending.read_bytes(),b'foreign fence')
        self.assertTrue(self.original.exists());self.assertTrue(self.restored.exists())

    def test_preservation_hardlink_is_never_accepted_as_independent_restore(self):
        import os
        self.restored.unlink();os.link(self.original,self.restored)
        with self.assertRaises(publication_native.Review):self.apply()
        self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)
        self.assertFalse(correction_transaction.present(self.writer));self.assertTrue(self.original.exists())

    def test_no_additions_rechecks_current_source_before_verified_unchanged(self):
        self.policy={};actual=tagger_supplement.snapshot
        def changed(path,*args,**kwargs):
            saved=actual(path,*args,**kwargs)
            if Path(path)==self.restored:
                with zipfile.ZipFile(self.source) as archive:
                    members={name:archive.read(name) for name in archive.namelist()}
                members['ComicInfo.xml']=b'<ComicInfo><Series>Publication</Series><Number>1</Number><Title>Changed</Title></ComicInfo>'
                with zipfile.ZipFile(self.source,'w') as archive:
                    for name,value in members.items():archive.writestr(name,value)
            return saved
        with patch.object(tagger_supplement,'snapshot',side_effect=changed),self.assertRaises(publication_native.Review):self.apply()
        self.assertTrue(self.original.exists());self.assertTrue(self.restored.exists())
        self.assertFalse(correction_transaction.present(self.writer));self.assertNotEqual(tagger_adapter.fingerprint(self.source),self.before)

    def test_no_additions_verified_unchanged_has_no_publication_replay_or_fence(self):
        self.policy={};result=self.apply()
        self.assertEqual(result['state'],'unchanged');self.assertTrue(result['payloads_verified']);self.assertIsNone(result['token'])
        self.assertEqual(tagger_adapter.fingerprint(self.source),self.before)
        self.assertFalse(correction_transaction.present(self.writer));self.assertFalse(self.writer.fenced(tagger=True))


if __name__=='__main__':unittest.main()

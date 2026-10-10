"""Actual public Controller/Writer, SQLite and archive backend; host SDK alias explicit."""
import importlib
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch
import zipfile

import publication_api as api
import media_writer as writers
import publication_guard as g
import publication_archive_owned as o
import test_publication_api as fixture
import workflow_store

HERE=Path(__file__).parent
pkg=types.ModuleType('mylar');pkg.__path__=[str(HERE)]
sys.modules['mylar']=pkg;sys.modules['mylar.publication_archive_owned']=o
spec=importlib.util.spec_from_file_location('mylar.publication_retained_delivery',HERE/'publication_retained_delivery.py')
r=importlib.util.module_from_spec(spec);sys.modules[spec.name]=r;spec.loader.exec_module(r)
p=importlib.import_module('mylar.pack_intake')

@unittest.skipUnless((Path(fixture.TOOL_ROOT)/'lib/archive_backend.py').is_file(),'public archive backend required')
class Retained(unittest.TestCase):
    def setUp(self):
        self.case=fixture.NativeProtocolTests('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.case.bootstrap();self.c=self.case.controller;self.writer=self.case.writer
        self.cache=self.case.root/'ddl';self.cache.mkdir();self.pack=self.cache/'pack';self.pack.mkdir()
        self.original=self.pack/'member.cbz';shutil.copyfile(self.case.source,self.original)
        self.owner=self.case.owner;self.target=self.case.source
        pkg.CONFIG=types.SimpleNamespace(DDL_LOCATION=str(self.cache));pkg.DATA_DIR=str(self.case.root)
        modules=[api,writers,g]+[importlib.import_module(n) for n in ('publication_derivative','publication_archive_repair','publication_archive_derivative','publication_archive_layout')]
        ctx=patch.object(o,'sdk',return_value=modules);ctx.start();self.addCleanup(ctx.stop)
        ctx=patch.object(g,'TOOL_ROOT',fixture.TOOL_ROOT);ctx.start();self.addCleanup(ctx.stop)
        # Actual Controller/Writer class identity, no substitutes. SDK path alias is
        # the predecessor owning host fixture; installed origin acceptance pending.
        sys.modules['mylar.workflow_store']=workflow_store
        self.ddl='56';self.key='a'*64;self.generation=p.source_state(self.pack,content=True)
        checksum=hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.member=hashlib.sha256(os.fsencode(Path('extracted')/self.original.name)+b'\0'+checksum.encode()).hexdigest()
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('CREATE TABLE ddl_info(id TEXT,comicid TEXT,status TEXT,pack INT,filename TEXT)')
            db.execute('INSERT INTO ddl_info VALUES(?,?,?,?,?)',(self.ddl,self.owner['parentcomicid'],'Completed',1,self.pack.name));db.commit()
        with patch.object(p.workflow,'store',return_value=workflow_store.Store(self.case.root,existing_only=True)):
            self.key=p.discover(self.ddl,self.pack,'Fixture')['id']
        self.body={'version':1,'kind':r.KIND,'ddl_id':self.ddl,'pack_id':self.key,'member_id':self.member,
                'source_generation':self.generation,'source_sha256':checksum,
                'target_sha256':hashlib.sha256(self.target.read_bytes()).hexdigest(),'owner':self.owner,'review_sha256':'b'*64}
        ctx=patch.object(r,'ENABLED',True);ctx.start();self.addCleanup(ctx.stop)

    def prepare(self):return r.prepare_existing(self.c,self.writer,self.body)

    def test_exact_preserved_acceptance_is_fresh_not_historical_import(self):
        before=self.target.read_bytes();signature=tuple(o.signature(self.target));source=self.original.read_bytes()
        with self.writer.hold():cap=self.prepare();answer=cap.accept()
        self.assertEqual(answer['outcome'],'fresh-retained-delivery-accepted');self.assertIs(answer['historical_import_ack'],False)
        self.assertEqual(self.target.read_bytes(),before);self.assertEqual(tuple(o.signature(self.target)),signature)
        self.assertEqual(self.original.read_bytes(),source)
        proof=json.loads(Path(answer['ack']['path']).read_text())
        self.assertTrue(proof['fresh_catalog_event']);self.assertFalse(proof['historical_import_ack'])
        self.assertEqual(len(proof['target_preservation']),2)
        with sqlite3.connect(self.c.native_database) as db:
            self.assertEqual(db.execute('SELECT Status,Location FROM issues WHERE IssueID=?',(self.owner['issueid'],)).fetchone(),('Downloaded',self.target.name))
        self.assertFalse((self.case.root/'ordinary-import-v1.sqlite').exists())

    def test_default_disabled(self):
        with self.writer.hold(),patch.object(r,'ENABLED',False),self.assertRaises(o.Held):self.prepare()
        self.assertFalse((self.case.root/r.NAME).exists())

    def test_fake_capability_and_controller_cannot_grant_acceptance(self):
        with self.assertRaises(o.Held):r.RetainedDeliveryAcceptance()
        fake=r.RetainedDeliveryAcceptance.__new__(r.RetainedDeliveryAcceptance)
        with self.writer.hold(),self.assertRaises(o.Held):fake.accept()
        with self.writer.hold(),self.assertRaises(o.Held):r.prepare_existing(object(),self.writer,self.body)

    def test_replaced_retained_original_held(self):
        with self.writer.hold():
            cap=self.prepare();raw=self.original.read_bytes();self.original.rename(self.pack/'aside');self.original.write_bytes(raw)
            with self.assertRaises(o.Held):cap.accept()

    def test_late_preserved_target_mode_held(self):
        with self.writer.hold():
            cap=self.prepare();os.chmod(self.target,0o600)
            # Ensure a real mode transition independent of fixture default.
            os.chmod(self.target,0o640)
            with self.assertRaises(o.Held):cap.accept()

    def test_different_payload_held(self):
        with zipfile.ZipFile(self.original,'w') as z:z.writestr('01.jpg',b'other original page')
        self.body['source_generation']=p.source_state(self.pack,content=True)
        self.body['source_sha256']=hashlib.sha256(self.original.read_bytes()).hexdigest()
        self.body['member_id']=hashlib.sha256(os.fsencode(Path('extracted')/self.original.name)+b'\0'+self.body['source_sha256'].encode()).hexdigest()
        workflow_store.Store(self.case.root,existing_only=True).set('pack',self.key,{
            'id':self.key,'ddl_id':self.ddl,'source':str(self.pack),'source_generation':self.body['source_generation'],'members':[]})
        with self.writer.hold(),self.assertRaises(o.Held):self.prepare()

    def test_unknown_member_and_capture_hold(self):
        self.body['member_id']='0'*64
        with self.writer.hold(),self.assertRaises(o.Held):self.prepare()

    def test_no_replay_after_acceptance(self):
        with self.writer.hold():
            cap=self.prepare();cap.accept()
            with self.assertRaises(o.Held):cap.accept()
            with self.assertRaises(FileExistsError):self.prepare()

    def test_final_helper_target_mutation_has_no_ACK(self):
        with self.writer.hold():
            cap=self.prepare();real=r._validate;fired=[]
            def late(core):
                real(core)
                if core['phase']=='uncertain' and (core['folder']/'accepted.json').exists():
                    os.chmod(self.target,0o640);fired.append(True)
            with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_created_preservation_FD_mode_drift_held(self):
        real=r.os.fsync;fired=[]
        def late(fd):
            s=os.fstat(fd)
            if not fired and s.st_mode&0o170000==0o100000:
                os.fchmod(fd,0o640);fired.append(True)
            return real(fd)
        with self.writer.hold(),patch.object(r.os,'fsync',late),self.assertRaises(o.Held):self.prepare()
        self.assertTrue(fired);self.assertTrue(self.original.exists());self.assertTrue(self.target.exists())

    def test_original_emitted_ACK_reopens_as_fact_without_live_capability(self):
        with self.writer.hold():
            cap=self.prepare();answer=cap.accept()
            observed=r.verify_ack(self.c,self.writer,self.body,answer['ack'])
        self.assertEqual(observed['outcome'],'fresh-retained-delivery-accepted')
        self.assertFalse(observed['historical_import_ack']);self.assertFalse(observed['ordinary_import_grant'])

    def test_passive_same_bytes_replaced_ACK_cannot_refresh_original_ref(self):
        with self.writer.hold():
            cap=self.prepare();answer=cap.accept();target=Path(answer['ack']['path']);raw=target.read_bytes()
            target.rename(target.with_name('foreign.json'));target.write_bytes(raw);target.chmod(0o600)
            with self.assertRaises(o.Held):r.verify_ack(self.c,self.writer,self.body,answer['ack'])

    def test_passive_last_raw_helper_cannot_change_original_target(self):
        with self.writer.hold():
            cap=self.prepare();answer=cap.accept();real=r._raw;fired=[]
            def late(files,nodes,absent,namespaces,claims=None):
                real(files,nodes,absent,namespaces,claims)
                if str(Path(answer['ack']['path'])) in files:
                    os.chmod(self.target,0o640);fired.append(True)
            with patch.object(r,'_raw',late),self.assertRaises(o.Held):r.verify_ack(self.c,self.writer,self.body,answer['ack'])
        self.assertTrue(fired)

    def test_annual_parent_release_identity_preserved(self):
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('DELETE FROM issues')
            db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.target.name,'Archived',0));db.commit()
        self.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
        with self.writer.hold():cap=self.prepare();answer=cap.accept();observed=r.verify_ack(self.c,self.writer,self.body,answer['ack'])
        self.assertFalse(observed['historical_import_ack'])
        with sqlite3.connect(self.c.native_database) as db:
            self.assertEqual(db.execute('SELECT ReleaseComicID,Status,Location FROM annuals').fetchone(),('789','Archived',self.target.name))

    def test_wrong_annual_release_owner_held(self):
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.target.name,'Archived',0));db.commit()
        self.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'790'}
        with self.writer.hold(),self.assertRaises(o.Held):self.prepare()

    def test_lost_postcommit_response_uses_original_ACK_only_no_replay(self):
        with self.writer.hold():
            cap=self.prepare();answer=cap.accept()
            # The simulated transport loses its response after actual producer completion.
            with self.assertRaises(o.Held):cap.accept()
            self.assertTrue(self.original.exists());self.assertTrue(self.target.exists())
            self.assertEqual(r.verify_ack(self.c,self.writer,self.body,answer['ack'])['token'],answer['token'])

    def test_late_catalog_helper_changes_complete_unrelated_row_and_holds(self):
        with self.writer.hold():
            cap=self.prepare();real=r._sql;fired=[]
            def late(path,stamp):
                result=real(path,stamp)
                if not fired:
                    with sqlite3.connect(path) as db:db.execute("UPDATE comics SET Status='Changed'");db.commit()
                    fired.append(True)
                return result
            with patch.object(r,'_sql',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired);self.assertTrue(self.original.exists())

    def test_nested_original_ZIP_member_key_matches_no_caller_path(self):
        outer=self.cache/'outer.zip'
        with zipfile.ZipFile(outer,'w') as archive:archive.writestr('sub/member.cbz',self.original.read_bytes())
        self.pack=outer;self.body['source_generation']=p.source_state(outer,content=True)
        self.body['member_id']=hashlib.sha256(os.fsencode(Path('extracted/sub/member.cbz'))+b'\0'+self.body['source_sha256'].encode()).hexdigest()
        with sqlite3.connect(self.c.native_database) as db:db.execute('UPDATE ddl_info SET filename=?',(outer.name,));db.commit()
        with patch.object(p.workflow,'store',return_value=workflow_store.Store(self.case.root,existing_only=True)):
            self.key=p.discover(self.ddl,outer,'Fixture')['id']
        self.body['pack_id']=self.key
        original=outer.read_bytes()
        with self.writer.hold():cap=self.prepare();answer=cap.accept();self.assertEqual(r.verify_ack(self.c,self.writer,self.body,answer['ack'])['token'],answer['token'])
        self.assertEqual(outer.read_bytes(),original)

    def test_fully_lost_response_reads_exact_producer_issued_reference(self):
        with self.writer.hold():
            cap=self.prepare();token=cap.accept()['token']  # discard original ACK ref entirely
            with self.assertRaises(o.Held):cap.accept()
            result=r.status_existing(self.c,self.writer,self.body)
        self.assertEqual(result['token'],token);self.assertFalse(result['historical_import_ack'])
        self.assertTrue(self.original.exists());self.assertTrue(self.target.exists())

    def test_missing_issuance_after_catalog_success_remains_uncertain_no_replay(self):
        real=r._write;fired=[]
        def lost(path,*args,**kwargs):
            if path.name=='accepted.json':fired.append(True);raise OSError('disposable lost completion')
            return real(path,*args,**kwargs)
        with self.writer.hold():
            cap=self.prepare()
            with patch.object(r,'_write',lost),self.assertRaises(OSError):cap.accept()
            with self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            with self.assertRaises(o.Held):cap.accept()
            with self.assertRaises(FileExistsError):self.prepare()
        self.assertTrue(fired);self.assertTrue(self.original.exists());self.assertTrue(self.target.exists())

    def test_issued_reference_same_bytes_new_inode_cannot_rebase(self):
        with self.writer.hold():
            cap=self.prepare();answer=cap.accept();path=Path(answer['ack']['path']).with_name('issued.json')
            raw=path.read_bytes();path.rename(path.with_name('foreign.json'));path.write_bytes(raw);path.chmod(0o600)
            with self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)

    def test_foreign_created_folder_entry_not_adopted_as_original_census(self):
        real=r._write;fired=[]
        def late(path,*args,**kwargs):
            result=real(path,*args,**kwargs)
            if path.name=='intent.json':(path.parent/'foreign').write_bytes(b'foreign');fired.append(True)
            return result
        with self.writer.hold(),patch.object(r,'_write',late),self.assertRaises(o.Held):self.prepare()
        self.assertTrue(fired)

    def test_late_baseline_mutation_cannot_refresh_factory_originals(self):
        with self.writer.hold():
            cap=self.prepare();real=r._validate;fired=[]
            def late(core):
                real(core)
                if core['phase']=='prepared':
                    os.chmod(self.target,0o640);core['files'][str(self.target)]=tuple(o.signature(self.target));fired.append(True)
            with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_missing_original_delivery_remains_review(self):
        self.original.unlink()
        with self.writer.hold(),self.assertRaises((o.Held,OSError,ValueError)):self.prepare()
        self.assertTrue(self.target.exists())

    def test_new_capture_generation_cannot_use_old_request(self):
        (self.pack/'new-sidecar.txt').write_text('new capture')
        with self.writer.hold(),self.assertRaises(o.Held):self.prepare()

    def test_overlapping_current_catalog_claim_is_held(self):
        with sqlite3.connect(self.c.native_database) as db:
            row=db.execute('SELECT * FROM issues').fetchone()
            columns=[x[1] for x in db.execute('PRAGMA table_info(issues)')]
            values=list(row);values[columns.index('IssueID')]='other'
            db.execute('INSERT INTO issues VALUES ('+','.join('?' for _ in values)+')',values);db.commit()
        with self.writer.hold(),self.assertRaises(o.Held):self.prepare()

    def test_created_private_parent_cannot_adopt_helper_mode_change(self):
        real=r._nodes;fired=[]
        def late(paths):
            for path in paths:
                path=Path(path)
                if path.parent.name==r.NAME and len(path.name)==64:
                    os.chmod(path,0o755);fired.append(True)
            return real(paths)
        with self.writer.hold(),patch.object(r,'_nodes',late),self.assertRaises(o.Held):self.prepare()
        self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_target_closure(self):
        with self.writer.hold():
            self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                os.chmod(self.target,0o640);fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_source_closure(self):
        with self.writer.hold():
            self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                os.chmod(self.original,0o640);fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_preserved_closure(self):
        with self.writer.hold():
            result_ack=self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                os.chmod(next(Path(result_ack['ack']['path']).parent.glob('target-preserved.*')),0o640);fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_workflow_closure(self):
        with self.writer.hold():
            self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                os.chmod(self.c.database,0o640);fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_companion_closure(self):
        with self.writer.hold():
            self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                Path(str(self.c.native_database)+'-wal').write_bytes(b'foreign');fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_status_last_verifier_preserves_original_namespace_closure(self):
        with self.writer.hold():
            result_ack=self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs)
                (Path(result_ack['ack']['path']).parent/'foreign').write_bytes(b'foreign');fired.append(True)
                return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_saved_records_without_original_producer_event_never_rehydrate(self):
        with self.writer.hold():
            answer=self.prepare().accept()
            with patch.object(r,'_EVENTS',{}):
                with self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
                with self.assertRaises(o.Held):r.verify_ack(self.c,self.writer,self.body,answer['ack'])

    def test_last_producer_validation_pending_absence_is_retained(self):
        real=r._validate;fired=[]
        def late(core):
            real(core)
            if core['phase']=='uncertain' and (core['folder']/'accepted.json').exists():
                self.writer.pending.write_bytes(b'foreign');fired.append(True)
        with self.writer.hold():
            cap=self.prepare()
            with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_last_passive_verifier_pending_absence_is_retained(self):
        with self.writer.hold():
            self.prepare().accept();real=r.verify_ack;fired=[]
            def late(*args,**kwargs):
                result=real(*args,**kwargs);self.writer.pending.write_bytes(b'foreign');fired.append(True);return result
            with patch.object(r,'verify_ack',late),self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertTrue(fired)

    def test_actual_same_instance_returned_event_survives_lost_reply(self):
        with self.writer.hold():
            self.prepare().accept()  # transport drops the response, never an ACK reissue
            self.assertEqual(r.status_existing(self.c,self.writer,self.body)['outcome'],'fresh-retained-delivery-accepted')

    def test_last_producer_validation_cannot_replace_Writer_binding(self):
        real=r._validate;fired=[];original=self.writer.pending
        def late(core):
            real(core)
            if core['phase']=='uncertain' and (core['folder']/'accepted.json').exists():
                self.writer.pending=self.writer.root/'changed.pending';fired.append(True)
        try:
            with self.writer.hold():
                cap=self.prepare()
                with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        finally:self.writer.pending=original
        self.assertTrue(fired)

    def test_last_producer_validation_retains_original_Writer_namespace(self):
        real=r._validate;fired=[]
        def late(core):
            real(core)
            if core['phase']=='uncertain' and (core['folder']/'accepted.json').exists():
                (self.writer.root/'foreign-protocol').write_bytes(b'foreign');fired.append(True)
        with self.writer.hold():
            cap=self.prepare()
            with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_last_producer_helper_cannot_refresh_original_Writer_binding(self):
        real=r._validate;fired=[];original=self.writer.pending
        def late(core):
            real(core)
            if core['phase']=='uncertain' and (core['folder']/'accepted.json').exists():
                self.writer.pending=self.writer.root/'changed.pending'
                core['writer_binding']=r._writer_binding(self.writer);fired.append(True)
        try:
            with self.writer.hold():
                cap=self.prepare()
                with patch.object(r,'_validate',late),self.assertRaises(o.Held):cap.accept()
        finally:self.writer.pending=original
        self.assertTrue(fired)

if __name__=='__main__':unittest.main()

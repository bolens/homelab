"""Real public factory/Writer/archives/SQLite; host SDK fixture aliases explicit."""
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from test_publication_api import TOOL_ROOT

import test_publication_retained_delivery as fixture
import workflow_store
r=fixture.r;o=fixture.o;p=fixture.p
f=importlib.import_module('mylar.publication_retained_finalize')


@unittest.skipUnless((Path(TOOL_ROOT)/'lib/archive_backend.py').is_file(),
                     'public archive backend required for retained finalization')
class Finalize(unittest.TestCase):
    def setUp(self):
        self.case=fixture.Retained('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.c=self.case.c;self.writer=self.case.writer;self.body=self.case.body
        self.store=workflow_store.Store(self.c.root,existing_only=True)
        old=self.store.get('pack',self.body['pack_id'])
        old['members']=[{'id':self.body['member_id'],'kind':'issue','phase':'review',
            'issueid':self.body['owner']['issueid'],'comicid':self.body['owner']['parentcomicid'],
            'releasecomicid':self.body['owner']['releasecomicid']}]
        self.store.set('pack',self.body['pack_id'],old)
        context=patch.object(f,'ENABLED',True);context.start();self.addCleanup(context.stop)

    def accept(self):
        cap=self.case.prepare();cap.accept();return cap

    def test_actual_acceptance_finalizes_one_member_and_reserved_record(self):
        target=self.case.target.read_bytes();source=self.case.original.read_bytes()
        with self.writer.hold():
            cap=self.accept();event=r._EVENTS[(str(self.c.root),r._CORES[cap]['token'])]
            answer=f.finalize(cap).observe()
            self.assertEqual(event,r._EVENTS[(str(self.c.root),answer['token'])])
            self.assertFalse(answer['ordinary_import_grant']);self.assertFalse(answer['cleanup_grant'])
        pack=self.store.get('pack',self.body['pack_id'])
        self.assertEqual(pack['members'][0]['phase'],f.MEMBER_PHASE);self.assertEqual(pack['phase'],'review')
        self.assertEqual(self.case.target.read_bytes(),target);self.assertEqual(self.case.original.read_bytes(),source)
        with sqlite3.connect(self.c.native_database) as db:
            self.assertEqual(db.execute('SELECT status FROM ddl_info').fetchall(),[('Completed',)])
        self.assertIsNotNone(self.store.get(f.RECORD_KIND,answer['token']))

    def test_default_disabled_and_fake_receipt(self):
        with self.writer.hold():
            cap=self.accept()
            with patch.object(f,'ENABLED',False),self.assertRaises(o.Held):f.finalize(cap)
            self.assertEqual(r._CORES[cap]['phase'],'accepted')
        with self.assertRaises(o.Held):f.RetainedFinalization()
        with self.assertRaises(o.Held):f.finalize(object())

    def test_prepared_receipt_cannot_finalize(self):
        with self.writer.hold(),self.assertRaises(o.Held):f.finalize(self.case.prepare())

    def test_no_replay(self):
        with self.writer.hold():
            cap=self.accept();f.finalize(cap)
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_saved_reserved_record_cannot_mint_commit_witness(self):
        with self.writer.hold():
            cap=self.accept();answer=f.finalize(cap).observe();original=f._FINALS.pop((str(self.c.root),answer['token']))
            try:
                with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)
            finally:f._FINALS[(str(self.c.root),answer['token'])]=original

    def test_lost_reply_reconciles_original_commit_read_only(self):
        with self.writer.hold():
            cap=self.accept();f.finalize(cap)
            before=self.c.database.read_bytes();answer=f.status_existing(self.c,self.writer,self.body)
            self.assertEqual(answer['outcome'],'fresh-retained-backend-finalized')
            self.assertEqual(self.c.database.read_bytes(),before)

    def test_actual_fork_cannot_rehydrate_committed_producer(self):
        with self.writer.hold():
            f.finalize(self.accept());read,write=os.pipe();pid=os.fork()
            if pid==0:
                os.close(read)
                try:
                    try:f.status_existing(self.c,self.writer,self.body)
                    except o.Held:answer=b'held'
                    else:answer=b'accepted'
                    os.write(write,answer)
                finally:os.close(write);os._exit(0)
            os.close(write)
            try:answer=os.read(read,20)
            finally:os.close(read)
            _,status=os.waitpid(pid,0)
            self.assertEqual(status,0);self.assertEqual(answer,b'held')

    def test_forged_preexisting_reserved_record_refused(self):
        token=hashlib.sha256((self.body['ddl_id']+'\0'+self.body['pack_id']+'\0'+self.body['member_id']).encode()).hexdigest()
        self.store.set(f.RECORD_KIND,token,{'fresh_retained_acceptance':True})
        with self.writer.hold():
            cap=self.accept()
            with self.assertRaises(o.Held):f.finalize(cap)
            self.assertEqual(r._CORES[cap]['phase'],'finalization-uncertain')

    def test_wrong_annual_or_member_identity(self):
        pack=self.store.get('pack',self.body['pack_id']);pack['members'][0]['kind']='annual';self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():
            cap=self.accept()
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_worker_cannot_forge_reserved_fields_before_handoff(self):
        for member in ({'retained_finalization':'f'*64},{'phase':'retained-accepted'}):
            with self.assertRaises(ValueError):p.report(json.dumps({'id':self.body['pack_id'],'members':[member]}))
        with self.assertRaises(ValueError):p.report(json.dumps({'retained_delivery_final':True}))
        with self.assertRaises(ValueError):p.report(json.dumps({'phase':'retained-accepted'}))
        with self.assertRaises(ValueError):p.report(json.dumps({'record_kind':f.RECORD_KIND}))

    def test_worker_cannot_erase_native_final_member(self):
        with self.writer.hold():f.finalize(self.accept())
        with patch.object(p.workflow,'store',return_value=self.store),patch.dict(__import__('sys').modules,
                {'mylar.worker_handoff':type('H',(),{'admit':staticmethod(lambda *a:None)})()}):
            with self.assertRaises(ValueError):p.report(json.dumps({'id':self.body['pack_id'],'members':[]}))

    def late(self,path,passive=False,companion=False):
        with self.writer.hold():
            cap=self.accept()
            if passive:f.finalize(cap)
            real=f._checked;calls=[]
            def late(packet,files):
                real(packet,files);calls.append(1)
                if passive or len(calls)==3:
                    if companion:Path(str(path)+'-wal').write_bytes(b'foreign')
                    else:os.chmod(path,0o640)
            with patch.object(f,'_checked',side_effect=late),self.assertRaises(o.Held):
                if passive:f.status_existing(self.c,self.writer,self.body)
                else:f.finalize(cap)
            self.assertTrue(calls)

    def test_final_callback_target_drift_held(self):self.late(self.case.target)
    def test_final_callback_source_drift_held(self):self.late(self.case.original)
    def test_final_callback_native_companion_held(self):self.late(self.c.native_database,companion=True)
    def test_passive_final_callback_target_drift_held(self):self.late(self.case.target,True)
    def test_passive_final_callback_source_drift_held(self):self.late(self.case.original,True)
    def test_passive_final_callback_pending_held(self):
        with self.writer.hold():
            f.finalize(self.accept());real=f._checked
            def late(packet,files):real(packet,files);self.writer.pending.write_bytes(b'foreign')
            with patch.object(f,'_checked',side_effect=late),self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_crash_before_commit_stays_uncertain_without_replay(self):
        with self.writer.hold():
            cap=self.accept();real=f._checked;calls=[]
            def stop(packet,files):
                real(packet,files);calls.append(1)
                if len(calls)==2:raise RuntimeError('simulated precommit crash')
            with patch.object(f,'_checked',side_effect=stop),self.assertRaises(RuntimeError):f.finalize(cap)
            self.assertEqual(r._CORES[cap]['phase'],'finalization-uncertain')
            with self.assertRaises(o.Held):f.finalize(cap)
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_complete_catalog_unrelated_row_mutation_held(self):
        with self.writer.hold():
            cap=self.accept()
            with sqlite3.connect(self.c.native_database) as db:db.execute('UPDATE ddl_info SET status=?',('Other',));db.commit()
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_native_backend_mutation_after_commit_held(self):
        with self.writer.hold():
            f.finalize(self.accept())
            with sqlite3.connect(self.c.database) as db:db.execute('UPDATE records SET value=? WHERE kind=?',('{}',f.RECORD_KIND));db.commit()
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_annual_parent_release_exact_positive(self):
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('DELETE FROM issues')
            db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.case.target.name,'Archived',0));db.commit()
        self.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
        pack=self.store.get('pack',self.body['pack_id']);pack['members'][0].update(kind='annual',releasecomicid='789')
        self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():answer=f.finalize(self.accept()).observe()
        self.assertFalse(answer['historical_import_ack'])
        with sqlite3.connect(self.c.native_database) as db:self.assertEqual(db.execute('SELECT ReleaseComicID,Status FROM annuals').fetchall(),[('789','Archived')])

    def test_annual_wrong_release_member_is_held(self):
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('DELETE FROM issues')
            db.execute('INSERT INTO annuals VALUES(?,?,?,?,?,?)',('123','456','789',self.case.target.name,'Archived',0));db.commit()
        self.body['owner']={'table':'annuals','issueid':'123','parentcomicid':'456','releasecomicid':'789'}
        pack=self.store.get('pack',self.body['pack_id']);pack['members'][0].update(kind='annual',releasecomicid='790')
        self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():
            cap=self.accept()
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_unknown_commit_response_never_mints_witness_or_replays(self):
        with self.writer.hold():
            cap=self.accept();real=sqlite3.connect
            class Lost:
                def __init__(self,db):self.db=db
                def execute(self,*a,**kw):return self.db.execute(*a,**kw)
                def commit(self):self.db.commit();raise RuntimeError('lost durable commit response')
                def close(self):self.db.close()
            def connect(path,*a,**kw):
                db=real(path,*a,**kw)
                return Lost(db) if path==self.c.database else db
            with patch.object(sqlite3,'connect',side_effect=connect),self.assertRaises(RuntimeError):f.finalize(cap)
            self.assertEqual(r._CORES[cap]['phase'],'finalization-uncertain')
            token=r._CORES[cap]['token'];self.assertIsNotNone(self.store.get(f.RECORD_KIND,token))
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_actual_commit_then_final_failure_keeps_evidence_without_witness(self):
        with self.writer.hold():
            cap=self.accept();real=f._checked;calls=[]
            def fail(packet,files):
                real(packet,files);calls.append(1)
                if len(calls)==3:raise RuntimeError('lost before final producer proof')
            with patch.object(f,'_checked',side_effect=fail),self.assertRaises(RuntimeError):f.finalize(cap)
            self.assertIsNotNone(self.store.get(f.RECORD_KIND,r._CORES[cap]['token']))
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_last_result_callback_target_drift_is_held(self):
        with self.writer.hold():
            cap=self.accept();real=f._result;fired=[]
            def late(packet):
                answer=real(packet);os.chmod(self.case.target,0o640);fired.append(True);return answer
            with patch.object(f,'_result',side_effect=late),self.assertRaises(o.Held):f.finalize(cap)
            self.assertEqual(fired,[True])
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_passive_last_result_callback_source_drift_is_held(self):
        with self.writer.hold():
            f.finalize(self.accept());real=f._result;fired=[]
            def late(packet):
                answer=real(packet);os.chmod(self.case.original,0o640);fired.append(True);return answer
            with patch.object(f,'_result',side_effect=late),self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)
            self.assertEqual(fired,[True])

    def test_final_helper_cannot_replace_passed_file_baseline(self):
        with self.writer.hold():
            cap=self.accept();real=f._checked;calls=[]
            def late(packet,files):
                real(packet,files);calls.append(1)
                if len(calls)==3:
                    os.chmod(self.case.target,0o640)
                    files[str(self.case.target)]=tuple(o.signature(self.case.target))
            with patch.object(f,'_checked',side_effect=late),self.assertRaises(o.Held):f.finalize(cap)

    def test_overlap_protocol_pending_prevents_finalization(self):
        with self.writer.hold():
            cap=self.accept();self.writer.root.joinpath('archive-repair-v1.terminal-pending').write_bytes(b'foreign')
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_missing_exact_member_never_invents_backend_identity(self):
        pack=self.store.get('pack',self.body['pack_id']);pack['members']=[];self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():
            cap=self.accept()
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_fresh_genuine_controller_and_writer_same_daemon_observe_original_commit(self):
        with self.writer.hold():f.finalize(self.accept())
        other=fixture.api.Controller(self.c.root,self.c.roots,tool_root=self.c.tool_root)
        writer=fixture.writers.Writer(self.writer.root)
        with writer.hold():answer=f.status_existing(other,writer,self.body)
        self.assertEqual(answer['outcome'],'fresh-retained-backend-finalized')
        self.assertFalse(answer['ordinary_import_grant'])

    def test_original_v4_vectors_are_not_refreshed_by_backend_finalization(self):
        with self.writer.hold():
            cap=self.accept();original=r._EVENTS[(str(self.c.root),r._CORES[cap]['token'])]
            f.finalize(cap)
            self.assertEqual(original,r._EVENTS[(str(self.c.root),r._CORES[cap]['token'])])
            with self.assertRaises(o.Held):r.status_existing(self.c,self.writer,self.body)
            self.assertEqual(f.status_existing(self.c,self.writer,self.body)['outcome'],'fresh-retained-backend-finalized')

    def test_legacy_confirmed_without_original_token_gets_distinct_fresh_phase(self):
        pack=self.store.get('pack',self.body['pack_id']);pack['phase']='confirmed';pack['members'][0]['phase']='confirmed'
        self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():answer=f.finalize(self.accept()).observe()
        saved=self.store.get('pack',self.body['pack_id'])
        self.assertEqual(saved['phase'],'review');self.assertEqual(saved['members'][0]['phase'],f.MEMBER_PHASE)
        self.assertNotIn('ordinary_import_token',saved['members'][0]);self.assertFalse(answer['ordinary_import_grant'])

    def test_member_destination_mismatch_is_not_rewritten(self):
        pack=self.store.get('pack',self.body['pack_id']);pack['members'][0]['destination']='/unrelated/library.cbz'
        self.store.set('pack',self.body['pack_id'],pack)
        with self.writer.hold():
            cap=self.accept()
            with self.assertRaises(o.Held):f.finalize(cap)

    def test_another_request_thread_same_daemon_reconciles_under_real_writer(self):
        with self.writer.hold():f.finalize(self.accept())
        outcomes=[];errors=[]
        def observe():
            try:
                controller=fixture.api.Controller(self.c.root,self.c.roots,tool_root=self.c.tool_root)
                writer=fixture.writers.Writer(self.writer.root)
                with writer.hold():outcomes.append(f.status_existing(controller,writer,self.body))
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=observe);thread.start();thread.join(10)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
        self.assertEqual(len(outcomes),1);self.assertFalse(outcomes[0]['ordinary_import_grant'])

    def test_replaced_same_byte_workflow_cannot_refresh_final_commit(self):
        with self.writer.hold():
            f.finalize(self.accept());path=self.c.database;before=path.read_bytes()
            moved=path.with_name('held-workflow.sqlite');path.rename(moved);path.write_bytes(before)
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def test_last_result_callback_pending_prevents_receipt(self):
        with self.writer.hold():
            cap=self.accept();real=f._result
            def late(packet):
                answer=real(packet);self.writer.pending.write_bytes(b'foreign');return answer
            with patch.object(f,'_result',side_effect=late),self.assertRaises(o.Held):f.finalize(cap)
            self.assertEqual(r._CORES[cap]['phase'],'finalization-uncertain')
            with self.assertRaises(o.Held):f.status_existing(self.c,self.writer,self.body)

    def source_capture_drift(self,role):
        # Isolate source-metadata fault in another real imported source tree.
        # No __file__ substitution and no writes to the frozen test input tree.
        with tempfile.TemporaryDirectory(prefix='retained-source-frame-') as tmp:
            root=Path(tmp);shutil.copytree(Path(__file__).parent,root/'config',
                ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
            script=root/'probe.py'
            script.write_text("""import os,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'config'))
import test_publication_retained_finalize as t
c=t.Finalize('runTest');c.setUp();f=t.f;real=os.read;fired=[]
role=sys.argv[1]
path=Path(f.__file__).parent if role=='parent' else Path(t.r.__file__)
original=path.stat().st_mode

def read(fd,size):
 raw=real(fd,size)
 if not fired and Path(os.readlink('/proc/self/fd/'+str(fd)))==Path(f.__file__):
  os.chmod(path,0o775 if role=='parent' else 0o640);fired.append(True)
 return raw
try:
 with c.writer.hold():
  cap=c.accept()
  try:
   with patch.object(f.os,'read',read):f.finalize(cap).observe()
   held=False
  except t.o.Held:held=True
  token=t.r._CORES[cap]['token']
  recorded=c.store.get(f.RECORD_KIND,token) is not None
 print(json.dumps({'fired':bool(fired),'held':held,'recorded':recorded}))
finally:
 os.chmod(path,original&0o7777);c.doCleanups()
""")
            answer=subprocess.run([sys.executable,'-B','-W','ignore::ResourceWarning',str(script),role],
                capture_output=True,text=True)
            self.assertEqual(answer.returncode,0,answer.stderr)
            result=json.loads(answer.stdout)
            self.assertTrue(result['fired']);self.assertTrue(result['held']);self.assertFalse(result['recorded'])

    def test_first_source_read_cannot_reseal_shared_ancestor(self):self.source_capture_drift('parent')
    def test_first_source_read_cannot_reseal_later_kernel_leaf(self):self.source_capture_drift('leaf')

if __name__=='__main__':unittest.main()

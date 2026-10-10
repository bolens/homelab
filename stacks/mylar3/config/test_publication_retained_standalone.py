"""Real public Controller/ordinary Writer/SQLite/archive; explicit host SDK fixture."""
import hashlib
import importlib
import json
import os
import select
import shutil
import sqlite3
import threading
import unittest
from unittest.mock import patch

import test_publication_retained_delivery as base
import publication_archive_owned as o

s=importlib.import_module('mylar.publication_retained_standalone')
a=importlib.import_module('mylar.comic_retained_standalone_action')

class Standalone(base.Retained):
    # Inherit fixture setup, not predecessor owning test cases.
    def setUp(self):
        super().setUp()
        self.source=self.cache/'download.cbz';shutil.copyfile(self.original,self.source)
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('ALTER TABLE ddl_info ADD COLUMN issueid TEXT')
            db.execute('UPDATE ddl_info SET pack=0,filename=?,issueid=?',(self.source.name,self.owner['issueid']));db.commit()
        self.value={'version':1,'kind':s.KIND,'ddl_id':self.ddl,'owner':self.owner,
            'source_sha256':hashlib.sha256(self.source.read_bytes()).hexdigest(),
            'target_sha256':hashlib.sha256(self.target.read_bytes()).hexdigest(),'review_sha256':''}
        self.config=self.case.root/'config.ini';self.config.write_bytes(b'[General]\npublic_fixture=true\n');os.chmod(self.config,0o600)
        self.mapping=self.case.root/'sdk-map.json';self.mapping.write_bytes(b'{}');os.chmod(self.mapping,0o600)
        self.review=self.case.root/'review.json';self.review.write_bytes(a.encoded({'version':1,'kind':'standalone-retained-review-v1',**{k:self.value[k] for k in ('ddl_id','owner','source_sha256','target_sha256')}}));os.chmod(self.review,0o600)
        self.value['review_sha256']=hashlib.sha256(self.review.read_bytes()).hexdigest()
        self.parent_in,self.child_out=os.pipe();self.child_in,self.parent_out=os.pipe()
        self.addCleanup(self.close_pipes)
        self.boot={'version':1,'kind':'standalone-retained-bootstrap-v1','nonce':'a'*64,'challenge':'c'*64,'parent_sha256':'d'*64,
            'request':self.value,'config_ref':self.ref(self.config),'source_map_ref':self.ref(self.mapping),'review_ref':self.ref(self.review),'data_root':str(self.case.root)}
        self.input=self.case.root/'input.json';self.input.write_bytes(a.encoded(self.boot));os.chmod(self.input,0o600)
        for module,name,value in ((s,'ENABLED',True),(a,'ENABLED',True),(a,'PARENT_SOURCE_SHA','d'*64)):
            c=patch.object(module,name,value);c.start();self.addCleanup(c.stop)
        self.channel=a.from_original_pipes(self.ref(self.input),self.child_in,self.child_out)

    def close_pipes(self):
        for fd in (self.parent_in,self.child_out,self.child_in,self.parent_out):
            try:os.close(fd)
            except OSError:pass

    def ref(self,p):return {'path':str(p),'signature9':list(o.signature(p)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}

    def init(self):return s.initialize(self.c,self.writer,self.value,conversation=self.channel)

    def ready(self,session):
        initialized=self.channel.initialized(session)
        refs=[self.ref(p) for p in (self.config,self.mapping,self.source,self.target)]
        value={'version':a.WIRE_VERSION,'protocol':a.PROTOCOL,'kind':'backup-ready','nonce':self.boot['nonce'],'sequence':2,
            'challenge':self.boot['challenge'],'payload':{'initialized_sha256':initialized,'backup_sha256':'e'*64,'original_refs':refs}}
        os.write(self.parent_out,a.encoded(value)+b'\n')
        # Drain original child frame; readiness peer in this unit is explicitly
        # synthetic. Real host copy/restore object belongs to the separate module.
        raw=bytearray()
        while (b:=os.read(self.parent_in,1))!=b'\n':raw.extend(b)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),initialized)
        return s.prepare_existing(session,self.channel)

    def test_standalone_positive_exact_noop_and_sole_workflow_record(self):
        source=self.source.read_bytes();target=self.target.read_bytes()
        with self.writer.hold():
            session=self.init();cap=self.ready(session);accepted=cap.accept();answer=cap.finalize();status=cap.status()
        self.assertEqual(answer,status);self.assertFalse(accepted['historical_import_ack']);self.assertFalse(answer['cleanup_grant'])
        self.assertEqual(source,self.source.read_bytes());self.assertEqual(target,self.target.read_bytes())
        with sqlite3.connect(self.c.database) as db:
            row=db.execute('SELECT value FROM records WHERE kind=? AND key=?',(s.RECORD_KIND,answer['token'])).fetchone()
        self.assertTrue(row);body=json.loads(row[0]);self.assertFalse(body['automatic_replay']);self.assertEqual(len(s._CORES[session]['workflow_sql']['rows']['records']),len(body['original_vectors']['workflow_sql']['rows']['records'])+1)
        self.assertEqual(body['request']['ddl_id'],self.ddl);self.assertNotIn('pack_id',body['request'])
        self.assertFalse((self.case.root/'ordinary-import-v1.sqlite').exists())

    def test_standalone_default_disabled(self):
        with self.writer.hold(),patch.object(s,'ENABLED',False),self.assertRaises(o.Held):self.init()

    def test_standalone_review_original_replaced(self):
        self.review.unlink();self.review.write_bytes(a.encoded({'version':1}))
        with self.writer.hold(),self.assertRaises((o.Held,ValueError)):self.init()

    def test_standalone_lost_final_response_same_session_only(self):
        def lost(raw):raise TimeoutError('disposable return loss')
        with self.writer.hold():
            cap=self.ready(self.init());cap.accept()
            with self.assertRaises(TimeoutError):cap.finalize(response_hook=lost)
            self.assertEqual(cap.status()['outcome'],'fresh-standalone-retained-finalized')
            fake=object.__new__(s.StandaloneAcceptance)
            with self.assertRaises(o.Held):fake.status()

    def test_standalone_original_source_replacement(self):
        with self.writer.hold():
            cap=self.ready(self.init());self.source.rename(self.cache/'aside.cbz');self.source.write_bytes(self.target.read_bytes())
            with self.assertRaises(o.Held):cap.accept()

    def test_standalone_late_final_validate_target_drift(self):
        with self.writer.hold():
            cap=self.ready(self.init());cap.accept();real=s._validate;fired=[]
            def late(c,*args,**kwargs):
                answer=real(c,*args,**kwargs)
                if c['phase']=='finalized':os.chmod(self.target,0o640);fired.append(True)
                return answer
            with patch.object(s,'_validate',late),self.assertRaises(o.Held):cap.finalize()
        self.assertTrue(fired)

    def test_standalone_pending_at_last_hash(self):
        with self.writer.hold():
            cap=self.ready(self.init());real=s.hashlib.sha256;fired=[]
            def late(raw=b''):
                answer=real(raw)
                if not fired and s._EVENTS[cap]['core']['phase']=='prepared':self.writer.pending.write_bytes(b'foreign');fired.append(True)
                return answer
            with patch.object(s.hashlib,'sha256',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_standalone_lost_accept_return_then_actual_finalize(self):
        with self.writer.hold():
            cap=self.ready(self.init())
            with self.assertRaises(TimeoutError):cap.accept(response_hook=lambda raw:(_ for _ in ()).throw(TimeoutError('lost')))
            self.assertEqual(cap.finalize()['outcome'],'fresh-standalone-retained-finalized')

    def test_standalone_saved_json_and_foreign_ready_cannot_make_capability(self):
        with self.writer.hold():
            session=self.init()
            with self.assertRaises(o.Held):s.prepare_existing(session,{'backup_sha256':'e'*64})
            with self.assertRaises(o.Held):s.StandaloneAcceptance()

    def test_standalone_original_library_other_claim(self):
        other=self.case.library/'other.cbz';shutil.copyfile(self.source,other)
        with self.writer.hold():
            cap=self.ready(self.init());os.chmod(other,0o640)
            with self.assertRaises(o.Held):cap.accept()

    def test_standalone_early_library_mutation_not_recaptured(self):
        real=o.sdk;fired=[]
        def late():
            modules=real();os.chmod(self.target,0o640);fired.append(True);return modules
        with self.writer.hold(),patch.object(o,'sdk',late),self.assertRaises(o.Held):self.init()
        self.assertTrue(fired)

    def test_standalone_early_selector_mutation_not_recaptured(self):
        real=o.sdk;fired=[]
        def late():
            modules=real();self.value['ddl_id']='57';fired.append(True);return modules
        with self.writer.hold(),patch.object(o,'sdk',late),self.assertRaises(o.Held):self.init()
        self.assertTrue(fired)

    def test_standalone_annual_exact_release_owner(self):
        with sqlite3.connect(self.c.native_database) as db:
            db.execute('DELETE FROM issues WHERE IssueID=?',(self.owner['issueid'],))
            db.execute('INSERT INTO annuals(IssueID,ComicID,ReleaseComicID,Location,Status,Deleted) VALUES(?,?,?,?,?,?)',
                (self.owner['issueid'],self.owner['parentcomicid'],'789',self.target.name,'Downloaded',0));db.commit()
        owner=dict(self.owner,table='annuals',releasecomicid='789');self.value['owner']=owner
        self.review.write_bytes(a.encoded({'version':1,'kind':'standalone-retained-review-v1',**{k:self.value[k] for k in ('ddl_id','owner','source_sha256','target_sha256')}}))
        self.value['review_sha256']=hashlib.sha256(self.review.read_bytes()).hexdigest()
        self.boot['request']=self.value;self.boot['review_ref']=self.ref(self.review);self.input.write_bytes(a.encoded(self.boot))
        self.channel=a.from_original_pipes(self.ref(self.input),self.child_in,self.child_out)
        with self.writer.hold():cap=self.ready(self.init());cap.accept();answer=cap.finalize()
        self.assertEqual(answer['outcome'],'fresh-standalone-retained-finalized')

    def test_standalone_pending_before_finalize_holds_without_record(self):
        with self.writer.hold():
            cap=self.ready(self.init());cap.accept();self.writer.pending.write_bytes(b'foreign')
            with self.assertRaises(o.Held):cap.finalize()
        with sqlite3.connect(self.c.database) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records WHERE kind=?',(s.RECORD_KIND,)).fetchone(),(0,))

    def test_standalone_late_cap_registry_removal(self):
        with self.writer.hold():
            cap=self.ready(self.init());cap.accept();cap.finalize();real=s.os.listdir;fired=[]
            def late(path):
                answer=real(path)
                if not fired:s._EVENTS.pop(cap);fired.append(True)
                return answer
            with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):cap.status()
        self.assertTrue(fired)

    def test_standalone_late_logical_core_mutation(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);cap.accept();cap.finalize();real=s.os.listdir;fired=[]
            def late(path):
                answer=real(path)
                if not fired:s._CORES[session]['request']['ddl_id']='57';fired.append(True)
                return answer
            with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):cap.status()
        self.assertTrue(fired)

    def test_standalone_late_actual_pipe_callback_source_drift(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);cap.accept();cap.finalize();real=a.os.fstat;fired=[]
            def late(fd):
                answer=real(fd)
                if fd==self.child_out and not fired:os.chmod(self.source,0o640);fired.append(True)
                return answer
            with patch.object(a.os,'fstat',late),self.assertRaises((o.Held,ValueError)):a._close(self.channel)
        self.assertTrue(fired)

    def test_standalone_full_original_pipe_waits_for_parent_exit_release(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);cap.accept();answer=cap.finalize()
            frames=[];errors=[]
            def parent():
                try:
                    for seq,kind in ((3,'observed'),(5,'observed-final-ACK')):
                        raw=bytearray()
                        while True:
                            ready,_,_=select.select([self.parent_in],[],[],5)
                            if not ready:raise TimeoutError('owning fixture pipe timeout')
                            b=os.read(self.parent_in,1)
                            if b==b'\n':break
                            if not b:raise EOFError()
                            raw.extend(b)
                        frame=a.decode(raw);frames.append(frame);self.assertEqual(frame['sequence'],seq);self.assertEqual(frame['kind'],kind)
                        sha=hashlib.sha256(raw).hexdigest() if seq==3 else frames[1]['payload']['observed_sha256']
                        response={'version':a.WIRE_VERSION,'protocol':a.PROTOCOL,'kind':'observed-release' if seq==3 else 'observed-exit',
                            'nonce':self.boot['nonce'],'sequence':seq+1,'challenge':self.boot['challenge'],'payload':{'observed_sha256':sha}}
                        # Actual file/SQL reopening; parent runtime observations and
                        # backup peer remain explicitly synthetic disposable facts.
                        self.assertEqual(self.ref(self.target)['sha256'],self.value['target_sha256'])
                        with sqlite3.connect(self.c.database) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records WHERE kind=?',(s.RECORD_KIND,)).fetchone(),(1,))
                        os.write(self.parent_out,a.encoded(response)+b'\n')
                except BaseException as exc:errors.append(exc)
            thread=threading.Thread(target=parent);thread.start()
            self.assertEqual(self.channel.observed(cap,answer),answer);thread.join(5)
            self.assertFalse(thread.is_alive());self.assertFalse(errors);self.assertEqual(len(frames),2)
            self.assertEqual(a._CHANNELS[self.channel]['sequence'],6)


    def test_standalone_completed_pack_true_is_not_standalone(self):
        with sqlite3.connect(self.c.native_database) as db:db.execute('UPDATE ddl_info SET pack=1');db.commit()
        with self.writer.hold(),self.assertRaises(o.Held):self.init()

    def test_standalone_completed_basename_escape_is_not_selector(self):
        with sqlite3.connect(self.c.native_database) as db:db.execute('UPDATE ddl_info SET filename=?',('../download.cbz',));db.commit()
        with self.writer.hold(),self.assertRaises(o.Held):self.init()

    def test_standalone_different_retained_pages_hold(self):
        with base.zipfile.ZipFile(self.source,'w') as z:z.writestr('01.jpg',b'different original pages')
        self.value['source_sha256']=hashlib.sha256(self.source.read_bytes()).hexdigest()
        with self.writer.hold(),self.assertRaises((o.Held,ValueError)):self.init()

    def test_standalone_ready_wrong_original_ref_holds(self):
        with self.writer.hold():
            session=self.init();initialized=self.channel.initialized(session)
            refs=[self.ref(p) for p in (self.config,self.mapping,self.source,self.target)];refs[-1]['signature9'][1]+=1
            packet={'version':a.WIRE_VERSION,'protocol':a.PROTOCOL,'kind':'backup-ready','nonce':self.boot['nonce'],'sequence':2,'challenge':self.boot['challenge'],
                'payload':{'initialized_sha256':initialized,'backup_sha256':'e'*64,'original_refs':refs}}
            os.write(self.parent_out,a.encoded(packet)+b'\n')
            with self.assertRaises(ValueError):s.prepare_existing(session,self.channel)
            self.assertEqual(s._CORES[session]['phase'],'initialized')

    def test_standalone_actual_purpose_mutation_after_physical_callback(self):
        with self.writer.hold():
            cap=self.ready(self.init());real=s.os.listdir;fired=[]
            def late(path):
                answer=real(path)
                if not fired:self.writer.local[1].allow_pending=True;fired.append(True)
                return answer
            try:
                with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):cap.accept()
            finally:self.writer.local[1].allow_pending=False
        self.assertTrue(fired)

    def test_standalone_original_backup_digest_cannot_refresh(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);real=s.os.listdir;fired=[]
            def late(path):
                answer=real(path)
                if not fired:s._CORES[session]['backup_digest']='f'*64;fired.append(True)
                return answer
            with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_standalone_actual_catalog_commit_unknown_keeps_uncertainty(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);real=s.sqlite3.connect
            class LostCommit:
                def __init__(self,db):self.db=db
                def execute(self,*args,**kwargs):return self.db.execute(*args,**kwargs)
                def close(self):return self.db.close()
                def commit(self):self.db.commit();raise TimeoutError('real commit response lost')
            def connect(path,*args,**kwargs):
                db=real(path,*args,**kwargs)
                return LostCommit(db) if path==self.c.native_database else db
            with patch.object(s.sqlite3,'connect',connect),self.assertRaises(TimeoutError):cap.accept()
            self.assertEqual(s._CORES[session]['phase'],'uncertain');self.assertIsNone(s._EVENTS[cap]['event'])
            with self.assertRaises(o.Held):cap.finalize()
            with self.assertRaises(o.Held):cap.status()

    def test_standalone_actual_backend_commit_unknown_cannot_resume(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);cap.accept();real=s.sqlite3.connect
            class LostCommit:
                def __init__(self,db):self.db=db
                def execute(self,*args,**kwargs):return self.db.execute(*args,**kwargs)
                def close(self):return self.db.close()
                def commit(self):self.db.commit();raise TimeoutError('real backend commit response lost')
            def connect(path,*args,**kwargs):
                db=real(path,*args,**kwargs)
                return LostCommit(db) if path==self.c.database else db
            with patch.object(s.sqlite3,'connect',connect),self.assertRaises(TimeoutError):cap.finalize()
            self.assertEqual(s._CORES[session]['phase'],'final-uncertain')
            with self.assertRaises(o.Held):cap.status()
            with self.assertRaises(o.Held):cap.finalize()
        with sqlite3.connect(self.c.database) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM records WHERE kind=?',(s.RECORD_KIND,)).fetchone(),(1,))

    def test_standalone_wire_bound_holds_before_catalog_mutation(self):
        with self.writer.hold():
            session=self.init();before=self.c.native_database.read_bytes()
            with patch.object(a,'LIMIT',16),self.assertRaises(ValueError):self.channel.initialized(session)
            self.assertEqual(self.c.native_database.read_bytes(),before)


    def test_standalone_body_publication_cannot_emit_arbitrary_JSON(self):
        with self.writer.hold():
            session=self.init()
            with self.assertRaises(o.Held):s.publish_body(session,'initialized',b'{}')
            self.assertFalse((self.c.root/s.CARRIER).exists())

    def test_standalone_complete_future_capacity_refuses_before_catalog_event(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);before=self.c.native_database.read_bytes()
            with patch.object(s,'BODY_LIMIT',1024),self.assertRaises(o.Held):cap.accept()
            self.assertEqual(before,self.c.native_database.read_bytes())
            self.assertEqual(s._CORES[session]['phase'],'prepared');self.assertIsNone(s._EVENTS[cap]['event'])

    def test_standalone_last_result_decode_target_change_is_held(self):
        with self.writer.hold():
            cap=self.ready(self.init());real=s.json.loads;fired=[]
            def decode(value,*args,**kwargs):
                answer=real(value,*args,**kwargs)
                if type(answer) is dict and answer.get('outcome')=='fresh-standalone-retained-accepted':
                    os.chmod(self.target,0o640);fired.append(True)
                return answer
            with patch.object(s.json,'loads',decode),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_standalone_return_callback_drift_is_held(self):
        def callback(raw):os.chmod(self.target,0o640)
        with self.writer.hold():
            cap=self.ready(self.init())
            with self.assertRaises(o.Held):cap.accept(response_hook=callback)
            with self.assertRaises(o.Held):cap.finalize()

    def test_standalone_publication_registry_cannot_reseal_directory(self):
        with self.writer.hold():
            session=self.init();self.ready(session);core=s._CORES[session];real=s.os.listdir;fired=[]
            def late(path):
                names=real(path)
                if str(path)==str(core['folder']) and not fired:
                    artifact=s._ARTIFACTS[session];os.chmod(artifact['directory'],0o750)
                    artifact['directory_after9']=tuple(o.signature(artifact['directory']));fired.append(True)
                return names
            with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):s._raw(core,s._SEALS[session])
        self.assertTrue(fired)

    def test_standalone_full_24_table_SQL_body_exceeds_wire_without_dropping_rows(self):
        with sqlite3.connect(self.c.native_database) as db:
            count=db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            for index in range(24-count):
                db.execute('CREATE TABLE extra_%d(id INTEGER PRIMARY KEY,payload TEXT)'%index)
                db.execute('INSERT INTO extra_%d VALUES(?,?)'%index,(1,'selected-public-fixture-'+'x'*240000))
            db.commit()
        self.test_standalone_full_original_pipe_waits_for_parent_exit_release()
        core=a._CHANNELS[self.channel]['kernel'];folder=self.c.root/s.CARRIER/core['token']
        initial_raw=(folder/'initialized-body.json').read_bytes();final_raw=(folder/'observed-body.json').read_bytes()
        initial=json.loads(initial_raw);final=json.loads(final_raw)
        self.assertGreater(len(initial_raw),a.LIMIT);self.assertGreater(len(final_raw),a.LIMIT)
        self.assertEqual(len(initial['original_vectors']['sql']['rows']),24)
        self.assertEqual(initial['original_vectors']['sql'],final['original_vectors']['sql'])
        self.assertEqual(final['original_vectors']['workflow_sql']['rows']['records'][-1],
            s._CORES[core['session']]['workflow_sql']['rows']['records'][-1])
        self.assertTrue(all(len(rows)==1 for name,rows in final['original_vectors']['sql']['rows'].items() if name.startswith('extra_')))



    def test_standalone_body_original_created_FD_mode_before_fsync(self):
        with self.writer.hold():
            session=self.init();real=s.r.os.fsync;fired=[]
            def late(fd):
                if os.readlink('/proc/self/fd/'+str(fd)).endswith('/initialized-body.json') and not fired:
                    os.fchmod(fd,0o640);fired.append(True)
                return real(fd)
            with patch.object(s.r.os,'fsync',late),self.assertRaises(o.Held):self.channel.initialized(session)
        self.assertTrue(fired);self.assertEqual(a._CHANNELS[self.channel]['sequence'],0)

    def test_standalone_initial_body_cannot_be_republished(self):
        with self.writer.hold():
            session=self.init();self.ready(session)
            with self.assertRaises((o.Held,ValueError)):self.channel.initialized(session)

    def test_standalone_original_body_replacement_holds_catalog_unchanged(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);core=s._CORES[session]
            path=self.c.root/s.CARRIER/core['token']/'initialized-body.json';raw=path.read_bytes()
            before=self.c.native_database.read_bytes();path.rename(path.with_name('foreign-body.json'));path.write_bytes(raw);os.chmod(path,0o600)
            with self.assertRaises(o.Held):cap.accept()
            self.assertEqual(before,self.c.native_database.read_bytes())



    def test_standalone_directory_projection_exact_birth_copy_SQL_chains(self):
        with self.writer.hold():
            session=self.init();initialized=s._SEALS[session];j=initialized['journal'];parent=initialized['sql_parents'][0]
            self.assertIsNone(j['before9']);self.assertEqual(j['journal_birth9'][8],2)
            self.assertEqual(j['after9'][8],j['journal_birth9'][8]+1)
            self.assertEqual(parent['initialized9'][8],parent['pre_initialize9'][8]+1)
            self.assertIsNone(parent['backup9']);self.assertEqual(j['initialized_names'],('intent.json',))
            cap=self.ready(session);prepared=s._SEALS[session];row=prepared['sql_parents'][0]
            self.assertEqual(row['backup9'][8],row['initialized9'][8]+1)
            copies=prepared['journal']['preservation'];self.assertEqual([v['name'] for v in copies],['target-preserved.cbz','target-restored.cbz'])
            self.assertEqual(copies[0]['before9'],j['initialized9']);self.assertEqual(copies[1]['before9'],copies[0]['after9'])
            cap.accept();cap.finalize();final=s._SEALS[session];row=final['sql_parents'][0]
            self.assertEqual(row['native_noop']['before9'],row['backup9'])
            self.assertEqual(row['workflow_cas']['before9'],row['native_noop']['after9'])
            self.assertEqual(row['workflow_cas']['after9'][8],row['backup9'][8])
            self.assertEqual(final['journal']['accepted']['before9'],copies[1]['after9'])
            self.assertEqual(final['journal']['accepted']['name'],'accepted.json')
            self.assertEqual(final['journal']['accepted']['file_ref']['sha256'],s._EVENTS[cap]['event'][4])

    def test_standalone_existing_carrier_and_journal_null_branches_are_disjoint(self):
        for name in (s.NAME,s.CARRIER):
            path=self.c.root/name;path.mkdir(mode=0o700);old=path/('f'*64);old.mkdir(mode=0o700)
            (old/'public-fixture.json').write_bytes(b'{}');os.chmod(old/'public-fixture.json',0o600)
        with self.writer.hold():
            session=self.init();j=s._SEALS[session]['journal'];parent=s._SEALS[session]['sql_parents'][0]
            self.assertIsNotNone(j['before9']);self.assertIsNone(j['journal_birth9'])
            self.assertEqual(parent['initialized9'][8],parent['pre_initialize9'][8])
            cap=self.ready(session);row=s._SEALS[session]['sql_parents'][0]
            self.assertEqual(row['backup9'],row['initialized9']);cap.accept();cap.finalize()
        for name in (s.NAME,s.CARRIER):self.assertEqual((self.c.root/name/('f'*64)/'public-fixture.json').read_bytes(),b'{}')

    def test_standalone_body_fsync_transient_directory_change_cannot_refresh_after9(self):
        with self.writer.hold():
            session=self.init();real=s.os.fsync;fired=[]
            def late(fd):
                path=os.readlink('/proc/self/fd/'+str(fd))
                if path.endswith('/initialized-body.json') and not fired:
                    folder=path.rsplit('/',1)[0];os.chmod(folder,0o750);os.chmod(folder,0o700);fired.append(True)
                return real(fd)
            with patch.object(s.os,'fsync',late),self.assertRaises(o.Held):self.channel.initialized(session)
        self.assertTrue(fired);self.assertEqual(a._CHANNELS[self.channel]['sequence'],0)

    def test_standalone_native_readback_transient_parent_change_is_not_SQL_successor(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);real=s.r._sql;fired=[]
            def late(path,stamp):
                answer=real(path,stamp)
                if s._CORES[session]['phase']=='uncertain' and path==self.c.native_database and not fired:
                    os.chmod(path.parent,0o750);os.chmod(path.parent,0o700);fired.append(True)
                return answer
            with patch.object(s.r,'_sql',late),self.assertRaises(o.Held):cap.accept()
            self.assertIsNone(s._EVENTS[cap]['event'])
        self.assertTrue(fired)

    def test_standalone_SQL_parent_foreign_namespace_is_held_before_catalog(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);before=self.c.native_database.read_bytes()
            (self.c.native_database.parent/'foreign-control').write_bytes(b'public')
            with self.assertRaises(o.Held):cap.accept()
            self.assertEqual(before,self.c.native_database.read_bytes())

    def test_standalone_directory_registry_removal_after_last_census_holds(self):
        with self.writer.hold():
            session=self.init();cap=self.ready(session);core=s._CORES[session];real=s.os.listdir;fired=[]
            def late(path):
                answer=real(path)
                if str(path)==str(core['folder']) and not fired:s._DIRS.pop(session);fired.append(True)
                return answer
            with patch.object(s.os,'listdir',late),self.assertRaises(o.Held):cap.accept()
        self.assertTrue(fired)

    def test_last_channel_need_cannot_change_original_config(self):
        real=a.need;fired=[]
        def late(ok,why):
            answer=real(ok,why)
            if why=='standalone-channel-original-pipe-final' and not fired:
                fired.append(True);self.config.chmod(0o640)
            return answer
        with patch.object(a,'need',late),self.assertRaises(ValueError):a._close(self.channel)
        self.assertTrue(fired)

    def test_last_session_need_cannot_change_original_config(self):
        with self.writer.hold():
            self.ready(self.init());real=a.need;fired=[]
            def late(ok,why):
                answer=real(ok,why)
                if why=='standalone-channel-kernel-purpose-final' and not fired:
                    fired.append(True);self.config.chmod(0o640)
                return answer
            with patch.object(a,'need',late),self.assertRaises(ValueError):a._close(self.channel)
        self.assertTrue(fired)

    def test_last_session_need_cannot_create_original_pending(self):
        with self.writer.hold():
            self.ready(self.init());real=a.need;fired=[]
            def late(ok,why):
                answer=real(ok,why)
                if why=='standalone-channel-kernel-purpose-final' and not fired:
                    fired.append(True);self.writer.pending.write_bytes(b'foreign')
                return answer
            with patch.object(a,'need',late),self.assertRaises(ValueError):a._close(self.channel)
        self.assertTrue(fired)

    def test_last_session_need_cannot_remove_original_registry(self):
        with self.writer.hold():
            self.ready(self.init());real=a.need;fired=[]
            def late(ok,why):
                answer=real(ok,why)
                if why=='standalone-channel-kernel-purpose-final' and not fired:
                    fired.append(True);a._SESSIONS.pop(self.channel)
                return answer
            with patch.object(a,'need',late),self.assertRaises(ValueError):a._close(self.channel)
        self.assertTrue(fired)

    def test_actual_final_exit_closure_rejects_last_need_source_drift(self):
        real=a.need;fired=[];count=[]
        def late(ok,why):
            answer=real(ok,why)
            if why=='standalone-channel-kernel-purpose-final' and a._CHANNELS[self.channel]['sequence']==6:
                count.append(1)
                if len(count)==2:
                    self.source.chmod(0o640);fired.append(True)
            return answer
        with patch.object(a,'need',late),self.assertRaises((ValueError,o.Held)):
            self.test_standalone_full_original_pipe_waits_for_parent_exit_release()
        self.assertTrue(fired);self.assertEqual(a._CHANNELS[self.channel]['sequence'],6)

    def test_last_channel_need_cannot_replace_actual_same_number_pipe(self):
        real=a.need;fired=[];original_fd=os.dup(self.child_in);foreign_in,foreign_out=os.pipe()
        def late(ok,why):
            answer=real(ok,why)
            if why=='standalone-channel-original-pipe-final' and not fired:
                os.dup2(foreign_in,self.child_in);fired.append(True)
            return answer
        try:
            with patch.object(a,'need',late),self.assertRaises(ValueError):a._close(self.channel)
        finally:
            os.dup2(original_fd,self.child_in)
            for fd in (original_fd,foreign_in,foreign_out):os.close(fd)
        self.assertTrue(fired)


# Explicitly remove inherited pack tests: this is standalone coverage, not a
# duplicate report of predecessor suites.
for name in tuple(base.Retained.__dict__):
    if name.startswith('test_'):setattr(Standalone,name,None)

if __name__=='__main__':unittest.main()

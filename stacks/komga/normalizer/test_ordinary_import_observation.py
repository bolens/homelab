"""Actual worker Authority/Writer/SQLite; explicit authenticated HTTP fixture.

The fixture returns source-closed native observation shapes, not a claim of
installed network authentication. Owning native rename/metadata export positives
run separately in the native suite. No Writer or Authority type is substituted.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import ordinary_import_observation as observation
import ordinary_import_ack as ack_reader
import publication_guard as guard
from maintenance import Maintenance
from test_publication_guard import AuthorityFixture


class Bridge(AuthorityFixture,unittest.TestCase):
    def setUp(self):
        AuthorityFixture.setUp(self)
        if getattr(self,'ANNUAL',False):
            with sqlite3.connect(self.catalog) as db:
                db.execute('DELETE FROM issues');db.execute('INSERT INTO annuals VALUES (?,?,?,?,?,0)',('123','456','789',self.source.name,'Downloaded'))
            self.owner=dict(table='annuals',issueid='123',parentcomicid='456',releasecomicid='789');self.native_owner=self.owner;self.seed()
        self.state=self.root/'state';self.state.mkdir();maint=self.state/'maintenance';maint.mkdir();(maint/'imports').mkdir()
        (self.config/'config.ini').write_text('[fixture]\napi_key='+'x'*32+'\n');(self.config/'config.ini').chmod(0o600)
        self.worker=SimpleNamespace(state=self.state,roots=[self.library],config={'writer_state':str(self.writer.root),
            'mylar':{'config_dir':str(self.config),'url':'http://native-fixture.invalid'},
            'publication_roots':[dict(native=str(self.native_root),worker=str(self.library))]})
        self.m=Maintenance.__new__(Maintenance);self.m.worker=self.worker;self.m.state=maint;self.m.roots=[self.library]
        self.m.settings={'ddl_cache':str(self.root/'cache'),'mylar_ddl_cache':'/native-cache'}
        actual=guard.scope
        @contextmanager
        def portable(*args,**kwargs):
            with actual(*args,**kwargs) as authority:
                authority.tool_root=self.tool
                yield authority
        self.scope=portable
        with self.writer.hold(),self.scope(self.worker,self.writer):
            proof=guard.import_check(self.worker,self.candidate,{'issueid':'123','comicid':'456'})
        self.match={'issueid':'123','comicid':'456'}
        self.record=dict(source=str(self.candidate),sha256=proof['inventory']['source_sha256'],phase='submitted',match=self.match,stage=str(self.candidate),
            publication=dict(source=proof,stage=proof))
        self.token=hashlib.sha256(os.fsencode(self.candidate)+self.record['sha256'].encode()).hexdigest()
        self.receipt=maint/'imports'/(self.token+'.json');self.receipt.write_text(json.dumps(self.record));self.receipt.chmod(0o600)
        queued=dict(token=self.token,owner=self.owner,source=str(self.native_root/self.candidate.name),payload=proof['inventory']['payload'],
            source_sha256=proof['inventory']['source_sha256'],census=proof['authority']['census'])
        self.attempt=dict(token=self.token,proof=queued,owner=self.owner,payload=queued['payload'],destination=str(self.native_root/'before.cbz'))
        signature,checksum=guard.evidence.file_hash(self.source)
        # Historical ACK fixture only. No original completion/rename is minted;
        # native owning positive is separately tested with actual producers.
        old=list(signature);old[4]+=1
        self.ack=dict(owner=self.owner,destination=dict(signature=old,sha256=checksum))
        self.original=(json.dumps(self.attempt),json.dumps(self.ack))
        self.history=self.config/'ordinary-import-v1.sqlite'
        with sqlite3.connect(self.history) as db:
            db.execute('CREATE TABLE completions(token TEXT,attempt TEXT,ack TEXT)');db.execute('INSERT INTO completions VALUES (?,?,?)',(self.token,*self.original))
        self.history.chmod(0o600)
        p=patch.object(observation,'ENABLED',True);p.start();self.addCleanup(p.stop)
        observation._PENDING.clear();observation._LIVE.clear();self.addCleanup(observation._PENDING.clear);self.addCleanup(observation._LIVE.clear)
        observation._SELECTORS.clear();observation._RESULTS.clear();self.addCleanup(observation._SELECTORS.clear);self.addCleanup(observation._RESULTS.clear)
        self.calls=[]
    def confirmed(self,**kwargs):
        with self.writer.hold(),self.scope(self.worker,self.writer):return ack_reader.confirmed(self.m,self.candidate,self.match,self.source,**kwargs)
    def prepare(self):self.assertIsNone(self.confirmed());self.assertEqual(len(observation._PENDING),1)
    def response(self,request):
        native_dir=Path(__file__).parent/'ordinary_observation_fixtures/native'
        if not native_dir.is_dir():native_dir=Path(__file__).parents[2]/'mylar3/config'
        source_names=('ordinary_import_continuity','ordinary_import_history','publication_rename','publication_transaction','publication_guard','publication_native','native_writers','media_writer','ordinary_import_observation','api')
        sources=[]
        for name in source_names:
            path=native_dir/(name+'.py');vector,digest=guard.evidence.file_hash(path);sources.append(dict(path=str(path),signature=vector,sha256=digest))
        # Data/Writer/target paths are native spellings of the same original
        # disposable files; source leaves stay in the native producer namespace.
        files=list(sources)
        for path,native in ((self.catalog,'/native-config/mylar.db'),(self.history,'/native-config/ordinary-import-v1.sqlite'),
                            (self.source,str(self.native_root/self.source.name))):
            vector,digest=guard.evidence.file_hash(path);files.append(dict(path=native,signature=vector,sha256=digest))
        return dict(version=1,kind='ordinary-import-current-observation',nonce=request['nonce'],request_sha256=guard.evidence.canonical_digest(request),
            token=request['token'],owner=request['owner'],native_destination=request['destination'],native_data_root='/native-config',
            original_attempt_sha256=request['attempt_sha256'],original_ack_sha256=request['ack_sha256'],current_target=dict(request['target'],payload=request['payload']),
            native_sources=sources,evidence=dict(files=files,nodes=[],claims=[],absent=[],namespaces=[]),rights=dict(mutation=False,replay=False,cleanup=False,index_acceptance=False))
    def transport(self,base,route,form=None,**kwargs):
        self.assertFalse(getattr(self.writer.local[1],'depth',0));self.calls.append(form['cmd'])
        if form['cmd']=='getHealth':return {'success':True,'data':{'workflow':{'ordinary_import_observation':1}}}
        self.assertEqual(form['cmd'],'ordinaryImportObservation');self.assertTrue(kwargs.get('text'));self.assertEqual(kwargs.get('limit'),4*1024*1024)
        return json.dumps({'success':True,'data':self.response(json.loads(form['request']))})
    def dispatch(self,transport=None):
        with patch('publication_guard.scope',self.scope),patch('maintenance.request',transport or self.transport):return observation.dispatch(self.m)
    def test_locked_prepare_unlocked_transport_locked_consume_keeps_ack(self):
        self.prepare();self.assertEqual(self.dispatch(),1);self.assertEqual(self.confirmed(),self.token);self.assertEqual(self.calls,['getHealth','ordinaryImportObservation'])
        with sqlite3.connect(self.history) as db:self.assertEqual(tuple(db.execute('SELECT attempt,ack FROM completions').fetchone()),self.original)
    def test_replaced_owning_authenticated_return_method_cannot_mint_witness(self):
        self.prepare()
        with patch.object(Maintenance,'mylar_observation',lambda *_:b'{"success":true,"data":{}}'):
            self.assertEqual(self.dispatch(),0)
        self.assertFalse(observation._LIVE)
    def test_replaced_owning_return_after_dispatch_cannot_consume_witness(self):
        self.prepare();self.assertEqual(self.dispatch(),1)
        with patch.object(Maintenance,'mylar_observation',lambda *_:b'{}'):
            self.assertIsNone(self.confirmed())
        self.assertFalse(observation._LIVE)
    def test_live_observation_never_permits_cleanup(self):
        self.prepare();self.assertEqual(self.dispatch(),1);self.assertIsNone(self.confirmed(cleanup=True))
    def test_saved_response_cannot_reconstruct_witness(self):
        self.prepare();self.dispatch();observation._LIVE.clear();self.assertIsNone(self.confirmed())
    def test_lost_response_does_not_retry(self):
        self.prepare()
        def lost(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':raise OSError('lost response')
            return result
        self.assertEqual(self.dispatch(lost),0);self.assertEqual(self.dispatch(),0);self.assertIsNone(self.confirmed())
    def test_response_wrong_token_is_held(self):
        self.prepare();real=self.response
        def bad(request):value=real(request);value['token']='a'*64;return value
        with patch.object(self,'response',bad):self.assertEqual(self.dispatch(),1)
        self.assertIsNone(self.confirmed())
    def test_response_wrong_annual_owner_is_held(self):
        self.prepare();real=self.response
        def bad(request):value=real(request);value['owner']=dict(value['owner'],table='annuals',releasecomicid='999');return value
        with patch.object(self,'response',bad):self.dispatch()
        self.assertIsNone(self.confirmed())
    def test_pending_after_transport_is_held(self):
        self.prepare()
        def late(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':(self.writer.root/'release-v1.pending').write_bytes(b'foreign')
            return result
        self.assertEqual(self.dispatch(late),0)
        with self.assertRaises((ValueError,guard.Unavailable)):self.confirmed()
    def test_original_receipt_replaced_after_transport_is_held(self):
        self.prepare()
        def late(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':
                raw=self.receipt.read_bytes();self.receipt.unlink();self.receipt.write_bytes(raw);self.receipt.chmod(0o600)
            return result
        self.assertEqual(self.dispatch(late),0)
    def test_last_close_callback_target_change_is_held(self):
        self.prepare();self.dispatch();real=observation._close;fired=[]
        def late(frame):real(frame);self.source.chmod(0o640);fired.append(True)
        with patch.object(observation,'_close',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def native_original_files(self, *, writer=False):
        folder=self.writer.root if writer else self.config
        paths=[folder/'ordinary-terminal.json',folder/'ordinary-terminal-later.json']
        for path in paths:path.write_bytes(b'original native terminal');path.chmod(0o600)
        original=self.response
        def reply(request):
            value=original(request)
            for path in paths:
                signature,digest=guard.evidence.file_hash(path)
                native='/native-config/media-writer/' if writer else '/native-config/'
                value['evidence']['files'].append(dict(path=native+path.name,signature=signature,sha256=digest))
            return value
        with patch.object(self,'response',reply):self.prepare();self.assertEqual(self.dispatch(),1)
        return paths
    def test_additional_native_original_leaves_are_retained_without_refresh(self):
        self.native_original_files();self.assertEqual(self.confirmed(),self.token)
    def test_native_first_file_hash_callback_cannot_reseal_changed_mode(self):
        first,_=self.native_original_files();real=guard.evidence.file_hash;fired=[]
        def late(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if Path(path)==first and not fired:first.chmod(0o640);fired.append(True)
            return value
        with patch.object(guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_native_first_hash_callback_cannot_reseal_samebytes_replacement(self):
        first,_=self.native_original_files();real=guard.evidence.file_hash;fired=[]
        def late(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if Path(path)==first and not fired:
                raw=first.read_bytes();first.rename(first.with_suffix('.retained'));first.write_bytes(raw);first.chmod(0o600);fired.append(True)
            return value
        with patch.object(guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_native_later_leaf_original_is_copied_before_first_hash_callback(self):
        first,later=self.native_original_files();real=guard.evidence.file_hash;fired=[]
        def late(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if Path(path)==first and not fired:later.chmod(0o640);fired.append(True)
            return value
        with patch.object(guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_native_later_file_hash_callback_cannot_reseal_changed_mode(self):
        _,later=self.native_original_files();real=guard.evidence.file_hash;fired=[]
        def late(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if Path(path)==later and not fired:later.chmod(0o640);fired.append(True)
            return value
        with patch.object(guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_native_writer_control_leaf_hash_callback_cannot_reseal(self):
        first,_=self.native_original_files(writer=True);real=guard.evidence.file_hash;fired=[]
        def late(path,*args,**kwargs):
            value=real(path,*args,**kwargs)
            if Path(path)==first and not fired:first.chmod(0o640);fired.append(True)
            return value
        with patch.object(guard.evidence,'file_hash',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_last_receiver_capture_callback_preserves_native_original(self):
        first,_=self.native_original_files();real=observation._capture;fired=[]
        def late(paths,*args,**kwargs):
            value=real(paths,*args,**kwargs)
            if first in list(map(Path,paths)) and not fired:first.chmod(0o640);fired.append(True)
            return value
        with patch.object(observation,'_capture',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired)
    def test_native_missing_catalog_claim_is_closed_after_transport(self):
        folder=self.library/'other';folder.mkdir();claim=folder/'missing.cbz'
        with sqlite3.connect(self.catalog) as db:db.execute('INSERT INTO issues VALUES (?,?,?,?)',('321','456','other/missing.cbz','Wanted'))
        original=self.response
        def reply(request):
            value=original(request);value['evidence']['claims']=[[str(self.native_root/'other/missing.cbz'),None]];return value
        with patch.object(self,'response',reply):self.prepare();self.assertEqual(self.dispatch(),1)
        claim.write_bytes(b'foreign');self.assertIsNone(self.confirmed())
    def test_last_current_confirmation_callback_missing_claim_is_closed(self):
        folder=self.library/'other';folder.mkdir();claim=folder/'missing.cbz'
        original=self.response
        def reply(request):
            value=original(request);value['evidence']['claims']=[[str(self.native_root/'other/missing.cbz'),None]];return value
        with patch.object(self,'response',reply):self.prepare();self.dispatch()
        real=guard.confirmation_check;calls=[]
        def late(*args,**kwargs):
            answer=real(*args,**kwargs);calls.append(True)
            if len(calls)==2:claim.write_bytes(b'late foreign claim')
            return answer
        with patch.object(guard,'confirmation_check',late):self.assertIsNone(self.confirmed())
        self.assertEqual(len(calls),2);self.assertTrue(claim.exists())
    def test_native_directory_claim_original_mode_is_retained(self):
        info=self.library.stat();vector=[info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_gid,None]
        original=self.response
        def reply(request):
            value=original(request);value['evidence']['claims']=[[str(self.native_root),vector]];return value
        with patch.object(self,'response',reply):self.prepare();self.assertEqual(self.dispatch(),1)
        self.library.chmod(0o770);self.assertIsNone(self.confirmed())
    def test_claim_conflicting_duplicate_or_unmapped_missing_is_held(self):
        original=self.response
        def reply(request):
            value=original(request);value['evidence']['claims']=[['/not-admitted/foreign.cbz',None]];return value
        with patch.object(self,'response',reply):self.prepare();self.dispatch()
        self.assertIsNone(self.confirmed())
    def test_raw_success_envelope_extra_field_is_held(self):
        self.prepare()
        def late(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':
                value=json.loads(result);value['foreign_envelope']={'cleanup_grant':True};return json.dumps(value)
            return result
        self.assertEqual(self.dispatch(late),0);self.assertIsNone(self.confirmed())
    def test_raw_success_envelope_duplicate_key_is_held(self):
        self.prepare()
        def late(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':return '{"success":true,'+result[1:]
            return result
        self.assertEqual(self.dispatch(late),0)
    def test_raw_response_bytes_are_kept_without_reserialization(self):
        self.prepare();returned=[]
        def spaces(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':result='  '+result+'\n';returned.append(result.encode())
            return result
        self.assertEqual(self.dispatch(spaces),1)
        self.assertEqual(next(iter(observation._LIVE.values()))['reply_bytes'],returned[0]);self.assertEqual(self.confirmed(),self.token)
    def actual_cycle(self,*,pending_job=False,recreate=False,workflow_before=False):
        from writer_cycle import cycle
        with sqlite3.connect(self.catalog) as db:
            db.execute('CREATE TABLE ddl_info(filename TEXT,tmp_filename TEXT,status TEXT)')
            for table,columns in (('issues',('Issue_Number','IssueDate')),('annuals',('Issue_Number','IssueDate','ReleaseComicName')),('comics',('ComicName','ComicYear'))):
                for column in columns:db.execute('ALTER TABLE '+table+' ADD COLUMN '+column+' TEXT DEFAULT \'\'')
        self.worker.jobs=self.state/'jobs';self.worker.jobs.mkdir();self.worker.pdf_policy={'enabled':False}
        self.worker.reader=SimpleNamespace(books=lambda:{})
        self.m.receipts=self.m.state/'receipts';self.m.receipts.mkdir()
        self.m.root=self.root/'completed';self.m.root.mkdir();self.m.roots=[self.m.root]
        self.m.settings={'interval_seconds':0,'pack_import':False,'ddl_cache':str(self.root/'cache'),'mylar_ddl_cache':'/native-cache'};self.m.last_run=0;self.m.observed={};self.m.cache={}
        events=[]
        def work():
            self.assertTrue(self.writer.fenced());events.append('marked-work')
            self.assertIsNone(ack_reader.confirmed(self.m,self.candidate,self.match,self.source))
            self.assertFalse(observation._PENDING);self.assertEqual(len(observation._SELECTORS),1)
            if pending_job:
                folder=self.worker.jobs/'pending';folder.mkdir();(folder/'receipt.json').write_text('{"phase":"converting"}')
        self.worker.cycle=work
        def naming():
            events.append('naming-before-fresh-admission')
            if workflow_before:
                with sqlite3.connect(self.workflow) as db:db.execute('INSERT INTO events(value) VALUES (?)',('ordinary prior dispatch fixture',))
            if recreate:
                with self.writer.hold(allow_pending=True):self.writer.mark_pending()
        self.worker.naming=SimpleNamespace(reconcile=lambda:None,tick=naming)
        def transport(base,route,form=None,**kwargs):
            self.assertFalse(getattr(self.writer.local[1],'depth',0))
            if form['cmd']=='getHealth':return {'success':True,'data':{'workflow':{'ordinary_import_observation':1},'queues':{'POST-PROCESS-QUEUE':{'alive':True,'size':0}},'processing':False}}
            if form['cmd']=='workflowCommands':return {'success':True,'data':{'commands':[],'aliases':[]}}
            events.append('observe-after-all-dispatch')
            self.assertIn('naming-before-fresh-admission',events)
            return self.transport(base,route,form=form,**kwargs)
        with patch('publication_guard.scope',self.scope),patch('writer_cycle.scope',self.scope),patch('maintenance.request',transport):
            self.assertTrue(cycle(self.worker,self.m))
        return events
    def test_actual_cycle_marker_clear_then_fresh_observation_consume(self):
        events=self.actual_cycle();self.assertFalse(self.writer.fenced());self.assertIn('observe-after-all-dispatch',events)
        result=next(iter(observation._RESULTS.values()));self.assertEqual(result[3],self.token);self.assertIs(result[5],False)
        self.assertFalse(observation._LIVE);self.assertFalse(observation._SELECTORS)
        self.assertEqual(json.loads((self.state/'maintenance-status.json').read_text())['state'],'checked')
    def test_actual_cycle_workflow_prior_change_is_before_new_preflight(self):
        self.actual_cycle(workflow_before=True);self.assertEqual(next(iter(observation._RESULTS.values()))[3],self.token)
    def test_actual_cycle_pending_job_does_not_observe(self):
        events=self.actual_cycle(pending_job=True);self.assertTrue(self.writer.fenced());self.assertNotIn('observe-after-all-dispatch',events);self.assertFalse(observation._RESULTS)
    def test_actual_cycle_recreated_marker_cannot_be_exempted(self):
        events=self.actual_cycle(recreate=True);self.assertTrue(self.writer.fenced());self.assertNotIn('observe-after-all-dispatch',events);self.assertFalse(observation._RESULTS)
    def test_last_ack_copied_export_callback_target_drift_is_held(self):
        real=ack_reader.confirmed;fired=[]
        def late(*args,**kwargs):
            answer=real(*args,**kwargs)
            if kwargs.get('_copied') and answer is not None:self.source.chmod(0o640);fired.append(True)
            return answer
        with patch.object(ack_reader,'confirmed',late):self.actual_cycle()
        self.assertTrue(fired);self.assertFalse(observation._RESULTS)
    def test_transport_read_limit_precedes_json_parser(self):
        import io
        import normalize
        reads=[]
        class Response(io.BytesIO):
            def read(self,size=-1):reads.append(size);return super().read(size)
        stream=Response(b' '*18)
        with patch('normalize.urllib.request.urlopen',return_value=stream):
            with self.assertRaises(ValueError):normalize.request('http://native-fixture.invalid','/api',text=True,limit=16)
            self.assertEqual(reads,[17])
    def test_transport_cannot_run_under_writer(self):
        self.prepare()
        with self.writer.hold(),self.scope(self.worker,self.writer),self.assertRaises(guard.Unavailable):self.dispatch()
        self.assertEqual(self.calls,[])
    def test_created_request_fd_mode_change_before_fsync_is_held(self):
        real=observation.os.fsync;fired=[]
        def late(fd):
            real(fd)
            if os.readlink('/proc/self/fd/'+str(fd)).endswith('.request.json'):os.fchmod(fd,0o640);fired.append(True)
        with patch.object(observation.os,'fsync',late):self.assertIsNone(self.confirmed())
        self.assertTrue(fired);self.assertFalse(observation._PENDING)
    def test_foreign_current_namespace_is_held_after_transport(self):
        self.prepare()
        def late(*args,**kwargs):
            result=self.transport(*args,**kwargs)
            if kwargs['form']['cmd']=='ordinaryImportObservation':(self.library/'foreign.cbz').write_bytes(b'foreign')
            return result
        self.assertEqual(self.dispatch(late),0)
    def test_overlapping_mappings_do_not_admit_observation(self):
        self.worker.config['publication_roots'].append(dict(native=str(self.native_root/'nested'),worker=str(self.library/'nested')))
        with self.assertRaises(guard.Unavailable):self.confirmed()
    def test_old_native_keeps_request_prepared_unspent(self):
        self.prepare()
        def old(*args,**kwargs):return {'success':True,'data':{'workflow':{}}}
        self.assertEqual(self.dispatch(old),0);self.assertEqual(next(iter(observation._PENDING.values()))['phase'],'prepared')
    def test_same_response_replay_has_no_live_witness(self):
        self.prepare();self.dispatch();self.assertEqual(self.confirmed(),self.token);self.assertIsNone(self.confirmed())
    def test_changed_history_after_return_is_held(self):
        self.prepare();self.dispatch()
        with sqlite3.connect(self.history) as db:db.execute('UPDATE completions SET ack=NULL')
        self.assertIsNone(self.confirmed())

class Annual(Bridge):
    ANNUAL=True
    def test_genuine_worker_annual_parent_release_are_distinct(self):
        self.prepare();self.assertEqual(self.dispatch(),1);self.assertEqual(self.confirmed(),self.token)
        self.assertNotEqual(self.owner['parentcomicid'],self.owner['releasecomicid'])
    def test_wrong_original_annual_ack_release_is_held(self):
        self.ack['owner']=dict(self.owner,releasecomicid='456')
        with sqlite3.connect(self.history) as db:db.execute('UPDATE completions SET ack=?',(json.dumps(self.ack),))
        self.assertIsNone(self.confirmed());self.assertFalse(observation._PENDING)

def load_tests(loader,tests,pattern):return unittest.TestSuite(cls(name) for cls in (Bridge,Annual) for name in cls.__dict__ if name.startswith('test_'))
if __name__=='__main__':unittest.main()

"""Real file/FD/flock/pipe controls; Parent/Docker/HTTP boundaries explicitly projected.

No root installation, image parity, connected Parent/NFS or live rights are proved.
"""
import ast
import copy
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE.parent))
import install_configured_reader_parent as installer
import comic_reader_lifecycle_parent as p
import comic_negative_nfs_active_parent as a
import comic_nfs_parent_session as pump
import comic_nfs_uid_child as child
import media_writer


def reference(path):
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=p.nine(path.lstat()))


def documents():
    user=dict(id='fixture-admin',roles=['ADMIN'],sharedAllLibraries=True,sharedLibrariesIds=[],labelsAllow=[],labelsExclude=[],ageRestriction=None)
    library=dict(id='fixture-library',root='/library',scanOnStartup=False,scanInterval='DISABLED',emptyTrashAfterScan=False,convertToCbz=False,repairExtensions=False,scanForceModifiedTime=False,scanDirectoryExclusions=[],unavailable=False)
    return dict(user=user,libraries=[library],repeated_libraries=[copy.deepcopy(library)])


class WorkerProfile(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        fixture=HERE/'_archive_worker_fixtures/archive_terminal_observation.py'
        # This exact private dependency is copied from the owning canonical worker.
        self.source=self.root/'archive_terminal_observation.py';self.source.write_bytes(fixture.read_bytes())
        self.mapping=self.root/'worker-image-map.json';self.mapping.write_text(json.dumps({'/app/archive_terminal_observation.py':installer.WORKER_OBSERVER_SOURCE_SHA}))
        self.metadata=self.root/'image.json';self.metadata.write_text(json.dumps([dict(Id='sha256:'+'a'*64,Os='linux',Architecture='amd64')]))
        for path in (self.source,self.mapping,self.metadata):path.chmod(0o600)
        self.profile=dict(mode='original-pipes-v1',source=reference(self.source),image_sources=reference(self.mapping),image_metadata=reference(self.metadata))
        refs=json.loads((HERE/'INSTALLER-SOURCE-LOCATORS.json').read_text());self.sources={name:(HERE/path).read_bytes() for name,path in refs.items()}
    def test_default_refuses_worker_and_optin_derives_entire_existing_graph(self):
        default,_=installer.build(self.sources,'/private/comic_reader_lifecycle_parent.py')
        self.assertIn(b'WORKER_OBSERVATION_ENABLED = False',default['comic_reader_lifecycle_parent.py'])
        image,rows,nodes=installer.worker_original_inputs(self.profile)
        self.assertEqual(image,'sha256:'+'a'*64);self.assertEqual(len(rows),3);self.assertTrue(nodes)
        actual,receipt=installer.build(self.sources,'/private/comic_reader_lifecycle_parent.py',worker_observation=self.profile,worker_image=image)
        tree=ast.parse(actual['comic_reader_lifecycle_parent.py']);constants={n.targets[0].id:ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and getattr(n.targets[0],'id','').startswith('WORKER_OBSERVATION_')}
        self.assertIs(constants['WORKER_OBSERVATION_ENABLED'],True)
        self.assertEqual(constants['WORKER_OBSERVATION_ORIGINALS'],{k:self.profile[k] for k in ('mode','source','image_sources')})
        self.assertEqual(constants['WORKER_OBSERVATION_IMAGE'],image);self.assertEqual(constants['WORKER_OBSERVATION_IMAGE_ORIGINAL'],self.profile['image_metadata'])
        pin=receipt['parent_sha256'];self.assertIn(pin.encode(),actual['publication_reader_admission.py']);self.assertIn(pin.encode(),actual['comic_archive_repair_action.py']);self.assertIn(pin.encode(),actual['comic_archive_backup_action.py'])
        self.assertFalse(receipt['lifecycle_authority']);self.assertFalse(receipt['base_image_parity'])
        # Both generated producer consumers must load the exact changed action.
        for name in ('comic_archive_proof_producer.py','comic_archive_backup_action.py','comic_archive_evidence_adapter.py'):ast.parse(actual[name])
    def test_missing_or_foreign_source_and_noncanonical_refs_refuse(self):
        for value in (None,{},dict(self.profile,source=dict(self.profile['source'],sha256='b'*64)),dict(self.profile,source=dict(self.profile['source'],path='/private/../foreign'))):
            with self.subTest(value=type(value).__name__),self.assertRaises(installer.Held):installer.worker_profile(value)
    def test_image_map_unknown_path_or_source_hash_refuses(self):
        for value in ({'/app/other.py':installer.WORKER_OBSERVER_SOURCE_SHA},{'/app/archive_terminal_observation.py':'0'*64}):
            self.mapping.write_text(json.dumps(value));self.profile['image_sources']=reference(self.mapping)
            with self.assertRaisesRegex(installer.Held,'exact-image-sources'):installer.worker_original_inputs(self.profile)
    def test_image_wrong_arch_or_bad_identity_refuses(self):
        for fields in (dict(Id='sha256:'+'a'*64,Os='linux',Architecture='arm64'),dict(Id='foreign',Os='linux',Architecture='amd64')):
            self.metadata.write_text(json.dumps([fields]));self.profile['image_metadata']=reference(self.metadata)
            with self.assertRaises(installer.Held):installer.worker_original_inputs(self.profile)
    def test_same_byte_metadata_replacement_refuses_original9(self):
        data=self.metadata.read_bytes();other=self.root/'replacement';other.write_bytes(data);other.chmod(0o600);os.replace(other,self.metadata)
        with self.assertRaisesRegex(installer.Held,'original9'):installer.worker_original_inputs(self.profile)
    def test_source_hash_drift_refuses(self):
        self.source.write_bytes(self.source.read_bytes()+b'\n')
        with self.assertRaises(installer.Held):installer.worker_original_inputs(self.profile)
    def test_metadata_swap_during_last_decode_cannot_be_adopted(self):
        real=json.loads;count=[]
        def changed(*args,**kwargs):
            value=real(*args,**kwargs);count.append(True)
            if len(count)==2:
                replacement=self.root/'replacement';replacement.write_bytes(self.metadata.read_bytes());replacement.chmod(0o600);os.replace(replacement,self.metadata)
            return value
        with patch.object(json,'loads',changed),self.assertRaisesRegex(installer.Held,'original9-final'):installer.worker_original_inputs(self.profile)
    def test_parent_rejects_v12_before_any_operation_for_default_or_foreign_originals(self):
        node=next(x for x in ast.parse((HERE/'comic_reader_lifecycle_parent.py').read_bytes()).body if isinstance(x,ast.ClassDef) and x.name=='LifecycleParent')
        init=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=='__init__')
        block=next(x for x in init.body if isinstance(x,ast.If) and ast.unparse(x.test)=="plan.get('version') == 12")
        code=compile(ast.Module(body=[block],type_ignores=[]),'<actual-v12-admission>','exec');plan={'version':12,'worker_observation':{k:self.profile[k] for k in ('mode','source','image_sources')}}
        env=dict(plan=plan,need=p.need,WORKER_OBSERVATION_ENABLED=False,WORKER_OBSERVATION_ORIGINALS=plan['worker_observation'])
        with self.assertRaisesRegex(p.Held,'default-disabled'):exec(code,env)
        env.update(WORKER_OBSERVATION_ENABLED=True,WORKER_OBSERVATION_ORIGINALS=copy.deepcopy(plan['worker_observation']));exec(code,env)
        plan['worker_observation']['image_sources']['sha256']='b'*64
        with self.assertRaisesRegex(p.Held,'reviewed-original-profile'):exec(code,env)

    def test_actual_parent_worker_image_binding_refuses_other_image(self):
        cls=next(n for n in ast.parse((HERE/'comic_reader_lifecycle_parent.py').read_bytes()).body if isinstance(n,ast.ClassDef) and n.name=='LifecycleParent')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
        selected=next(n for n in fn.body if isinstance(n,ast.If) and 'worker-reviewed-image-mismatch' in ast.unparse(n))
        code=compile(ast.Module(body=[selected],type_ignores=[]),'<actual-worker-image-admission>','exec')
        env=dict(plan={'version':12},self=SimpleNamespace(baselines={'held_worker':{'Image':'sha256:'+'a'*64}}),WORKER_OBSERVATION_IMAGE='sha256:'+'a'*64,need=p.need)
        exec(code,env);env['self'].baselines['held_worker']['Image']='sha256:'+'b'*64
        with self.assertRaisesRegex(p.Held,'reviewed-image-mismatch'):exec(code,env)
    def test_metadata_ancestor_replacement_refuses(self):
        directory=self.root/'nested';directory.mkdir(mode=0o700);target=directory/'image.json';target.write_bytes(self.metadata.read_bytes());target.chmod(0o600);self.profile['image_metadata']=reference(target)
        real=json.loads;count=[]
        def changed(*args,**kwargs):
            value=real(*args,**kwargs);count.append(True)
            if len(count)==2:
                directory.rename(self.root/'old-nested');directory.mkdir(mode=0o700);replacement=directory/'image.json';replacement.write_bytes(target.with_name('missing').name.encode())
            return value
        with patch.object(json,'loads',changed),self.assertRaisesRegex(installer.Held,'original-node-final'):installer.worker_original_inputs(self.profile)


class LibraryQuery(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.writer=media_writer.Writer(self.root/'media-writer',create=True)
        self.cfg=self.root/'config.json';self.cfg.write_text(json.dumps(dict(komga=dict(url='http://fixture.invalid:25600',api_key='PUBLIC TEST KEY'))));self.cfg.chmod(0o600)
        self.query=dict(version=1,kind='approved-active-komga-library-query',configuration={'path':str(self.cfg),'sha256':hashlib.sha256(self.cfg.read_bytes()).hexdigest()},expected_base_url='http://fixture.invalid:25600')
        self.owner=object.__new__(p.LifecycleParent);self.owner.engine=p.ScopedDocker();self.owner.plan={'nonce':'b'*64}
        self.owner.files={str(self.cfg):tuple(p.nine(self.cfg.lstat())),str(self.writer.lock):tuple(p.nine(self.writer.lock.lstat()))};self.owner.nodes={}
        for path in (self.cfg,self.writer.lock):self.owner.nodes.update(p.parents(path))
        self.owner.left=lambda:10
        row=dict(Id='c'*64,Name='/komga',Image='sha256:'+'d'*64,Path='fixture',Args=[],Config={},HostConfig={},Mounts=[],NetworkSettings={},State=dict(Status='running',Running=True,Paused=False,Restarting=False,OOMKilled=False,Dead=False,Pid=os.getpid(),ExitCode=0,Error='',StartedAt='original-fixture-epoch',FinishedAt=''))
        self.owner.baselines={'reader':row};self.owner.inspect=lambda cid:copy.deepcopy(row)
        self.session=SimpleNamespace(close=lambda:None,state='starting',pump=SimpleNamespace(failed=False,finished=False),engine_replies=SimpleNamespace(sequence=0),lease_replies=SimpleNamespace(lease=None,done=False))
        self.functions=tuple((name,getattr(a,name),getattr(a,name).__code__) for name in ('library_documents','checked_library_user','checked_library_documents','map_library_documents','encode','digest'))
        p._NFS_LIVE_SESSIONS[self.owner]=self.session
        p._NFS_LIBRARY_QUERIES[self.owner]=(p.encode(self.query),p.encode(reference(self.cfg)),a,self.functions,p.encode(dict(path=str(self.writer.lock),signature9=p.nine(self.writer.lock.lstat()))),a.RefuseRedirect,a.RefuseRedirect.redirect_request.__code__)
        self.calls=[];self.docs=documents();self.callback=None
        class Response(io.BytesIO):pass
        def opened(request,timeout):
            self.calls.append((request.get_method(),request.full_url,timeout))
            if self.callback:self.callback()
            data=self.docs['user'] if len(self.calls)%3==1 else self.docs['libraries'] if len(self.calls)%3==2 else self.docs['repeated_libraries']
            return Response(json.dumps(data).encode())
        self.opener=SimpleNamespace(open=opened)
        self.patch=patch.object(a.urllib.request,'build_opener',return_value=self.opener);self.patch.start();self.addCleanup(self.patch.stop)
        self.addCleanup(self.cleanup)
    def cleanup(self):
        for registry in (p._NFS_LIVE_SESSIONS,p._NFS_LIBRARY_QUERIES,p._NFS_LIBRARY_REPLIES,p._NFS_REMOTE_WINDOWS,p._NFS_PROBE_REMOVED):registry.pop(self.owner,None);registry.pop(self.owner.engine,None)
    def frame(self,**changes):
        return dict(dict(type='nfs-library-query',nonce=self.owner.plan['nonce'],sequence=self.session.engine_replies.sequence+1,payload={}),**changes)
    def run_query(self):return self.owner.nfs_library_query_reply(self.frame())
    def test_fixed_three_gets_full_child_validation_and_no_credential_reply(self):
        reply=self.run_query();self.assertEqual([x[:2] for x in self.calls],[('GET','http://fixture.invalid:25600/api/v2/users/me'),('GET','http://fixture.invalid:25600/api/v1/libraries'),('GET','http://fixture.invalid:25600/api/v1/libraries')]);self.assertNotIn('PUBLIC TEST KEY',json.dumps(reply));self.assertEqual(self.session.engine_replies.sequence,1)
        library=self.root/'library';library.mkdir();rows=[dict(Name='/komga',Mounts=[dict(Type='bind',Source=str(library),Destination='/library')])]
        result=a.fresh_libraries(self.query,rows,{},[library],library_observer=lambda:reply['payload']);self.assertEqual(result['mapped_roots'],[str(library)]);self.assertEqual(len(self.calls),3)
    def test_route_endpoint_nonce_sequence_or_payload_substitution_refuses_before_http(self):
        for changes in ({'payload':{'route':'/other'}},{'payload':[]},{'nonce':'e'*64},{'sequence':0},{'type':'query'}):
            with self.subTest(changes=changes),self.assertRaises(p.Held):self.owner.nfs_library_query_reply(self.frame(**changes))
        self.assertEqual(self.calls,[])
    def test_real_cross_process_exclusive_writer_without_window_refuses_http(self):
        program="import sys;sys.path.insert(0,sys.argv[1]);import media_writer;from pathlib import Path;w=media_writer.Writer(Path(sys.argv[2]),create=False);ctx=w.hold();ctx.__enter__();print('held',flush=True);sys.stdin.buffer.read();ctx.__exit__(None,None,None)"
        process=subprocess.Popen([sys.executable,'-I','-B','-c',program,str(HERE.parent),str(self.writer.root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(process.stdout.readline(),b'held\n')
            with self.assertRaisesRegex(p.Held,'exclusive-Writer-held'):self.run_query()
            self.assertEqual(self.calls,[])
        finally:
            process.stdin.close();self.assertEqual(process.wait(timeout=5),0,process.stderr.read());process.stdout.close();process.stderr.close()
    def test_shared_interlock_blocks_exclusive_acquisition_during_each_get(self):
        def attempted():
            program="import os,fcntl,sys;f=os.open(sys.argv[1],os.O_RDONLY);\ntry:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)\nexcept BlockingIOError:sys.exit(7)\nsys.exit(0)"
            result=subprocess.run([sys.executable,'-I','-B','-c',program,str(self.writer.lock)],capture_output=True,timeout=5);self.assertEqual(result.returncode,7,result.stderr)
        self.callback=attempted;self.run_query();self.assertEqual(len(self.calls),3)
        fd=os.open(self.writer.lock,os.O_RDONLY)
        try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:os.close(fd)
    def test_registered_writer_window_and_failed_session_refuse_before_http(self):
        p._NFS_REMOTE_WINDOWS[self.owner.engine]=('explicit-fixture-window',)
        with self.assertRaisesRegex(p.Held,'no-remote-under-Writer'):self.run_query()
        p._NFS_REMOTE_WINDOWS.pop(self.owner.engine);self.session.state='failed'
        with self.assertRaises(p.Held):self.run_query()
        self.assertEqual(self.calls,[])
    def test_moved_missing_or_foreign_lock_refuses_before_http(self):
        original=self.writer.lock.read_bytes();self.writer.lock.unlink()
        with self.assertRaises(FileNotFoundError):self.run_query()
        self.writer.lock.write_bytes(original);self.writer.lock.chmod(0o600)
        with self.assertRaisesRegex(p.Held,'original-lock-FD'):self.run_query()
        self.assertEqual(self.calls,[])
    def test_malformed_admin_and_unstable_or_incomplete_dto_refuse(self):
        self.docs['user']['roles']=[]
        with self.assertRaisesRegex(a.Held,'unrestricted-admin'):self.run_query()
        self.assertEqual(len(self.calls),1)
        self.calls.clear();self.docs=documents();self.docs['repeated_libraries'][0]['id']='changed'
        with self.assertRaisesRegex(a.Held,'stable-library-pair'):self.run_query()
        self.calls.clear();self.docs=documents();del self.docs['libraries'][0]['scanInterval'];self.docs['repeated_libraries']=copy.deepcopy(self.docs['libraries'])
        with self.assertRaisesRegex(a.Held,'full-dto'):self.run_query()
    def test_configuration_inode_drift_during_get_refuses_original(self):
        def change():
            replacement=self.root/'replacement';replacement.write_bytes(self.cfg.read_bytes());replacement.chmod(0o600);os.replace(replacement,self.cfg)
        self.callback=change
        with self.assertRaises(p.Held):self.run_query()
        self.assertEqual(len(self.calls),1)
    def test_second_query_before_physical_release_refuses(self):
        self.run_query()
        with self.assertRaisesRegex(p.Held,'physical-release-required'):self.run_query()
        self.assertEqual(len(self.calls),3)
    def test_changed_child_reply_or_root_escape_refuses(self):
        reply=self.run_query()['payload'];reply['query_plan_sha256']='0'*64
        with self.assertRaisesRegex(a.Held,'original-host-library-query-reply'):a.fresh_libraries(self.query,[],{},[],library_observer=lambda:reply)
        reply['query_plan_sha256']=a.digest(a.encode(self.query));reply['documents']['libraries'][0]['root']='/other';reply['documents']['repeated_libraries']=copy.deepcopy(reply['documents']['libraries'])
        with self.assertRaisesRegex(a.Held,'mapped-library-root'):a.fresh_libraries(self.query,[dict(Name='/komga',Mounts=[])],{},[],library_observer=lambda:reply)
    def released_fixture(self):
        class Lease:
            def window_state(self):return 'RELEASED_PHYSICAL'
        self.session.lease_replies.lease=Lease();self.session.lease_replies.done=True
        self.owner.nfs_host_modules=lambda:{'comic_nfs_host_lease.py':SimpleNamespace(HostWriterLease=Lease)}
        p._NFS_PROBE_REMOVED[self.owner]=('explicit-fixture-removal',)
    def test_postrelease_fresh_original_query_repeats_all_gets(self):
        before=self.run_query();self.released_fixture();after=self.run_query()
        self.assertEqual(before['payload'],after['payload']);self.assertEqual(len(self.calls),6);self.assertEqual(after['sequence'],2)
    def test_lock_replacement_during_get_refuses_before_next_request(self):
        def change():
            replacement=self.root/'foreign-lock';replacement.write_bytes(self.writer.lock.read_bytes());replacement.chmod(0o600);os.replace(replacement,self.writer.lock)
        self.callback=change
        with self.assertRaisesRegex(p.Held,'original-lock-each-GET'):self.run_query()
        self.assertEqual(len(self.calls),1)
    def test_postrelease_changed_documents_cannot_be_adopted(self):
        self.run_query()
        # Only genuine HostWriterLease.window_state is production-authorizing;
        # this source-method phase fixture projects it explicitly, not NFS proof.
        class Lease:
            def window_state(self):return 'RELEASED_PHYSICAL'
        self.session.lease_replies.lease=Lease();self.session.lease_replies.done=True
        self.owner.nfs_host_modules=lambda:{'comic_nfs_host_lease.py':SimpleNamespace(HostWriterLease=Lease)}
        p._NFS_PROBE_REMOVED[self.owner]=('explicit-fixture-removal',)
        self.docs['user']['id']='changed-principal'
        with self.assertRaisesRegex(p.Held,'original-reply-changed'):self.run_query()
    def test_actual_retained_pump_routes_only_fixed_query_then_ready(self):
        program="import sys,json;sys.path.insert(0,sys.argv[1]);from comic_nfs_uid_child import Channel;c=Channel(0,1,'b'*64,5);seq=c.send('nfs-library-query',{});r=c.receive(seq);assert r['kind']=='parent-original-library-query' and r['native_grant'] is False;c.send('nfs-ready',{'fixture_only':True});sys.stdin.buffer.read()"
        self.retained_transport(program,False)
    def test_lost_child_ack_marks_retained_session_failed_without_replay(self):
        program="import sys,json;print(json.dumps({'type':'nfs-library-query','nonce':'b'*64,'sequence':1,'payload':{}}),flush=True)"
        self.retained_transport(program,True)
    def retained_transport(self,program,lost):
        process=subprocess.Popen([sys.executable,'-I','-B','-c',program,str(HERE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        session=object.__new__(pump.RetainedChild);session.owner=self.owner;session.close=lambda:None;session.state='starting';session.last=None
        session.engine_replies=self.session.engine_replies;session.lease_replies=self.session.lease_replies
        def fact(frame,kind):
            self.assertEqual(frame['nonce'],self.owner.plan['nonce']);self.assertEqual(frame['sequence'],session.engine_replies.sequence+1);session.engine_replies.sequence=frame['sequence'];return frame['payload']
        session.engine_replies.fact=fact
        session.pump=pump.OriginalPump(process,time.monotonic()+5,session.close);pump._SESSION_PUMPS[session]=session.pump
        p._NFS_LIVE_SESSIONS[self.owner]=session
        try:
            if lost:
                process.wait(timeout=5)
                with self.assertRaises((BrokenPipeError,pump.Held)):session.until('nfs-ready')
                self.assertEqual(session.state,'failed');self.assertTrue(session.pump.failed)
                with self.assertRaisesRegex(p.Held,'original-session'):self.owner.nfs_library_query_reply(self.frame())
            else:
                self.assertEqual(session.until('nfs-ready'),{'fixture_only':True});self.assertEqual(session.engine_replies.sequence,2)
            self.assertEqual(len(self.calls),3)
        finally:
            if not process.stdin.closed:process.stdin.close()
            self.assertEqual(process.wait(timeout=5),0,process.stderr.read());process.stdout.close();process.stderr.close();pump._SESSION_PUMPS.pop(session,None)

    def test_actual_child_channel_lost_ack_never_retries(self):
        r1,w1=os.pipe();r2,w2=os.pipe();channel=child.Channel(r1,w2,'b'*64,2)
        try:
            sequence=channel.send('nfs-library-query',{});raw=os.read(r2,4096);self.assertEqual(json.loads(raw)['payload'],{})
            os.close(w1);w1=None
            with self.assertRaisesRegex(child.Held,'lost-host'):channel.receive(sequence)
            os.set_blocking(r2,False)
            with self.assertRaises(BlockingIOError):os.read(r2,4096)
        finally:
            for fd in (r1,w1,r2,w2):
                if fd is not None:os.close(fd)

if __name__=='__main__':unittest.main()

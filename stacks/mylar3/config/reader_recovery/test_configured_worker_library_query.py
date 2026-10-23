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
    def test_parent_rejects_v12_v13_before_any_operation_for_default_or_foreign_originals(self):
        node=next(x for x in ast.parse((HERE/'comic_reader_lifecycle_parent.py').read_bytes()).body if isinstance(x,ast.ClassDef) and x.name=='LifecycleParent')
        init=next(x for x in node.body if isinstance(x,ast.FunctionDef) and x.name=='__init__')
        expected=ast.dump(ast.parse("plan.get('version') in (12, 13)",mode='eval').body,include_attributes=False)
        blocks=[x for x in init.body if isinstance(x,ast.If) and ast.dump(x.test,include_attributes=False)==expected and any(isinstance(value,ast.Constant) and value.value=='worker-observation-default-disabled' for value in ast.walk(x))]
        self.assertEqual(len(blocks),1)
        code=compile(ast.Module(body=blocks,type_ignores=[]),'<actual-v12-v13-admission>','exec')
        for version in (12,13):
            with self.subTest(version=version):
                plan={'version':version,'worker_observation':copy.deepcopy({k:self.profile[k] for k in ('mode','source','image_sources')})}
                env=dict(plan=plan,need=p.need,WORKER_OBSERVATION_ENABLED=False,WORKER_OBSERVATION_ORIGINALS=copy.deepcopy(plan['worker_observation']))
                with self.assertRaisesRegex(p.Held,'default-disabled'):exec(code,env)
                env.update(WORKER_OBSERVATION_ENABLED=True);exec(code,env)
                plan['worker_observation']['image_sources']['sha256']='b'*64
                with self.assertRaisesRegex(p.Held,'reviewed-original-profile'):exec(code,env)

    def test_actual_v12_v13_constructor_refusals_create_no_operation_or_engine_calls(self):
        source=self.root/'parent.py';source.write_bytes(Path(p.__file__).read_bytes());source.chmod(0o600)
        original=copy.deepcopy({k:self.profile[k] for k in ('mode','source','image_sources')})
        class NoEngine:
            def __getattr__(self,name):raise AssertionError('No engine access before worker admission: '+name)
        for version in (12,13):
            for enabled in (False,True):
                with self.subTest(version=version,worker_enabled=enabled):
                    operation=self.root/('operation-'+str(version)+'-'+str(enabled))
                    plan={key:{} for key in ('reader','held_native','held_worker','provider','producer','observer','sdk_map','native','producer_inputs','scope_projection','bounds','nfs','backup_provider')}
                    plan.update(version=version,kind='reviewed-archive-one-lifecycle-protocol',nonce='a'*64,seconds=60,operation=str(operation),selected_image='sha256:'+'b'*64,mounts=[],birth_source_sha256='c'*64,action='archive-one',terminal_mode='same-child-v1',worker_observation=copy.deepcopy(original))
                    if version==13:plan['publication_geometry']={}
                    if enabled:plan['worker_observation']['image_sources']['sha256']='b'*64
                    path=self.root/('plan-'+str(version)+'-'+str(enabled)+'.json');path.write_bytes(p.encode(plan));path.chmod(0o600)
                    names=frozenset(self.root.iterdir())
                    with patch.object(p,'WORKER_OBSERVATION_ENABLED',enabled),patch.object(p,'WORKER_OBSERVATION_ORIGINALS',copy.deepcopy(original)),self.assertRaisesRegex(p.Held,'reviewed-original-profile' if enabled else 'default-disabled'):
                        p.LifecycleParent(reference(path),reference(source),NoEngine())
                    self.assertFalse(operation.exists());self.assertEqual(frozenset(self.root.iterdir()),names)

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
    def test_upstream_user_omitted_age_reaches_all_three_GETs(self):
        # Komga 1.28.1 UserDto NON_NULL omits nullable ageRestriction.
        del self.docs['user']['ageRestriction']
        reply=self.run_query();self.assertEqual(len(self.calls),3)
        self.assertEqual([v[1].rsplit('/',1)[-1]for v in self.calls],['me','libraries','libraries'])
        self.assertNotIn('ageRestriction',reply['payload']['documents']['user'])
    def test_upstream_user_explicit_null_age_remains_accepted(self):
        self.assertIsNone(self.docs['user']['ageRestriction']);reply=self.run_query()
        self.assertEqual(len(self.calls),3);self.assertIsNone(reply['payload']['documents']['user']['ageRestriction'])
    def test_nonnull_age_always_refuses_before_library_GET(self):
        for age in ({'age':18,'restriction':'ALLOW_ONLY'},{'age':18,'restriction':'EXCLUDE'},{},[],False,0,'none'):
            with self.subTest(age_type=type(age).__name__):
                self.calls.clear();self.docs=documents();self.docs['user']['ageRestriction']=age
                with self.assertRaisesRegex(a.Held,'unrestricted-admin'):self.run_query()
                self.assertEqual(len(self.calls),1);self.assertTrue(self.calls[0][1].endswith('/api/v2/users/me'))
    def test_other_missing_or_restricted_principal_refuses_before_library_GET(self):
        variants=[]
        for name in ('id','roles','sharedAllLibraries','sharedLibrariesIds','labelsAllow','labelsExclude'):
            value=documents()['user'];del value[name];variants.append(value)
        for key,value in (('id',''),('roles',[]),('roles',['USER']),('sharedAllLibraries',False),('sharedAllLibraries',1)):
            user=documents()['user'];user[key]=value;variants.append(user)
        for key in ('sharedLibrariesIds','labelsAllow','labelsExclude'):
            for value in (['restricted'],None,{},False,''):
                user=documents()['user'];user[key]=value;variants.append(user)
        for index,user in enumerate(variants):
            with self.subTest(variant=index):
                self.calls.clear();self.docs=documents();self.docs['user']=user;self.docs['user'].pop('ageRestriction',None)
                with self.assertRaisesRegex(a.Held,'unrestricted-admin'):self.run_query()
                self.assertEqual(len(self.calls),1);self.assertTrue(self.calls[0][1].endswith('/api/v2/users/me'))

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


class NativeLibraryQuery(unittest.TestCase):
    """Actual owning method; only Docker/HTTP boundaries explicitly projected."""
    cleanup=LibraryQuery.cleanup
    frame=LibraryQuery.frame
    run_query=LibraryQuery.run_query
    def setUp(self):
        LibraryQuery.setUp(self)
        self.cfg.write_text(json.dumps(dict(komga=dict(url='http://komga:25600',api_key='PUBLIC TEST KEY'))));self.cfg.chmod(0o600)
        self.query['configuration']=dict(path=str(self.cfg),sha256=hashlib.sha256(self.cfg.read_bytes()).hexdigest());self.query['expected_base_url']='http://komga:25600'
        self.owner.files[str(self.cfg)]=tuple(p.nine(self.cfg.lstat()))
        reader=self.owner.baselines['reader'];reader['NetworkSettings']={'Networks':{'reader-net':{'NetworkID':'1'*64,'Aliases':['komga']}}}
        native=copy.deepcopy(reader);native.update(Id='e'*64,Name='/mylar3',Image='sha256:'+'f'*64);native['NetworkSettings']={'Networks':{'native-net':{'NetworkID':'1'*64,'Aliases':['mylar3']}}}
        self.owner.baselines['held_native']=native;self.owner.plan['held_native']=dict(id=native['Id'],profile=p.static(native))
        self.owner.inspect=lambda cid:copy.deepcopy(self.owner.baselines['reader'] if cid==reader['Id'] else self.owner.baselines['held_native'])
        p._NFS_LIBRARY_QUERIES[self.owner]=(p.encode(self.query),p.encode(reference(self.cfg)),a,self.functions,p.encode(dict(path=str(self.writer.lock),signature9=p.nine(self.writer.lock.lstat()))),a.RefuseRedirect,a.RefuseRedirect.redirect_request.__code__)
        self.execs=[]
        def remote(argv,**kwargs):
            self.execs.append((list(argv),dict(kwargs)));request=json.loads(kwargs['input'])
            self.calls.append(('GET',request['base'].rstrip('/')+request['route'],request['seconds']))
            if self.callback:self.callback()
            value=self.docs['user'] if len(self.calls)%3==1 else self.docs['libraries'] if len(self.calls)%3==2 else self.docs['repeated_libraries']
            return subprocess.CompletedProcess(argv,0,json.dumps(value).encode(),b'')
        self.remote=remote;self.owner.engine.canary=remote
    def test_exact_native_context_original_url_key_stdin_only(self):
        result=self.run_query();self.assertEqual(len(self.execs),3)
        for argv,kwargs in self.execs:
            self.assertEqual(argv,[*p.DOCKER,'exec','-i','--user','1000:1000','e'*64,'/lsiopy/bin/python3','-I','-B','-c',p.NATIVE_LIBRARY_GET])
            self.assertNotIn('PUBLIC TEST KEY',json.dumps(argv));self.assertNotIn('http://komga:25600',json.dumps(argv));request=json.loads(kwargs['input']);self.assertEqual(request['base'],'http://komga:25600');self.assertEqual(request['key'],'PUBLIC TEST KEY');self.assertIn(request['route'],('/api/v2/users/me','/api/v1/libraries'));self.assertFalse(kwargs['check'])
        self.assertNotIn('PUBLIC TEST KEY',json.dumps(result));self.assertFalse(result['payload']['native_grant']);self.assertEqual(len(self.calls),3)
    def helper_context(self):
        native=self.owner.baselines['held_native'];native['NetworkSettings']['Networks']['native-net']['NetworkID']='2'*64
        self.owner.plan['held_native']['profile']=p.static(native)
        worker=copy.deepcopy(native);worker.update(Id='9'*64,Name='/held-worker',Image='sha256:'+'7'*64);worker['State'].update(Status='created',Running=False,Pid=0)
        self.owner.baselines['held_worker']=worker;self.owner.plan['held_worker']=dict(id=worker['Id'],profile=p.static(worker))
        self.owner.inspect=lambda cid:copy.deepcopy(next(row for row in self.owner.baselines.values()if row['Id']==cid))
        self.owner.emit=lambda name,value:None
        self.helper_calls=[]
        def helper(image,reader,route,body,seconds,guard,record):
            guard();self.helper_calls.append((image,reader['Id'],route,body));result=self.remote([],input=body);guard();return result.stdout
        self.owner.engine.library_get=helper
    def test_no_common_network_selects_original_worker_reader_namespace(self):
        self.helper_context();self.run_query();self.assertEqual(len(self.helper_calls),3)
        self.assertTrue(all(row[0]=='sha256:'+'7'*64 and row[1]==self.owner.baselines['reader']['Id']for row in self.helper_calls))
    def test_helper_worker_epoch_drift_refuses_after_get(self):
        self.helper_context();original=self.owner.inspect
        def changed():
            def inspect(cid):
                row=original(cid)
                if cid=='9'*64:row['State']['StartedAt']='changed'
                return row
            self.owner.inspect=inspect
        self.callback=changed
        with self.assertRaisesRegex(p.Held,'worker-epoch'):self.run_query()
        self.assertEqual(len(self.helper_calls),1)
    def test_helper_reader_namespace_epoch_drift_refuses(self):
        self.helper_context();original=self.owner.inspect;reader_id=self.owner.baselines['reader']['Id']
        def changed():
            def inspect(cid):
                row=original(cid)
                if cid==reader_id:row['State']['StartedAt']='changed'
                return row
            self.owner.inspect=inspect
        self.callback=changed
        with self.assertRaisesRegex(p.Held,'reader-epoch'):self.run_query()
        self.assertEqual(len(self.helper_calls),1)
    def test_helper_failure_never_falls_back_to_host_or_native(self):
        self.helper_context();calls=[]
        def refused(*args):calls.append(True);raise p.Held('library-helper-command-unknown-no-replay')
        self.owner.engine.library_get=refused
        with self.assertRaisesRegex(p.Held,'unknown-no-replay'):self.run_query()
        self.assertEqual(calls,[True]);self.assertEqual(self.calls,[]);self.assertEqual(self.execs,[])
    def test_missing_reader_alias_refuses_without_host_fallback(self):
        self.owner.baselines['reader']['NetworkSettings']['Networks']['reader-net']['Aliases']=[]
        with self.assertRaisesRegex(p.Held,'alias-network-join'):self.run_query()
        self.assertEqual(self.execs,[]);self.assertEqual(self.calls,[])
    def test_native_network_drift_after_get_refuses(self):
        original=self.owner.inspect
        def changed():
            def inspect(cid):
                row=original(cid)
                if cid=='e'*64:row['NetworkSettings']['Networks']['native-net']['NetworkID']='3'*64
                return row
            self.owner.inspect=inspect
        self.callback=changed
        with self.assertRaisesRegex(p.Held,'native-epoch'):self.run_query()
        self.assertEqual(len(self.execs),1)
    def test_native_role_cid_or_profile_substitution_refuses(self):
        self.owner.plan['held_native']['id']='9'*64
        with self.assertRaisesRegex(p.Held,'native-role'):self.run_query()
        self.assertEqual(self.execs,[])
    def test_native_epoch_drift_after_first_get_refuses(self):
        def changed():self.owner.baselines['held_native']['State']['StartedAt']='changed'
        self.callback=changed
        with self.assertRaisesRegex(p.Held,'native-seal'):self.run_query()
        self.assertEqual(len(self.execs),1)
    def test_native_command_failure_not_retried_or_host_fallback(self):
        def failed(argv,**kwargs):
            self.execs.append((argv,kwargs));return subprocess.CompletedProcess(argv,2,b'',b'SECRET_FAILURE')
        self.owner.engine.canary=failed
        with self.assertRaisesRegex(p.Held,'native-query-held'):self.run_query()
        self.assertEqual(len(self.execs),1);self.assertEqual(self.calls,[])
    def test_client_source_drift_refuses(self):
        original=p.NATIVE_LIBRARY_GET
        try:
            self.callback=lambda:setattr(p,'NATIVE_LIBRARY_GET',original+'\n# changed')
            with self.assertRaisesRegex(p.Held,'client-source'):self.run_query()
        finally:p.NATIVE_LIBRARY_GET=original
    test_original_config_inode_drift=LibraryQuery.test_configuration_inode_drift_during_get_refuses_original
    test_real_shared_interlock_each_get=LibraryQuery.test_shared_interlock_blocks_exclusive_acquisition_during_each_get
    test_registered_writer_window_refusal=LibraryQuery.test_registered_writer_window_and_failed_session_refuse_before_http
    test_malformed_principal_and_dto=LibraryQuery.test_malformed_admin_and_unstable_or_incomplete_dto_refuse

class FixedNativeClient(unittest.TestCase):
    def test_source310_and_invalid_route_secret_safe(self):
        ast.parse(p.NATIVE_LIBRARY_GET,feature_version=(3,10))
        request=dict(base='http://fixture.invalid',key='SECRET_KEY',route='/api/v1/books/list',seconds=1)
        result=subprocess.run([sys.executable,'-I','-B','-c',p.NATIVE_LIBRARY_GET],input=json.dumps(request).encode(),capture_output=True,timeout=5)
        self.assertEqual(result.returncode,2);self.assertEqual(result.stdout,b'');self.assertNotIn(b'SECRET',result.stderr);self.assertNotIn(b'Traceback',result.stderr)
    def test_typed_host_selection_has_no_error_fallback(self):
        row=dict(Name='/komga',Config={},NetworkSettings={})
        self.assertEqual(p.library_transport('https://fixture.example',row,None),('host-http-v1',()))
        self.assertEqual(p.library_transport('http://127.0.0.1:25600',row,None),('host-http-v1',()))
    def test_native_get_decodes_with_genuine_shared_route_rules(self):
        calls=[]
        class Response(io.BytesIO):
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        def open_request(request,timeout):
            calls.append((request.get_method(),request.full_url,request.get_header('X-api-key')));return Response(b'{"fixture":true}')
        opener=SimpleNamespace(open=open_request)
        request=dict(base='http://komga:25600',key='PUBLIC TEST KEY',route='/api/v2/users/me',seconds=1)
        oldin,oldout=sys.stdin,sys.stdout
        try:
            sys.stdin=SimpleNamespace(buffer=io.BytesIO(json.dumps(request).encode()));output=io.BytesIO();sys.stdout=SimpleNamespace(buffer=output)
            with patch('urllib.request.build_opener',return_value=opener):exec(compile(p.NATIVE_LIBRARY_GET,'<source-owned-native-client>','exec'),{})
            self.assertEqual(output.getvalue(),b'{"fixture":true}')
        finally:sys.stdin,sys.stdout=oldin,oldout
        self.assertEqual(calls,[('GET','http://komga:25600/api/v2/users/me','PUBLIC TEST KEY')])




class ReaderNetworkHelper(unittest.TestCase):
    """Real source-owned method, projected Docker command/results only."""
    def setUp(self):
        self.engine=p.ScopedDocker();self.image='sha256:'+'5'*64;self.reader=dict(Id='6'*64,State={'Running':True})
        self.record_tmp=tempfile.TemporaryDirectory();self.addCleanup(self.record_tmp.cleanup);self.record_root=Path(self.record_tmp.name);self.events=[];self.records=[];self.calls=[];self.guard_calls=0;self.started=False;self.removed=False;self.row=None;self.change=None;self.timeout=None;self.client_code=0
        self.body=p.encode(dict(base='http://komga:25600',key='SECRET',route='/api/v2/users/me',seconds=10))
        self.image_config=dict(Env=['PATH=/usr/bin:/bin'],Labels={'org.opencontainers.image.source':'public-source'},Volumes=None)
        def run(argv,**kwargs):
            args=argv[len(p.DOCKER):];self.calls.append((args,kwargs));self.events.append(('command',args[0]))
            if self.timeout==args[0]:raise subprocess.TimeoutExpired(argv,1)
            if args[:2]==['image','inspect']:return subprocess.CompletedProcess(argv,0,p.encode([dict(Id=self.image,Os='linux',Architecture='amd64',Config=self.image_config)]),b'')
            if args[0]=='create':
                self.row=self.created(args)
                if self.change:self.change(self.row)
                return subprocess.CompletedProcess(argv,0,('8'*64+'\n').encode(),b'')
            if args[0]=='inspect':
                if self.removed:return subprocess.CompletedProcess(argv,1,b'[]',('Error: No such object: '+'8'*64+'\n').encode())
                row=copy.deepcopy(self.row)
                if self.started:row['State'].update(Status='exited',ExitCode=self.client_code)
                return subprocess.CompletedProcess(argv,0,p.encode([row]),b'')
            if args[0]=='start':self.started=True;return subprocess.CompletedProcess(argv,self.client_code,b'{"id":"fixture"}',b'')
            if args[0]=='rm':self.removed=True;return subprocess.CompletedProcess(argv,0,('8'*64+'\n').encode(),b'')
            self.fail('unapproved command')
        self.patch=patch.object(p.subprocess,'run',side_effect=run);self.patch.start();self.addCleanup(self.patch.stop)
    def created(self,args):
        get=lambda key:args[args.index(key)+1];label=get('--label');key,value=label.split('=',1);labels=dict(self.image_config['Labels'],**{key:value})
        return dict(Id='8'*64,Name='/'+get('--name'),Image=self.image,Path='python3',Args=['-I','-B','-S','-c',p.NATIVE_LIBRARY_GET],Config=dict(Image=self.image,User='1000:1000',Entrypoint=['python3'],Cmd=['-I','-B','-S','-c',p.NATIVE_LIBRARY_GET],WorkingDir='/',OpenStdin=True,Tty=False,Env=self.image_config['Env'],Labels=labels,Healthcheck={'Test':['NONE']}),HostConfig=dict(ReadonlyRootfs=True,Privileged=False,NetworkMode='container:'+self.reader['Id'],IpcMode='private',PidMode='',CapDrop=['ALL'],CapAdd=None,SecurityOpt=['no-new-privileges'],PidsLimit=32,Memory=268435456,MemorySwap=268435456,NanoCpus=500000000,RestartPolicy={'Name':'no'},AutoRemove=False,LogConfig={'Type':'none','Config':{}},PublishAllPorts=False,Binds=None,Mounts=[],Tmpfs=None,Devices=[],DeviceRequests=None,PortBindings={}),Mounts=[],NetworkSettings={'Networks':{}},State=dict(Status='created',Running=False,Pid=0,Paused=False,Restarting=False,Dead=False,OOMKilled=False,ExitCode=0))
    def guard(self):self.guard_calls+=1
    def record(self,name,value):
        self.records.append((name,value));self.events.append(('record',name.rsplit('-',1)[-1]))
        target=self.record_root/name;raw=p.encode(value);target.write_bytes(raw);target.chmod(0o600);return reference(target)
    def run_get(self):return self.engine.library_get(self.image,self.reader,'/api/v2/users/me',self.body,10,self.guard,self.record)
    def test_exact_owned_helper_get_profile_stdin_cleanup(self):
        self.assertEqual(self.run_get(),b'{"id":"fixture"}');self.assertTrue(self.removed);self.assertGreater(self.guard_calls,12)
        create=next(v for v,k in self.calls if v[0]=='create');self.assertEqual(create[create.index('--network')+1],'container:'+'6'*64);self.assertNotIn('SECRET',str(create));self.assertNotIn('http://komga',str(create));self.assertNotIn('--volume',create);self.assertNotIn('--mount',create)
        starts=[(v,k)for v,k in self.calls if v[0]=='start'];self.assertEqual(len(starts),1);self.assertEqual(starts[0][1]['input'],self.body);self.assertTrue(any(name.endswith('-cleanup.json')for name,_ in self.records))
    def test_every_cleanup_error_requires_exact_empty_JSON(self):
        original=p.subprocess.run.side_effect
        for prefix in ('error: no such object: ','Error: No such object: ','Error: No such container: ','Error response from daemon: No such container: '):
            for stdout in (b'[]',b'[{}]',b'{}',b'not-json'):
                with self.subTest(prefix=prefix,stdout=stdout):
                    self.started=False;self.removed=False;self.records.clear();self.calls.clear()
                    def absent(argv,**kwargs):
                        result=original(argv,**kwargs)
                        if self.removed and argv[len(p.DOCKER)]=='inspect':
                            result.stdout=stdout;result.stderr=(prefix+'8'*64+'\n').encode()
                        return result
                    p.subprocess.run.side_effect=absent
                    if stdout==b'[]':
                        self.assertEqual(self.run_get(),b'{"id":"fixture"}')
                        self.assertTrue(any(name.endswith('-cleanup.json')for name,_ in self.records))
                    else:
                        with self.assertRaises((p.Held,ValueError)):self.run_get()
                        self.assertFalse(any(name.endswith('-cleanup.json')for name,_ in self.records))
    def phase_rows(self):
        before=self.created(['--name','reader-library-'+'a'*32,'--label','com.homelab.reader.library-query='+'a'*32])
        before['Config']['Hostname']='8'*12;before['HostConfig']['OomKillDisable']=False
        after=copy.deepcopy(before);after['Config']['Hostname']='reader-original';after['HostConfig']['OomKillDisable']=None
        return p.static(before),p.static(after),dict(Config={'Hostname':'reader-original'})
    def test_exact_recorded_helper_phase_pair(self):
        before,after,reader=self.phase_rows();self.assertTrue(p.library_helper_created_to_exited(before,after,'8'*64,reader));self.assertNotEqual(before,after)
    def test_helper_phase_wrong_or_blank_hostname_refuses(self):
        before,after,reader=self.phase_rows()
        for which,value in(('before',''),('before','foreign'),('after','foreign'),('after','')):
            left=copy.deepcopy(before);right=copy.deepcopy(after);(left if which=='before'else right)['Config']['Hostname']=value
            self.assertFalse(p.library_helper_created_to_exited(left,right,'8'*64,reader))
        self.assertFalse(p.library_helper_created_to_exited(before,after,'8'*64,dict(Config={'Hostname':''})))
    def test_helper_phase_OOM_pair_has_exact_types(self):
        before,after,reader=self.phase_rows()
        for old_oom,new_oom in((True,None),(0,None),(False,False),(False,0),(None,False)):
            left=copy.deepcopy(before);right=copy.deepcopy(after);left['HostConfig']['OomKillDisable']=old_oom;right['HostConfig']['OomKillDisable']=new_oom
            self.assertFalse(p.library_helper_created_to_exited(left,right,'8'*64,reader))
    def test_helper_phase_security_unknown_extra_and_alias_refuse(self):
        before,after,reader=self.phase_rows()
        for section,key,value in(('HostConfig','ReadonlyRootfs',False),('Config','UnknownExtra','unexpected'),('NetworkSettings','Networks',{'foreign':{}}),('Config','Env',['FOREIGN'])):
            changed=copy.deepcopy(after);changed[section][key]=value;self.assertFalse(p.library_helper_created_to_exited(before,changed,'8'*64,reader))
        self.assertFalse(p.library_helper_created_to_exited(before,after,'9'*64,reader))
        wrong_before=copy.deepcopy(before);wrong_after=copy.deepcopy(after);wrong_before['Id']='9'*64;wrong_after['Id']='9'*64
        self.assertFalse(p.library_helper_created_to_exited(wrong_before,wrong_after,'8'*64,reader))
    def actual_phase_boundary(self,cleanup_drift=False):
        self.reader['Config']={'Hostname':'reader-original'};original=p.subprocess.run.side_effect;count=0
        def run(argv,**kwargs):
            nonlocal count
            result=original(argv,**kwargs)
            if argv[len(p.DOCKER)]=='inspect'and not self.removed:
                value=json.loads(result.stdout);value[0]['Config']['Hostname']='reader-original'if self.started else'8'*12;value[0]['HostConfig']['OomKillDisable']=None if self.started else False
                if self.started:
                    count+=1
                    if cleanup_drift and count==2:value[0]['Config']['Hostname']='foreign-after-phase'
                result.stdout=p.encode(value)
            return result
        p.subprocess.run.side_effect=run
    def test_genuine_helper_recorded_phase_reaches_exact_exited_cleanup(self):
        self.actual_phase_boundary();self.assertEqual(self.run_get(),b'{"id":"fixture"}');self.assertTrue(self.removed)
        created=next(value for name,value in self.records if name.endswith('-created.json'));terminal=next(value for name,value in self.records if name.endswith('-terminal.json'));self.assertEqual(created['HostConfig']['OomKillDisable'],False);self.assertIsNone(terminal['HostConfig']['OomKillDisable'])
    def test_genuine_helper_full_exited_profile_drift_never_cleans(self):
        self.actual_phase_boundary(True)
        with self.assertRaisesRegex(p.Held,'cleanup-original'):self.run_get()
        self.assertFalse(self.removed);self.assertFalse(any(name.endswith('-cleanup.json')for name,value in self.records))
    def test_phase_projection_does_not_change_general_static_contract(self):
        before,after,reader=self.phase_rows();left=copy.deepcopy(before);right=copy.deepcopy(after)
        self.assertTrue(p.library_helper_created_to_exited(before,after,'8'*64,reader));self.assertEqual(before,left);self.assertEqual(after,right);self.assertNotEqual(p.static(before),p.static(after))
    def test_durable_intent_and_create_ACK_precede_inspect(self):
        self.run_get();intent=next(value for name,value in self.records if name.endswith('-intent.json')and not name.endswith('-start-intent.json'))
        self.assertEqual(intent['network_mode'],'container:'+'6'*64);self.assertEqual(intent['create_argv'],next(args for args,kw in self.calls if args[0]=='create'));self.assertNotIn('SECRET',json.dumps(intent))
        ack=next(value for name,value in self.records if name.endswith('-create-ack.json'));self.assertEqual(ack['container_id'],'8'*64)
        self.assertLess(self.events.index(('record','ack.json')),self.events.index(('command','inspect')))
    def test_memory_only_record_refuses_before_create(self):
        self.record=lambda name,value:None
        with self.assertRaisesRegex(p.Held,'ref-shape'):self.run_get()
        self.assertFalse(any(args[0]=='create'for args,kw in self.calls))
    def test_intent_record_failure_prevents_create(self):
        original=self.record
        def record(name,value):
            if name.endswith('-intent.json'):raise OSError('private-record-error')
            return original(name,value)
        self.record=record
        with self.assertRaises(OSError):self.run_get()
        self.assertFalse(any(args[0]=='create'for args,kw in self.calls))
    def test_create_ACK_record_failure_never_inspects_starts_or_removes(self):
        original=self.record
        def record(name,value):
            if name.endswith('-create-ack.json'):raise OSError('private-record-error')
            return original(name,value)
        self.record=record
        with self.assertRaises(OSError):self.run_get()
        self.assertTrue(any(args[0]=='create'for args,kw in self.calls));self.assertFalse(any(args[0]in('inspect','start','rm')for args,kw in self.calls))
    def test_declared_volumes_refuse_before_create(self):
        self.image_config['Volumes']={'/data':{}}
        with self.assertRaisesRegex(p.Held,'image-original'):self.run_get()
        self.assertFalse(any(v[0]=='create'for v,k in self.calls))
    def test_wrong_image_platform_refuses_before_create(self):
        original=p.subprocess.run.side_effect
        def wrong(argv,**kwargs):
            r=original(argv,**kwargs)
            if argv[len(p.DOCKER):len(p.DOCKER)+2]==['image','inspect']:
                data=json.loads(r.stdout);data[0]['Architecture']='arm64';r.stdout=p.encode(data)
            return r
        p.subprocess.run.side_effect=wrong
        with self.assertRaisesRegex(p.Held,'image-original'):self.run_get()
    def test_unsafe_mount_refuses_without_start_or_cleanup(self):
        self.change=lambda row:row['Mounts'].append({'Type':'bind','Source':'/private','Destination':'/private','RW':False})
        with self.assertRaisesRegex(p.Held,'exact-isolation'):self.run_get()
        self.assertFalse(self.started);self.assertFalse(self.removed)
    def test_wrong_network_mode_refuses(self):
        self.change=lambda row:row['HostConfig'].update(NetworkMode='host')
        with self.assertRaisesRegex(p.Held,'exact-isolation'):self.run_get()
        self.assertFalse(self.started)
    def test_wrong_UID_or_command_refuses(self):
        self.change=lambda row:row['Config'].update(User='0:0')
        with self.assertRaisesRegex(p.Held,'command-profile'):self.run_get()
    def test_helper_profile_drift_before_cleanup_refuses(self):
        original=p.subprocess.run.side_effect
        def changed(argv,**kwargs):
            r=original(argv,**kwargs)
            if self.started and argv[len(p.DOCKER)]=='inspect':
                data=json.loads(r.stdout);data[0]['Config']['Cmd']=['foreign'];r.stdout=p.encode(data)
            return r
        p.subprocess.run.side_effect=changed
        with self.assertRaisesRegex(p.Held,'command-profile'):self.run_get()
        self.assertFalse(self.removed)
    def test_failed_GET_retains_without_replay_or_cleanup(self):
        self.client_code=2
        with self.assertRaisesRegex(p.Held,'GET-held'):self.run_get()
        self.assertEqual(sum(v[0]=='start'for v,k in self.calls),1);self.assertFalse(self.removed)
    def test_unknown_create_never_starts_or_cleans(self):
        self.timeout='create'
        with self.assertRaisesRegex(p.Held,'unknown-no-replay'):self.run_get()
        self.assertFalse(self.started);self.assertFalse(self.removed);self.assertTrue(any('-unknown-'in name for name,_ in self.records))
    def test_unknown_start_never_cleans_or_replays(self):
        self.timeout='start'
        with self.assertRaisesRegex(p.Held,'unknown-no-replay'):self.run_get()
        self.assertEqual(sum(v[0]=='start'for v,k in self.calls),1);self.assertFalse(self.removed)
    def test_unknown_cleanup_never_repeats_removal(self):
        self.timeout='rm'
        with self.assertRaisesRegex(p.Held,'unknown-no-replay'):self.run_get()
        self.assertEqual(sum(v[0]=='rm'for v,k in self.calls),1)
    def test_guard_failure_after_start_retains_helper(self):
        def guard():
            if self.started:raise p.Held('original-profile-drift')
        self.guard=guard
        with self.assertRaisesRegex(p.Held,'original-profile-drift'):self.run_get()
        self.assertFalse(self.removed)
    def test_route_body_mismatch_rejected_before_command(self):
        self.body=p.encode(dict(base='http://komga',key='SECRET',route='/other',seconds=10))
        with self.assertRaisesRegex(p.Held,'original-input'):self.run_get()
        self.assertFalse(self.calls)


class CanaryCommandPrefix(unittest.TestCase):
    def test_real_canary_inspect_and_native_exec_forward_exact_argv(self):
        engine=p.ScopedDocker()
        for tail in (['inspect','a'*64],['exec','-i','--user','1000:1000','a'*64,'/lsiopy/bin/python3','-I','-B','-c',p.NATIVE_LIBRARY_GET]):
            args=[*p.DOCKER,*tail];out=SimpleNamespace(returncode=0,stdout=b'{}',stderr=b'')
            with self.subTest(command=tail[0]),patch.object(p.subprocess,'run',return_value=out)as run:
                self.assertIs(engine.canary(args,input=b'private',capture_output=True,timeout=10,check=False),out)
                run.assert_called_once_with(args,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},input=b'private',capture_output=True,timeout=10,check=False)
    def test_findmnt_runs_only_new_child_as_fixed_owner(self):
        args=['findmnt','--json','--target','/fixture/private','--output','SOURCE,TARGET,FSTYPE,FSROOT,OPTIONS,MAJ:MIN']
        out=SimpleNamespace(returncode=1,stdout=b'',stderr=b'private refusal')
        with patch.object(p.subprocess,'run',return_value=out)as run:
            self.assertIs(p.ScopedDocker().canary(args,capture_output=True,timeout=10,check=False),out)
            run.assert_called_once_with(args,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},user=1000,group=1000,extra_groups=(),capture_output=True,timeout=10,check=False)
    def test_caller_cannot_choose_subprocess_identity(self):
        args=['findmnt','--json','--target','/fixture/private']
        for extra in ({'user':0},{'group':0},{'extra_groups':(0,)},{'preexec_fn':lambda:None}):
            with self.subTest(extra=next(iter(extra))),patch.object(p.subprocess,'run')as run:
                with self.assertRaisesRegex(p.Held,'nfs-engine-call-shape'):
                    p.ScopedDocker().canary(args,capture_output=True,timeout=10,check=False,**extra)
                run.assert_not_called()
    def test_findmnt_launch_failure_and_timeout_remain_held(self):
        args=['findmnt','--json','--target','/fixture/private']
        for error in (PermissionError('private'),p.subprocess.TimeoutExpired(args,1)):
            with self.subTest(error=type(error).__name__),patch.object(p.subprocess,'run',side_effect=error):
                with self.assertRaisesRegex(p.Held,'nfs-engine-ACK-unknown'):
                    p.ScopedDocker().canary(args,capture_output=True,timeout=10,check=False)
    def test_forbidden_and_malformed_commands_never_reach_subprocess(self):
        for args in ([],list(p.DOCKER),tuple([*p.DOCKER,'inspect','a'*64]),['docker','inspect','a'*64],[*p.DOCKER,'rm','a'*64],[*p.DOCKER,'stop','a'*64],['findmnt','--target','/']):
            with self.subTest(args=args),patch.object(p.subprocess,'run')as run:
                with self.assertRaises(p.Held):p.ScopedDocker().canary(args,capture_output=True,timeout=10,check=False)
                run.assert_not_called()
    def test_call_shape_refusals_precede_subprocess(self):
        for kwargs in ({'capture_output':False,'timeout':10,'check':False},{'capture_output':True,'timeout':901,'check':False},{'capture_output':True,'timeout':10,'check':True},{'capture_output':True,'timeout':10,'check':False,'shell':True}):
            with self.subTest(kwargs=kwargs),patch.object(p.subprocess,'run')as run:
                with self.assertRaisesRegex(p.Held,'nfs-engine-call-shape'):p.ScopedDocker().canary([*p.DOCKER,'inspect','a'*64],**kwargs)
                run.assert_not_called()
    def test_real_remote_window_guard_precedes_subprocess(self):
        engine=p.ScopedDocker();p._NFS_REMOTE_WINDOWS[engine]=object()
        try:
            with patch.object(p.subprocess,'run')as run:
                with self.assertRaisesRegex(p.Held,'nfs-no-remote-under-Writer'):engine.canary([*p.DOCKER,'inspect','a'*64],capture_output=True,timeout=10,check=False)
                run.assert_not_called()
        finally:del p._NFS_REMOTE_WINDOWS[engine]

if __name__=='__main__':unittest.main()

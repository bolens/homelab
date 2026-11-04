"""Explicit disposable installation projection; no actual root enrollment/auth launch claim."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

HERE=Path(__file__).resolve().parent.parent
OLD=HERE/'fixtures/host'
CRYPTO=HERE/'fixtures/host_crypto/private_crypto.py'
PUBLIC=bytes.fromhex('302a300506032b6570032100d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a')
# RFC8032 test seed; public test material, never a production credential.
DER=bytes.fromhex('302e020100300506032b6570042204209d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60')

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m

class BrokerTests(unittest.TestCase):
    def test_pack_target_witness_needs_no_ordinary_destination_history(self):
        request={'target_sha256':'a'*64}
        review={'existing_target':{'path':'/library/current.cbz','sha256':'a'*64}}
        self.assertEqual(self.m._pack_existing_target(review,request,{}),'/library/current.cbz')
        for member in ({'destination':'/library/foreign.cbz'},{'destination_sha256':'b'*64}):
            with self.assertRaises(self.m.Held):self.m._pack_existing_target(review,request,member)

    def test_pack_target_witness_refuses_wrong_hash_or_noncanonical_path(self):
        request={'target_sha256':'a'*64}
        for witness in ({'path':'/library/current.cbz','sha256':'b'*64},
                        {'path':'/library/../current.cbz','sha256':'a'*64},
                        {'path':'//library/current.cbz','sha256':'a'*64},
                        {'path':'/','sha256':'a'*64},
                        {'path':'/library/current.cbz','sha256':'a'*64,'ack':True}):
            with self.assertRaises(self.m.Held):self.m._pack_existing_target({'existing_target':witness},request,{})

    def test_actual_bootstrap_map_accepts_versioned_worker_modules(self):
        import ast,re
        tree=ast.parse((HERE/'source/BOOTSTRAP.py').read_bytes())
        predicate=next(n.args[0] for n in ast.walk(tree) if isinstance(n,ast.Call)
            and isinstance(n.func,ast.Name) and n.func.id=='need' and len(n.args)==2
            and isinstance(n.args[1],ast.Constant) and n.args[1].value=='bootstrap-map-schema')
        code=compile(ast.Expression(predicate),'bootstrap-map-predicate','eval')
        def accepts(name):
            mapping={name:'a'*64};scope=dict(mapping=mapping,map_raw=self.m.canonical(mapping),canonical=self.m.canonical,re=re)
            return eval(code,scope)
        for name in ('operations_v2.py','v3_auth_core.py','__init__.py'):
            with self.subTest(name=name):self.assertTrue(accepts(name))
        for name in ('../operations_v2.py','.py','3module.py','path/module.py'):
            with self.subTest(name=name):self.assertFalse(accepts(name))
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='fixed-launch-fixture-',dir=Path.home()/'.cache');self.root=Path(self.tmp.name);self.root.chmod(0o700)
        self.pkg=self.root/'package';self.pkg.mkdir(mode=0o700)
        shutil.copy2(CRYPTO,self.pkg/'private_crypto.py')
        for name in ('comic_retained_standalone_parent.py','comic_retained_standalone_backup.py','comic_reader_backup_primitives.py'):shutil.copy2(OLD/name,self.pkg/name)
        source_root=HERE/'fixtures/probe_sources'
        for name in ('comic_native_process_probe.py','publication_native_configured_scope.py'):shutil.copy2(source_root/name,self.pkg/name)
        shutil.copy2(HERE/'source/BOOTSTRAP.py',self.pkg/'BOOTSTRAP.py')
        shutil.copy2(HERE/'source/comic_retained_standalone_broker.py',self.pkg/'comic_retained_standalone_broker.py')
        self.m=load(self.pkg/'comic_retained_standalone_broker.py','broker_fixture')
        self.key=self.root/'test-key.der';self.key.write_bytes(DER);self.key.chmod(0o600)
        self.file=self.root/'deployment.json';self.enrollment=self.root/'enrollment.json'
        self.doc=dict(version=1,kind='standalone-root-deployment-v1',deployment='d'*64,image='e'*64,profile=self.m.LOGICAL_PROFILE_SHA,runtime_profile_sha256='f'*64,
                      broker_sources='a'*64,parent_sha256='b'*64,bootstrap_sha256='c'*64,inventory_sha256='1'*64,
                      anchor_sha256='2'*64,key_sha256=hashlib.sha256(PUBLIC).hexdigest(),public_der=PUBLIC.hex(),
                      host_sources={name:hashlib.sha256((self.pkg/name).read_bytes()).hexdigest() for name in self.m.NAMES},
                      daemon_sources={'/app/mylar3/mylar/worker_health.py':'6'*64,'/app/mylar3/mylar/native_writers.py':'7'*64},
                      ids=dict(native='3'*64,reader='4'*64,worker='5'*64))
        self.doc['broker_sources']=hashlib.sha256(json.dumps(self.doc['host_sources'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        self.doc['parent_sha256']=self.doc['host_sources']['comic_retained_standalone_parent.py']
        self.doc['bootstrap_sha256']=self.doc['host_sources']['BOOTSTRAP.py']
        self.anchors=self.root/'child';self.anchors.mkdir(mode=0o700)
        inventory={'version':1,'kind':'standalone-leaf-inventory-v1','sources':{
            **{'/opt/mylar-publication-launch/auth/'+n:'1'*64 for n in ('private_crypto.py','v3_auth_core.py','standalone_launch_auth.py')},
            **{'/app/mylar3/mylar/fixture_'+str(i)+'.py':'2'*64 for i in range(9)}}}
        inventory_raw=self.m.canonical(inventory);self.doc['inventory_sha256']=self.m.sha(inventory_raw)
        anchor={k:self.doc[k] for k in ('deployment','profile','broker_sources','parent_sha256','bootstrap_sha256','inventory_sha256','key_sha256')}
        anchor.update(version=1,kind='standalone-installation-anchor-v1')
        anchor_raw=self.m.canonical(anchor);self.doc['anchor_sha256']=self.m.sha(anchor_raw)
        for name,raw in zip(self.m.ANCHOR_NAMES,(anchor_raw,inventory_raw,PUBLIC)):
            path=self.anchors/name;path.write_bytes(raw);path.chmod(0o444)
        self.write();self.enroll()
        # This explicit unit-test projection is not a production installation grant.
        self.settings=patch.multiple(self.m,ROOT_UID=os.geteuid(),PACKAGE=self.pkg,KEY=self.key,INSTALLATION=self.file,
                                     ENROLLMENT=self.enrollment,CHILD_ANCHORS=self.anchors)
        self.settings.start()
        for name in self.m.NAMES:
            if name[:-3] in sys.modules:del sys.modules[name[:-3]]
    def tearDown(self):
        self.settings.stop()
        for name in self.m.NAMES:sys.modules.pop(name[:-3],None)
        self.tmp.cleanup()
    def write(self):
        self.file.write_text(json.dumps(self.doc,sort_keys=True,separators=(',',':'),ensure_ascii=True)+'')
        self.file.chmod(0o600)
    def enroll(self,digest=None):
        self.enrollment.write_text(json.dumps(dict(version=1,kind='standalone-root-enrollment-v1',deployment_sha256=digest or hashlib.sha256(self.file.read_bytes()).hexdigest()),sort_keys=True,separators=(',',':')))
        self.enrollment.chmod(0o600)
    def test_selected_existing_volume_profile_exact_name_no_extra_mount(self):
        parent=self.m.load_original_installation().close()['modules']['comic_retained_standalone_parent.py']
        mount=dict(Type='volume',Name='original-data',Source='/var/lib/docker/volumes/original-data/_data',Destination='/config',RW=True)
        native=dict(Image='sha256:'+'e'*64,Mounts=[dict(mount)])
        selected=dict(Image=native['Image'],Config=dict(User='1000:1000'),HostConfig=dict(ReadonlyRootfs=True,Privileged=False,CapAdd=None,CapDrop=['ALL'],PortBindings={},Devices=[],NetworkMode='none',SecurityOpt=['no-new-privileges']),NetworkSettings=dict(Networks={}),Mounts=[dict(mount)])
        self.assertTrue(parent.selected_profile(native,selected))
        for value in (None,'different-data'):
            selected['Mounts'][0]['Name']=value
            with self.assertRaises(ValueError):parent.selected_profile(native,selected)
        selected['Mounts'][0]=dict(mount);selected['HostConfig']['Privileged']=True
        with self.assertRaises(ValueError):parent.selected_profile(native,selected)
    def test_real_encoded_static_profile_and_external_identity_refusal(self):
        installation=self.m.load_original_installation();parent=installation.close()['modules']['comic_retained_standalone_parent.py']
        native=dict(Id='9'*64,Image='sha256:'+'e'*64,Config=dict(Image='actual-image',Hostname='original-host',User='1000:1000',Env=[]),HostConfig={},Mounts=[],NetworkSettings=dict(Networks={}))
        # Inspect-row fixture; the exact real static implementation returns bytes.
        runtime=object.__new__(parent.ConfiguredRuntime);runtime.baseline={'native':native}
        document=dict(self.doc,runtime_profile_sha256=self.m.sha(runtime.static(native)))
        self.assertIs(type(runtime.static(native)),bytes);self.m._verify_runtime_receipt(document,runtime)
        for field in ('Id','Image','Config'):
            old=native[field]
            native[field]=('7'*64 if field=='Id' else 'sha256:'+'6'*64 if field=='Image' else dict(old,Hostname='foreign-host'))
            with self.assertRaises(self.m.Held):self.m._verify_runtime_receipt(document,runtime)
            native[field]=old
        bad=dict(document,profile='a'*64)
        with self.assertRaisesRegex(self.m.Held,'logical-policy'):self.m._verify_runtime_receipt(bad,runtime)
        self.assertEqual(document['profile'],self.m.LOGICAL_PROFILE_SHA)
        self.assertNotEqual(document['profile'],document['runtime_profile_sha256'])
    def test_pack_receipt_binds_worker_image_and_profile(self):
        parent=self.m.load_original_installation().close()['modules']['comic_retained_standalone_parent.py']
        runtime=object.__new__(parent.ConfiguredRuntime)
        worker=dict(Id='5'*64,Image='sha256:'+'e'*64,Config={},HostConfig={},Mounts=[],NetworkSettings=dict(Networks={}))
        native=dict(worker,Id='3'*64,Image='sha256:'+'6'*64)
        runtime.baseline=dict(native=native,worker=worker)
        document=dict(self.doc,kind='pack-root-deployment-v1',profile=self.m.PACK_PROFILE_SHA,
                      runtime_profile_sha256=self.m.sha(runtime.static(worker)))
        self.m._verify_runtime_receipt(document,runtime)
        document['image']='6'*64
        with self.assertRaisesRegex(self.m.Held,'image-receipt'):self.m._verify_runtime_receipt(document,runtime)
        document['image']='e'*64;document['runtime_profile_sha256']=self.m.sha(runtime.static(native))
        with self.assertRaisesRegex(self.m.Held,'profile-receipt'):self.m._verify_runtime_receipt(document,runtime)
        document['profile']=self.m.LOGICAL_PROFILE_SHA
        with self.assertRaisesRegex(self.m.Held,'logical-policy'):self.m._verify_runtime_receipt(document,runtime)

    def test_timestamp_valid_poisoned_bytecode_cannot_replace_verified_source(self):
        import py_compile,marshal
        leaf=self.pkg/'private_crypto.py';cache=Path(py_compile.compile(str(leaf),doraise=True));header=cache.read_bytes()[:16]
        cache.write_bytes(header+marshal.dumps(compile("raise RuntimeError('poisoned-cache-executed')",str(leaf),'exec')))
        original=leaf.read_bytes();result=self.m.load_original_installation()
        self.assertEqual(leaf.read_bytes(),original)
        self.assertIsNotNone(result.close()['modules']['private_crypto.py']._HostExperiment)

    def test_explicit_fixture_original_installation_sources(self):
        result=self.m.load_original_installation();row=result.close();self.assertEqual(row['document']['deployment'],'d'*64)
        self.assertIsNone(row['modules']['comic_retained_standalone_parent.py'].PARENT_SOURCE_SHA256)
    def test_unprovisioned_defaults_refuse_before_any_read(self):
        self.enrollment.unlink()
        with patch.object(self.m.os,'open',side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(self.m.Held,'unprovisioned'):self.m.load_original_installation()
    def test_constructor_saved_json_cannot_mint(self):
        with self.assertRaises(self.m.Held):self.m.Installation(self.doc)
        with self.assertRaises(self.m.Held):object.__new__(self.m.Installation).close()
    def test_linked_private_key_refuses(self):
        os.link(self.key,self.root/'alias')
        with self.assertRaisesRegex(self.m.Held,'root-file'):self.m.load_original_installation()
    def test_root_receipt_wrong_digest_refuses(self):
        self.enroll('0'*64)
        with self.assertRaisesRegex(self.m.Held,'installation-digest'):self.m.load_original_installation()
    def test_original_source_after_last_read_callback_refuses(self):
        real=self.m.read;fired=[]
        def change(path,frame):
            data=real(path,frame)
            if Path(path).name=='comic_retained_standalone_broker.py':
                fired.append(True);(self.pkg/'private_crypto.py').chmod(0o640)
            return data
        with patch.object(self.m,'read',change),self.assertRaisesRegex(self.m.Held,'original-file'):self.m.load_original_installation()
        self.assertTrue(fired)
    def test_changed_original_receipt_after_loading_refuses(self):
        result=self.m.load_original_installation();self.file.chmod(0o640)
        with self.assertRaisesRegex(self.m.Held,'original-file'):result.close()
    def test_last_raw_callback_original_source_drift_refuses(self):
        result=self.m.load_original_installation();real=self.m.raw;fired=[]
        def change(frame):
            real(frame);fired.append(True);(self.pkg/'private_crypto.py').chmod(0o640)
        with patch.object(self.m,'raw',change),self.assertRaisesRegex(self.m.Held,'final-file'):result.close()
        self.assertTrue(fired)
    def test_original_registry_frame_replacement_refuses(self):
        result=self.m.load_original_installation();row=self.m._INSTALLATIONS[result]
        row['frame']=((),())
        with self.assertRaisesRegex(self.m.Held,'logical'):result.close()
    def test_last_raw_callback_module_replacement_refuses(self):
        result=self.m.load_original_installation();real=self.m.raw
        def change(frame):
            real(frame);self.m._INSTALLATIONS[result]['modules']['private_crypto.py']=object()
        with patch.object(self.m,'raw',change),self.assertRaisesRegex(self.m.Held,'module-identity'):result.close()

    def test_last_raw_callback_document_drift_refuses(self):
        result=self.m.load_original_installation();real=self.m.raw
        def change(frame):
            real(frame);self.m._INSTALLATIONS[result]['document']['image']='0'*64
        with patch.object(self.m,'raw',change),self.assertRaisesRegex(self.m.Held,'document-value'):result.close()

    def publication(self,state='held',reason='startup-restart-required'):
        census=dict(version=1,epoch='9'*64,revision=0,keys=[],digest=hashlib.sha256(b'[]').hexdigest())
        return dict(version=1,state=state,reason=reason,census=census)
    def test_exact_recovery_startup_hold_observation_only(self):
        self.m._recovery_publication(self.publication())
        self.m._recovery_publication(self.publication('ready','verified'))
    def test_every_other_held_reason_refuses(self):
        for reason in ('media-pending','writer-busy','authority-unavailable','verified'):
            with self.subTest(reason=reason),self.assertRaisesRegex(self.m.Held,'held-reason'):self.m._recovery_publication(self.publication(reason=reason))
    def test_missing_foreign_or_boolean_census_refuses(self):
        for field,value in (('revision',True),('digest','0'*64),('keys',['1'*64])):
            status=self.publication();status['census'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(self.m.Held,'current-census'):self.m._recovery_publication(status)
        status=self.publication();status['census']=None
        with self.assertRaisesRegex(self.m.Held,'current-census'):self.m._recovery_publication(status)

    def test_foreign_host_graph_source_refuses(self):
        self.doc['host_sources']['private_crypto.py']='0'*64
        self.doc['broker_sources']=hashlib.sha256(json.dumps(self.doc['host_sources'],sort_keys=True,separators=(',',':')).encode()).hexdigest();self.write()
        self.enroll()
        with self.assertRaisesRegex(self.m.Held,'source-digest'):self.m.load_original_installation()


    def test_original_launch_tail_projection_mechanics_and_registry_refusal(self):
        # Explicit mechanics fixture, not Docker/profile/launch authority acceptance.
        import subprocess,time,threading,copy
        installation=self.m.load_original_installation();row=installation.close();parent=row['modules']['comic_retained_standalone_parent.py']
        process=subprocess.Popen([sys.executable,'-I','-B','-c','pass'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);process.wait(timeout=10)
        self.addCleanup(process.stdin.close);self.addCleanup(process.stdout.close);self.addCleanup(process.stderr.close)
        runtime=object.__new__(parent.ConfiguredRuntime);runtime.process=process;runtime.selected='6'*64;runtime.selected_started='original-start';runtime.selected_pid=process.pid;runtime.selected_static=b'original-profile'
        observation=patch.object(parent.ConfiguredRuntime,'close',lambda *args: None)
        observation.start();self.addCleanup(observation.stop)  # Declared class observation double only.
        terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,process);registry=b'original-runtime-seal'
        parent._RUNTIMES[runtime]=registry;parent._TERMINALS[runtime]=terminal
        obj=object.__new__(self.m.OriginalLaunch);frame=((),(),())
        state=dict(installation=installation,runtime=runtime,process=process,cid=runtime.selected,started=runtime.selected_started,selected_pid=process.pid,start='unused-after-exit',attach_pid=process.pid,owner=(os.getpid(),threading.get_ident()),deadline=time.monotonic()+30,pipes=tuple((stream.fileno(),self.m.nine(os.fstat(stream.fileno()))) for stream in (process.stdin,process.stdout)),stdin=process.stdin,stdout=process.stdout,bootframe=frame,inputframe=frame,boot={'original':['value']},preflight={'source':'original'},recovery={'census':[]},admission='a'*64,sequence=6,previous=b'original',auth_challenge='b'*64)
        seal=(state,dict(objects=tuple((key,state[key]) for key in ('installation','runtime','process','stdin','stdout')),values=(),boot=copy.deepcopy(state['boot']),preflight=copy.deepcopy(state['preflight']),recovery=copy.deepcopy(state['recovery']),runtime_registry=registry,runtime_table=parent._RUNTIMES,terminal_table=parent._TERMINALS))
        self.m._LAUNCHES[obj]=state;self.m._LAUNCH_SEALS[obj]=seal;self.m._PHASES[obj]=tuple(state[key] for key in ('deadline','admission','sequence','previous','auth_challenge'));self.m._EXITS[obj]=terminal
        self.assertIs(obj.close(),state)
        real=self.m.raw
        for table,value,reason in ((parent._TERMINALS,('foreign',),'terminal-registry'),(parent._RUNTIMES,b'foreign','runtime-registry')):
            fired=[]
            def change(frame):
                real(frame)
                if not fired:table[runtime]=value;fired.append(True)
            with patch.object(self.m,'raw',change),self.assertRaisesRegex(self.m.Held,reason):obj.close()
            self.assertTrue(fired);parent._TERMINALS[runtime]=terminal;parent._RUNTIMES[runtime]=registry


class WriteOrderingTests(unittest.TestCase):
    """Actual pipe mechanics with explicit signer/runtime doubles; no launch grant."""
    def setUp(self):
        self.m=load(HERE/'source/comic_retained_standalone_broker.py','ordering_fixture')
        self.read_fd,self.write_fd=os.pipe()
        self.addCleanup(os.close,self.read_fd);self.addCleanup(os.close,self.write_fd)
        self.written=False;self.waited=False
        owner=self
        class Stream:
            def fileno(inner):return owner.write_fd
        class Process:
            def wait(inner,**kwargs):owner.waited=True;return 0
        class Runtime:pass
        runtime=Runtime();runtime.selected='selected';runtime.selected_started='started'
        runtime.selected_static=b'profile'
        class Installation:
            def close(inner):
                class Parent:pass
                parent=Parent();parent._TERMINALS={}
                return dict(document=dict(kind='standalone-root-deployment-v1'),
                            modules={'comic_retained_standalone_parent.py':parent})
        import time
        self.state=dict(stdin=Stream(),process=Process(),runtime=runtime,installation=Installation(),
            sequence=5,boot=dict(nonce='a'*64,challenge='b'*64),session='c'*64,admission='d'*64,
            auth_challenge='e'*64,previous=b'',deadline=time.monotonic()+30)
        class Launch:
            def close(inner):
                if owner.written:raise owner.m.Held('synthetic original drift')
                return owner.state
        self.launch=Launch()
        write=os.write
        def changed(fd,data):
            result=write(fd,data)
            if fd==self.write_fd:self.written=True
            return result
        self.writer=patch.object(self.m.os,'write',changed)
        self.writer.start();self.addCleanup(self.writer.stop)
    def test_original_frame_closes_before_delimiter(self):
        with self.assertRaisesRegex(self.m.Held,'synthetic original drift'):
            self.m._send_original(self.launch,b'original')
        os.set_blocking(self.read_fd,False)
        self.assertEqual(os.read(self.read_fd,1024),b'original')
    def test_exit_permission_closes_before_delimiter_and_wait(self):
        with patch.object(self.m,'_signed',return_value=(b'original',b'assertion',b'signature')):
            with self.assertRaisesRegex(self.m.Held,'synthetic original drift'):
                self.m._send_stage(self.launch,6,'observed-exit',{},exit_permission=True)
        os.set_blocking(self.read_fd,False)
        self.assertEqual(os.read(self.read_fd,1024),b'original')
        self.assertFalse(self.waited)


class PackSuccessorTests(unittest.TestCase):
    """Actual complete-census validator with synthetic preserved state."""
    def setUp(self):
        self.m=load(HERE/'source/comic_retained_standalone_broker.py','pack_successor_fixture')
        self.root=tempfile.TemporaryDirectory();self.addCleanup(self.root.cleanup)
        self.path=Path(self.root.name);(self.path/'keep').write_bytes(b'original')
        (self.path/'database').write_bytes(b'before');(self.path/'receipt').write_bytes(b'before')
        self.primitive=load(OLD/'comic_reader_backup_primitives.py','pack_successor_primitive')
        self.before=self.rows()
    def rows(self):return self.primitive.inventory(self.path,'tree')[0]
    def verify(self,rows,**overrides):
        args=dict(changed={},new_files=set(),new_directories=set());args.update(overrides)
        return self.m._pack_scope_successor(self.before,rows,**args)
    def test_complete_unchanged_scope_accepts(self):self.verify(self.rows())
    def test_unrelated_payload_metadata_namespace_and_inode_drift_refuse(self):
        import copy
        rows=self.rows()
        for change in ('payload','metadata','inode','extra','missing'):
            current=copy.deepcopy(rows);selected=next(r for r in current if r['path']=='keep')
            if change=='payload':selected['sha256']='0'*64
            elif change=='metadata':selected['attributes']['uid']+=1
            elif change=='inode':selected['stamp'][1]+=1
            elif change=='extra':current.append(dict(selected,path='extra'))
            else:current.remove(selected)
            with self.subTest(change=change),self.assertRaises(self.m.Held):self.verify(current)
    def test_SQL_inode_preserved_but_explicit_receipt_replacement_allowed(self):
        rows=self.rows();selected=next(r for r in rows if r['path']=='receipt')
        selected['stamp'][1]+=1;selected['sha256']='0'*64
        self.verify(rows,changed={'receipt':'replace'})
        with self.assertRaises(self.m.Held):self.verify(rows,changed={'receipt':'sqlite'})
        selected['attributes']['mode']^=0o040
        with self.assertRaises(self.m.Held):self.verify(rows,changed={'receipt':'replace'})
    def test_only_private_owned_finite_journal_additions_allowed(self):
        import copy
        rows=self.rows();base=next(r for r in rows if r['path']=='keep')
        added=copy.deepcopy(base);added.update(path='journal',sha256='1'*64)
        added['attributes'].update(mode=0o600,uid=1000,gid=1000)
        added['stamp'][5:9]=[0o100600,1000,1000,1];rows.append(added)
        self.verify(rows,new_files={'journal'})
        for field,value in (('uid',0),('mode',0o644)):
            changed=copy.deepcopy(rows);changed[-1]['attributes'][field]=value
            with self.subTest(field=field),self.assertRaises(self.m.Held):self.verify(changed,new_files={'journal'})
        with self.assertRaises(self.m.Held):self.verify(rows,new_files={'another'})
    def test_failed_run_uses_original_release_and_preserves_primary_error(self):
        m=self.m;calls=[];foreign=[];fds=os.pipe()
        class Image:
            def __init__(inner,fd):inner.fd=fd
            def release(inner):
                calls.append(inner.fd);os.close(inner.fd)
                raise ValueError('Synthetic original cleanup uncertainty')
        images=tuple(Image(fd) for fd in fds)
        document=dict(kind='pack-root-deployment-v1')
        row=dict(document=document,modules={'comic_retained_pack_parent.py':object()})
        state=dict(installation=SimpleNamespace(close=lambda:row),worker_image=images[0],native_image=images[1])
        launch=object.__new__(m.OriginalLaunch);primary=OSError('Synthetic run failure')
        def failed(_):
            Image.release=lambda image:foreign.append(image.fd)
            raise primary
        try:
            with patch.object(m.OriginalLaunch,'close',return_value=state),patch.object(m,'_run_pack_original',failed):
                with self.assertRaises(OSError) as error:m.run_original(launch)
            self.assertIs(error.exception,primary);self.assertEqual(calls,list(fds));self.assertEqual(foreign,[])
            for fd in fds:
                with self.assertRaises(OSError):os.fstat(fd)
        finally:
            for fd in fds:
                try:os.close(fd)
                except OSError:pass

    def test_native_journal_container_paths_are_mapped_before_host_census(self):
        # Real mapping mechanism from the standalone parent, with ordinary
        # differing host/container paths rather than identity mounts.
        with patch.dict(sys.modules):
            load(OLD/'comic_retained_standalone_backup.py','comic_retained_standalone_backup')
            mapping=load(OLD/'comic_retained_standalone_parent.py','journal_namespace_parent')
        mounts=[dict(Type='bind',Source='/srv/native',Destination='/config',RW=True)]
        folder=Path('/srv/native/data/retained-delivery-v1')/('a'*64)
        names=('intent.json','accepted.json','issued.json','target-preserved.cbz','target-restored.cbz')
        files={str(Path('/config/data/retained-delivery-v1')/('a'*64)/name):[] for name in names}
        files['/app/mylar3/mylar/api.py']=[]
        result=self.m._pack_native_journal(mapping,files,{},mounts,folder,Path('/srv/native'))
        self.assertEqual(result,{str(Path('data/retained-delivery-v1')/('a'*64)/name) for name in names})

    def test_detached_vectors_join_actual_bind_and_image_facts(self):
        class Image:
            def data(inner):return {'/app/source.py':dict(signature9=[1,2,3,4,5,0o100444,0,0,1],sha256='a'*64,attrs={})}
            def nodes(inner):return {'/':[1,1,0o40755,0,0]}
            def close(inner):pass
        stamp=[1,3,4,5,6,0o100600,1000,1000,1]
        facts=dict(files={'/host/file':stamp},nodes={'/host':[1,4,0o40700,1000,1000]},names={'/host':['file']},hashes={'/host/file':'b'*64},attrs={'/host/file':{}})
        mounts=[dict(Source='/host',Destination='/state')]
        frame=dict(files={'/state/file':stamp},nodes={'/state':facts['nodes']['/host']},names={'/state':['file']},hashes={'/state/file':'b'*64,'/app/source.py':'a'*64},absent=['/state/absent'])
        self.m._pack_join_vectors(frame,mounts=mounts,facts=facts,image=Image())
        frame['absent']=['/state/file']
        with self.assertRaises(self.m.Held):self.m._pack_join_vectors(frame,mounts=mounts,facts=facts,image=Image())
        frame['absent']=[];frame['hashes']['/state/file']='c'*64
        with self.assertRaises(self.m.Held):self.m._pack_join_vectors(frame,mounts=mounts,facts=facts,image=Image())


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.m=load(HERE/'source/comic_retained_standalone_broker.py','mapping_fixture')
        self.file=self.root/'config.ini';self.file.write_bytes(b'original')
        self.ref=dict(path='/data/config.ini',sha256=hashlib.sha256(b'original').hexdigest(),signature9=list(self.m.nine(self.file.lstat())))
        self.mounts=[dict(Type='bind',Source=str(self.root),Destination='/data',RW=True)]
    def tearDown(self):self.tmp.cleanup()
    def native_transport(self):
        # Explicit installation/runtime/CLI doubles test transport closure only.
        # They grant no Root enrollment, real HTTP or lifecycle acceptance.
        m=self.m;helper=self.root/'comic_retained_native_control.py';helper.write_bytes(b'# public fixed helper\n')
        frame=(((helper,m.nine(helper.lstat())),),tuple((p,m.five(p.lstat())) for p in helper.parents))
        config_frame=(((self.file,m.nine(self.file.lstat())),),tuple((p,m.five(p.lstat())) for p in self.file.parents))
        parent=SimpleNamespace(read_original=lambda ref,**kwargs:(b'original',config_frame),raw=m.raw)
        worker=dict(Image='sha256:'+'e'*64,Mounts=[]);native=dict(Image='sha256:'+'f'*64,Mounts=self.mounts)
        self.closed=[]
        owner=self
        class Runtime:
            static=staticmethod(m.canonical)
            def close(inner):owner.closed.append('runtime')
        runtime=Runtime();runtime.ids=dict(native='1'*64,reader='2'*64,worker='3'*64)
        runtime.baseline=dict(native=native,worker=worker)
        parent.ConfiguredRuntime=Runtime;parent._RUNTIMES={runtime:b'explicit-test-registry'}
        document=dict(kind='pack-root-deployment-v1',profile=m.PACK_PROFILE_SHA,image='e'*64,
            runtime_profile_sha256=m.sha(runtime.static(worker)),ids=runtime.ids,native_config_ref=self.ref,
            host_sources={'comic_retained_native_control.py':m.sha(helper.read_bytes())})
        row=dict(document=document,modules={'comic_retained_pack_parent.py':parent},frame=frame,deadline=m.time.monotonic()+30)
        installation=object.__new__(m.Installation)
        def original(_):self.closed.append('installation');return row
        for context in (patch.object(m,'PACKAGE',self.root),patch.object(m.Installation,'close',original)):
            context.start();self.addCleanup(context.stop)
        session=dict(nonce='a'*64,version=1,kind='retained-native-session-v1',action='observe',request={},proof=None)
        answer=dict(version=1,kind='root-retained-native-control-result-v1',nonce=session['nonce'],
            config_signature9=self.ref['signature9'],response_sha256='b'*64,response={'success':True,'data':{}})
        return installation,runtime,session,answer,helper

    def test_native_transport_fixed_owner_original_deadline_and_closed_sources(self):
        installation,runtime,session,answer,_=self.native_transport()
        calls=[]
        def run(args,**kwargs):
            calls.append((args,kwargs));return SimpleNamespace(stdout=self.m.canonical(answer)+b'\n',stderr=b'')
        with patch.object(self.m.subprocess,'run',run):
            self.assertEqual(self.m.parse(self.m.native_control_original(installation,runtime,session)),answer)
        args,options=calls[0]
        self.assertEqual(args[:6],['docker','exec','--interactive','--user','1000:1000',runtime.ids['native']])
        self.assertEqual(args[6:10],['python3','-I','-B','-c'])
        packet=self.m.parse(options['input']);self.assertEqual(packet['config_ref'],self.ref)
        self.assertEqual(packet['session'],session);self.assertGreater(packet['deadline'],self.m.time.monotonic())
        self.assertTrue(options['check']);self.assertTrue(options['capture_output']);self.assertGreaterEqual(self.closed.count('runtime'),3)

    def test_native_transport_refuses_incomplete_or_failed_child_without_replay(self):
        installation,runtime,session,answer,_=self.native_transport()
        for result in (SimpleNamespace(stdout=self.m.canonical(answer),stderr=b''),
                       SimpleNamespace(stdout=self.m.canonical(dict(answer,nonce='c'*64))+b'\n',stderr=b''),
                       SimpleNamespace(stdout=self.m.canonical(answer)+b'\n',stderr=b'private diagnostic')):
            with self.subTest(result=result),patch.object(self.m.subprocess,'run',return_value=result) as run:
                with self.assertRaises(self.m.Held):self.m.native_control_original(installation,runtime,session)
                run.assert_called_once()
        with patch.object(self.m.subprocess,'run',side_effect=self.m.subprocess.CalledProcessError(2,['docker'])) as run:
            with self.assertRaisesRegex(self.m.Held,'native-control-held'):self.m.native_control_original(installation,runtime,session)
            run.assert_called_once()

    def test_native_transport_recloses_helper_after_response(self):
        installation,runtime,session,answer,helper=self.native_transport()
        def changed(*args,**kwargs):
            helper.chmod(0o600 if helper.stat().st_mode&0o777!=0o600 else 0o400)
            return SimpleNamespace(stdout=self.m.canonical(answer)+b'\n',stderr=b'')
        with patch.object(self.m.subprocess,'run',changed),self.assertRaisesRegex(self.m.Held,'original-file'):
            self.m.native_control_original(installation,runtime,session)

    def test_native_transport_refuses_foreign_runtime_before_its_callback(self):
        installation,runtime,session,_,_=self.native_transport()
        foreign=SimpleNamespace(**runtime.__dict__,close=lambda:self.fail('foreign callback'))
        with patch.object(self.m.subprocess,'run') as run:
            with self.assertRaisesRegex(self.m.Held,'original-runtime'):self.m.native_control_original(installation,foreign,session)
            run.assert_not_called()
        parent=installation.close()['modules']['comic_retained_pack_parent.py'];parent._RUNTIMES.pop(runtime)
        self.closed.clear()
        with self.assertRaisesRegex(self.m.Held,'original-runtime'):self.m.native_control_original(installation,runtime,session)
        self.assertNotIn('runtime',self.closed)
        parent._RUNTIMES[runtime]=b'explicit-test-registry';runtime.ids=dict(runtime.ids,native='9'*64)
        self.closed.clear()
        with self.assertRaisesRegex(self.m.Held,'runtime-IDs'):self.m.native_control_original(installation,runtime,session)
        self.assertNotIn('runtime',self.closed)

    def test_control_reference_refuses_noncanonical_or_nonfile_before_mapping(self):
        self.assertIs(self.m.native_config_reference(self.ref),self.ref)
        variants=[dict(self.ref,path=p) for p in ('relative','//data/config.ini','/data/../config.ini','/data//config.ini')]
        variants+=[dict(self.ref,sha256=True),dict(self.ref,signature9=[True]*9),dict(self.ref,foreign=True)]
        for index,value in ((2,0),(2,2*1024**2+1),(5,0o40700),(8,2)):
            vector=list(self.ref['signature9']);vector[index]=value;variants.append(dict(self.ref,signature9=vector))
        for value in variants:
            with self.subTest(reference=value),self.assertRaises(self.m.Held):self.m.native_config_reference(value)
    def test_archive_mapping_preserves_large_hardlinked_original_refs(self):
        # This mapper also serves standalone source/target archives. Native INI
        # limits must not silently narrow those existing exact-ref contracts.
        with self.file.open('r+b') as stream:stream.truncate(self.m.SOURCE_LIMIT+1)
        os.link(self.file,self.root/'retained-alias')
        reference=dict(self.ref,signature9=list(self.m.nine(self.file.lstat())),
                       sha256=hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(self.m._host_original_ref(reference,self.mounts)['signature9'],reference['signature9'])
        with self.assertRaisesRegex(self.m.Held,'native-config-file'):self.m.native_config_reference(reference)
    def test_differing_paths_preserve_child_reference(self):
        original=json.dumps(self.ref,sort_keys=True)
        host=self.m._host_original_ref(self.ref,self.mounts)
        self.assertEqual(host['path'],str(self.file));self.assertEqual(host['signature9'],self.ref['signature9']);self.assertEqual(host['sha256'],self.ref['sha256'])
        self.assertEqual(json.dumps(self.ref,sort_keys=True),original)
    def test_changed_original_full9_refuses(self):
        self.file.chmod(0o640)
        with self.assertRaisesRegex(self.m.Held,'original-nine'):self.m._host_original_ref(self.ref,self.mounts)
    def test_misleading_physical_mount_refuses(self):
        other=self.root/'other';other.mkdir();(other/'config.ini').write_bytes(b'original')
        self.mounts[0]['Source']=str(other)
        with self.assertRaisesRegex(self.m.Held,'original-nine'):self.m._host_original_ref(self.ref,self.mounts)
    def test_named_volume_physical_mapping_and_missing_name_refuse(self):
        volume=dict(self.mounts[0],Type='volume',Name='existing-data')
        self.assertEqual(self.m._host_original_ref(self.ref,[volume])['path'],str(self.file))
        for bad in (None,'../foreign',''):
            volume['Name']=bad
            with self.assertRaisesRegex(self.m.Held,'volume-name'):self.m._host_original_ref(self.ref,[volume])
    def test_existing_volume_inspect_requires_exact_name_and_source(self):
        mount=dict(self.mounts[0],Type='volume',Name='existing-data')
        row=dict(Name='existing-data',Mountpoint=str(self.root),Driver='local',Scope='local',Options=None)
        class Runtime:
            def command(inner,args):
                self.assertEqual(args,['volume','inspect','existing-data'])
                return json.dumps([row]).encode()
        runtime=Runtime();self.m._existing_volume_original(runtime,mount)
        for key,bad in (('Name','stale-data'),('Mountpoint','/foreign'),('Driver','remote'),('Scope','global')):
            old=row[key];row[key]=bad
            with self.assertRaisesRegex(self.m.Held,'existing-volume'):self.m._existing_volume_original(runtime,mount)
            row[key]=old
    def test_last_original_file_callback_mapping_or_ref_drift_refuses(self):
        for field in ('mount','reference'):
            mounts=[dict(self.mounts[0])];reference=dict(self.ref);reference['signature9']=list(self.ref['signature9']);real=self.m.os.lstat;fired=[]
            def change(path):
                result=real(path)
                if Path(path)==self.file:
                    fired.append(True)
                    if field=='mount':mounts[0]['Source']+='/.'
                    else:reference['path']='/foreign/config.ini'
                return result
            with patch.object(self.m.os,'lstat',change),self.assertRaisesRegex(self.m.Held,'original-mapping'):self.m._host_original_ref(reference,mounts)
            self.assertTrue(fired)
    def test_shadow_ambiguity_and_unmapped_refuse(self):
        for extra in (dict(Type='bind',Source=str(self.root),Destination='/',RW=True),dict(self.mounts[0])):
            with self.assertRaises(self.m.Held):self.m._host_original_ref(self.ref,[*self.mounts,extra])
        with self.assertRaisesRegex(self.m.Held,'unmapped'):self.m._host_original_ref(self.ref,[])

if __name__=='__main__':unittest.main()

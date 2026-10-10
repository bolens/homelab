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
        self.write();self.enroll()
        # This explicit unit-test projection is not a production installation grant.
        self.settings=patch.multiple(self.m,ROOT_UID=os.geteuid(),PACKAGE=self.pkg,KEY=self.key,INSTALLATION=self.file,
                                     ENROLLMENT=self.enrollment)
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
        runtime.close=lambda *args: None  # Declared runtime observation fixture only.
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


class MappingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.m=load(HERE/'source/comic_retained_standalone_broker.py','mapping_fixture')
        self.file=self.root/'config.ini';self.file.write_bytes(b'original')
        self.ref=dict(path='/data/config.ini',sha256=hashlib.sha256(b'original').hexdigest(),signature9=list(self.m.nine(self.file.lstat())))
        self.mounts=[dict(Type='bind',Source=str(self.root),Destination='/data',RW=True)]
    def tearDown(self):self.tmp.cleanup()
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

"""Disposable files and explicit engine/daemon doubles; never live observations."""
import copy
import hashlib
import importlib.util
import json
import sqlite3
import types
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).parent.parent

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=load('comic_native_process_probe');a=load('comic_native_evidence_adapter')

class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
        self.data=self.root/'config';self.data.mkdir();self.config=self.data/'config.ini'
        self.config.write_text('[General]\napi_key='+'k'*32+'\napi_enabled=1\nhttp_port=8090\nhttp_root=/mylar\nenable_https=0\ndestination_dir=/data/comics\n')
        self.proc=self.root/'proc';self.proc.mkdir();d=self.proc/'123';d.mkdir()
        self.argv=['/lsiopy/bin/python3','/app/mylar3/Mylar.py','--datadir',str(self.data)]
        (d/'cmdline').write_bytes(b'\0'.join(x.encode() for x in self.argv)+b'\0')
        (d/'stat').write_text('123 (mylar) '+' '.join(['S']+['0']*18+['987']+['0']*5))
        self.modules={};self.pins={}
        for name in ('worker_health.py','native_writers.py'):
            f=self.root/name;f.write_text('x=1\n');key='/app/mylar3/mylar/'+name;self.modules[key]=f;self.pins[key]=hashlib.sha256(f.read_bytes()).hexdigest()
        self.req=dict(version=1,nonce='a'*64,source_sha256='b'*64,seconds=60,module_pins=self.pins)
        self.publication=dict(state='held',reason='startup-restart-required',census={})
    def run_probe(self,transport=None):
        original=p.Reads.read
        def mapped(obj,path):return original(obj,self.modules.get(str(path),path))
        with patch.object(p.Reads,'read',mapped):
            return p.decode(p.capture(self.req,proc=self.proc,transport=transport or self.transport))
    def transport(self,url,body,seconds):
        self.assertEqual(url,'http://127.0.0.1:8090/mylar/api');self.assertIn(b'cmd=getHealth',body);self.assertIn(b'apikey=',body)
        return dict(success=True,data=dict(publication=copy.deepcopy(self.publication)))
    def test_actual_proc_and_daemon_output(self):
        value=self.run_probe();self.assertEqual(value['process']['start_ticks'],987);self.assertEqual(value['process']['pid'],123)
        self.assertNotIn('k'*32,json.dumps(value));self.assertEqual(value['config']['sha256'],hashlib.sha256(self.config.read_bytes()).hexdigest())
    def test_duplicate_daemon_refused(self):
        d=self.proc/'124';d.mkdir();(d/'cmdline').write_bytes((self.proc/'123'/'cmdline').read_bytes());(d/'stat').write_text((self.proc/'123'/'stat').read_text().replace('123','124',1))
        with self.assertRaises(p.Held):self.run_probe()
    def test_last_health_changes_config_mode_refused(self):
        def transport(*args):value=self.transport(*args);self.config.chmod(0o640);return value
        self.config.chmod(0o600)
        with self.assertRaises(p.Held):self.run_probe(transport)
    def test_last_health_replaces_config_same_bytes_refused(self):
        def transport(*args):value=self.transport(*args);raw=self.config.read_bytes();self.config.unlink();self.config.write_bytes(raw);return value
        with self.assertRaises(p.Held):self.run_probe(transport)
    def test_restart_during_health_refused(self):
        def transport(*args):value=self.transport(*args);f=self.proc/'123'/'stat';f.write_text(f.read_text().replace('987','988'));return value
        with self.assertRaises(p.Held):self.run_probe(transport)
    def test_daemon_absent_publication_refused(self):
        with self.assertRaises(p.Held):self.run_probe(lambda *args:dict(success=True,data={}))
    def test_daemon_API_failure_refused(self):
        with self.assertRaises(p.Held):self.run_probe(lambda *args:dict(success=False,data={}))
    def test_disable_API_refused(self):
        self.config.write_text(self.config.read_text().replace('api_enabled=1','api_enabled=0'))
        with self.assertRaises(p.Held):self.run_probe()
    def test_https_refused(self):
        self.config.write_text(self.config.read_text().replace('enable_https=0','enable_https=1'))
        with self.assertRaises(p.Held):self.run_probe()
    def test_prefix_redirect_spelling_refused(self):
        self.config.write_text(self.config.read_text().replace('/mylar','/mylar?bad'))
        with self.assertRaises(p.Held):self.run_probe()
    def test_source_module_pin_refused(self):
        self.pins[next(iter(self.pins))]='c'*64
        with self.assertRaises(p.Held):self.run_probe()
    def test_redirect_denied(self):
        with self.assertRaises(p.Held):p.NoRedirect().redirect_request(None,None,None,None,None,None)

class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name)
        self.config=self.root/'config';self.config.mkdir();(self.config/'config.ini').write_text('[General]\ndestination_dir=/data/comics\n')
        self.library=self.root/'comics';self.library.mkdir()
        def row(cid,status):
            return dict(Id=cid*64,Image='sha256:'+'b'*64,Name='fixture',Path='/init',Args=[],Config={},HostConfig={},NetworkSettings={},
                        Mounts=[dict(Type='bind',Source=str(self.config),Destination='/config/mylar',RW=False),dict(Type='bind',Source=str(self.library),Destination='/data/comics',RW=False)],
                        State=dict(Running=status=='running',Status=status,Pid=999 if status=='running' else 0,StartedAt='start',Paused=False,Restarting=False,Dead=False,OOMKilled=False))
        self.values=dict(reader=row('1','exited'),held_native=row('2','running'),held_worker=row('3','created'));self.child=row('4','running')
        self.plan=dict(nonce='a'*64,operation=str(self.root),selected_image=self.child['Image'],native={'roots':['/data/comics']})
        def ref(path,raw):
            path.write_bytes(raw);path.chmod(0o600);return dict(path=str(path),sha256=hashlib.sha256(raw).hexdigest(),signature9=list(a.nine(path.lstat())))
        sdk=ref(self.root/'sdk.json',a.encode({'publication_native_configured_scope.py':a.SCOPE_SHA,'worker_health.py':'c'*64,'native_writers.py':'d'*64}));self.plan['sdk_map']=sdk
        self.plan['producer']=dict(sha256=hashlib.sha256((ROOT/'comic_native_evidence_adapter.py').read_bytes()).hexdigest())
        parentcode=b'def same_runtime(a,b): return {k:v for k,v in a.items() if k != \'State\'}=={k:v for k,v in b.items() if k != \'State\'} and {k:v for k,v in a[\'State\'].items() if k != \'Health\'}=={k:v for k,v in b[\'State\'].items() if k != \'Health\'}\nclass Parent:\n def continuous(self): return self.values\n def inspect(self,cid): return self.child\n'
        self.source=ref(self.root/'parent.py',parentcode);namespace={};exec(compile(parentcode,str(self.root/'parent.py'),'exec'),namespace)
        self.parent=namespace['Parent']();self.parent.values=self.values;self.parent.child=self.child
        self.planref=ref(self.root/'plan.json',a.encode(self.plan));self.req=dict(version=1,phase='native-observation',nonce='a'*64,operation=str(self.root),deadline_monotonic=time.monotonic()+60,parent_source=self.source,parent_plan=self.planref,context=dict(observations=copy.deepcopy(self.values),child=copy.deepcopy(self.child),child_mounts=copy.deepcopy(self.child['Mounts'])))
        census=dict(version=1,epoch='e'*64,revision=0,keys=[],digest=hashlib.sha256(b'[]').hexdigest())
        self.response=dict(version=1,nonce='a'*64,source_sha256=a.PROBE_SHA,process=dict(pid=123,start_ticks=987,argv=['python','/app/mylar3/Mylar.py','--datadir','/config/mylar']),publication=dict(state='held',reason='startup-restart-required',census=census),config=dict(path='/config/mylar/config.ini',sha256=hashlib.sha256((self.config/'config.ini').read_bytes()).hexdigest(),signature9=[0]*9))
    def run_adapter(self,probe=None):
        with patch.object(a,'probe_exec',probe or (lambda *args:copy.deepcopy(self.response))):return a.produce('native-observation',self.req,watch=self.parent.continuous)
    def test_fresh_probe_scope_and_mount_positive(self):self.assertEqual(self.run_adapter()['evidence']['native']['process']['pid'],123)
    def test_between_probe_health_only_allowed_and_fresh_row_returned(self):
        def probe(*args):
            self.values['held_native']['State']['Health']={'Log':['new-health']}
            return copy.deepcopy(self.response)
        self.assertEqual(self.run_adapter(probe)['evidence']['native']['inspect']['State']['Health'],{'Log':['new-health']})

    def pair_fixture(self):
        restore=self.root/'restore';restore.mkdir();current=self.root/'reader';current.mkdir();pairs={};original={}
        for directory,dest in ((current,original),(restore,pairs)):
            for name in ('database.sqlite','tasks.sqlite'):
                path=directory/name
                db=sqlite3.connect(path);db.execute('CREATE TABLE actual(id INTEGER)');db.execute('INSERT INTO actual VALUES(1)');db.commit();db.close()
                dest[name]={'':dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(a.nine(path.lstat())))}
        custody=dict(reader_root=str(current),restore_root=str(restore),current_pairs=original,pairs=pairs)
        roles=['stopped_runtime','backup_ack','backup_manifest','backup_acceptance','rows','schema','reviewed_plan','timestamp_evidence','custody'];controls={}
        for role in roles:
            value=custody if role=='custody' else {'container':self.values['reader']} if role=='stopped_runtime' else {}
            path=self.root/(role+'.json');path.write_bytes(a.encode(value));path.chmod(0o600)
            controls[role]=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(a.nine(path.lstat())))
        self.parent.mapping=types.SimpleNamespace(child=lambda path:str(path))
        self.req['phase']='phase-custody';self.req['context']=dict(backup={},controls=controls,observations=copy.deepcopy(self.values),phase='prepare',invocation={},stage='prebirth')
        return current,restore

    def test_genuine_sqlite_pairs_seed_has_no_host_incarnation(self):
        current,restore=self.pair_fixture();value=a.reader_pair_birth_request(self.req,watch=self.parent.continuous)
        descriptor=value['pairs']['current']['database.sqlite']['']
        self.assertEqual(set(descriptor),{'sha256','attributes'});self.assertNotIn('signature9',descriptor)
        self.assertIsNone(value['pairs']['restore']['tasks.sqlite']['-wal'])
        self.assertEqual(descriptor['sha256'],hashlib.sha256((current/'database.sqlite').read_bytes()).hexdigest())

    def test_current_phase_custody_refuses_host_child_fact_relabel(self):
        self.pair_fixture()
        with self.assertRaisesRegex(a.Held,'child-pair-birth-successor-required'):a.produce('phase-custody',self.req,watch=self.parent.continuous)

    def test_last_pair_deadline_callback_creates_WAL_refused(self):
        current,restore=self.pair_fixture();original=a.deadline;calls=[]
        def late(request):
            value=original(request);calls.append(1)
            if len(calls)==9:(current/'database.sqlite-wal').write_bytes(b'late')
            return value
        with patch.object(a,'deadline',late):
            with self.assertRaisesRegex(a.Held,'prebirth-final-absence'):a.reader_pair_birth_request(self.req,watch=self.parent.continuous)
        self.assertEqual(len(calls),9)

    def test_unapproved_pair_companion_refused(self):
        current,restore=self.pair_fixture();(current/'database.sqlite-wal').write_bytes(b'foreign')
        with self.assertRaisesRegex(a.Held,'pair-absence'):a.reader_pair_birth_request(self.req,watch=self.parent.continuous)

    def test_cached_health_without_startup_hold_denied(self):
        self.response['publication']['state']='ready'
        with self.assertRaises(ValueError):self.run_adapter()
    def test_census_not_complete_denied(self):
        self.response['publication']['census']['revision']=1
        with self.assertRaises(ValueError):self.run_adapter()
    def test_probe_nonce_denied(self):
        self.response['nonce']='b'*64
        with self.assertRaises(a.Held):self.run_adapter()
    def test_config_host_child_digest_mismatch(self):
        self.response['config']['sha256']='f'*64
        with self.assertRaises(a.Held):self.run_adapter()
    def test_probe_callback_native_restart(self):
        def probe(*args):self.values['held_native']['State']['StartedAt']='new';return copy.deepcopy(self.response)
        with self.assertRaises(a.Held):self.run_adapter(probe)
    def test_last_inspect_original_source_chmod(self):
        original=self.parent.inspect;calls=[]
        def inspect(cid):
            calls.append(cid)
            if len(calls)==2:Path(self.source['path']).chmod(0o640)
            return original(cid)
        self.parent.inspect=inspect
        with self.assertRaisesRegex(a.Held,'adapter-final-file'):self.run_adapter()
    def test_selected_child_image_mismatch(self):
        self.child['Image']='sha256:'+'f'*64
        with self.assertRaises(a.Held):self.run_adapter()
    def test_actual_child_same_path_foreign_host_library_refused(self):
        self.child['Mounts'][1]['Source']=str(self.root/'foreign')
        self.req['context']['child']=copy.deepcopy(self.child);self.req['context']['child_mounts']=copy.deepcopy(self.child['Mounts'])
        with self.assertRaisesRegex(a.Held,'child-native-host-geometry'):self.run_adapter()

    def test_multiple_configured_roots_refused(self):
        self.plan['native']['roots'].append('/other')
        path=Path(self.planref['path']);path.write_bytes(a.encode(self.plan));self.planref['sha256']=hashlib.sha256(path.read_bytes()).hexdigest();self.planref['signature9']=list(a.nine(path.lstat()))
        with self.assertRaisesRegex(a.Held,'single-configured-library-required'):self.run_adapter()

    def test_probe_engine_argv_no_shell_no_secret(self):
        class Result:returncode=0;stdout=b'{"ok":true}';stderr=b''
        with patch.object(a.subprocess,'run',return_value=Result()) as run:a.probe_exec('a'*64,b'x=1',{'version':1},2)
        args=run.call_args.args[0];self.assertEqual(args[:6],['pkexec','/usr/bin/docker','--host','unix:///run/docker.sock','exec','--user']);self.assertNotIn('shell',run.call_args.kwargs);self.assertIn('-B',args)
    def test_unimplemented_phase_never_grants(self):
        self.req['phase']='nfs-ready'
        with self.assertRaises(a.Held):a.produce('nfs-ready',self.req,watch=self.parent.continuous)

if __name__=='__main__':unittest.main()

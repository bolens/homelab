"""Genuine local canary objects; explicit engine/daemon/NFS/Writer fixtures only."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

# All source-mode fault injection is confined to this process-private copy.
# The published proposal can be mounted read-only and suites may run in parallel.
import shutil
import atexit
BUNDLE=Path(__file__).parent
_PRIVATE=tempfile.TemporaryDirectory(prefix='nfs-factual-private-sources-')
atexit.register(_PRIVATE.cleanup)
ROOT=Path(_PRIVATE.name)/'source'
shutil.copytree(BUNDLE,ROOT,ignore=shutil.ignore_patterns('__pycache__'))

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

F=load('test_nfs_current_source');A=F.P;P=load('comic_reader_lifecycle_parent');N=load('comic_nfs_factual_successor')

def ref(path,raw=None):
    if raw is not None:path.write_bytes(raw);path.chmod(0o600)
    return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=P.nine(path.lstat()))

class Controls(unittest.TestCase):
    def setUp(self):
        for module in (A,P,N):Path(module.__file__).chmod(0o600)
        self.f=F.FullLifecycleControls();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.canary,self.rows,self.events=self.f.fixture(use_core=True,return_factual=True)
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);base=Path(self.tmp.name);base.chmod(0o700)
        self.x=object.__new__(P.LifecycleParent);x=self.x;x.op=base/'operation';x.op.mkdir(mode=0o700);x.op_fact=tuple(P.five(x.op.lstat()))
        x.source_ref=ref(Path(P.__file__));self.active_source=ref(Path(A.__file__));self.adapter=ref(Path(N.__file__))
        x.plan_ref=ref(base/'plan.json',b'{}');self.active_input=ref(base/'active.json',json.dumps(dict(operation_output=str(base/'different'))).encode())
        x.plan=dict(nonce='a'*64,operation=str(x.op),nfs=dict(adapter=self.adapter,active_parent=self.active_source,active_input=self.active_input),reader=dict(id='c'*64),
                    provider=ref(base/'provider.py',b'# fixture\n'),mounts=[dict(host=str(base),child='/operation-root',write=True)])
        x.mapping=P.Paths(x.plan['mounts']);x.baselines={key:copy.deepcopy(next(r for r in self.rows if r['Name']==name)) for key,name in [('reader','/komga'),('held_native','/mylar3'),('held_worker','/komga-comic-normalizer-1')]}
        for key,row in x.baselines.items():x.plan[key]=dict(id=row['Id'])
        for key in ('producer','observer','sdk_map'):x.plan[key]=ref(base/(key+'.json'),b'{}')
        x.thread=threading.get_ident();x.deadline=time.monotonic()+120;x.phase='admitted';x.event_start='0';x.generated={};x.files={r['path']:tuple(r['signature9']) for r in (x.source_ref,x.plan_ref,self.active_source,self.adapter,self.active_input)};x.nodes={};self.stops=[]
        outer=self
        class Engine:
            def canary(inner,*args,**kwargs):raise AssertionError('factory route explicitly doubled; no protected engine')
            def run(inner,args,seconds):
                if args[0]=='events':return b''
                if args[0]=='inspect':return P.encode([next(r for r in outer.rows if r['Id']==args[1])])
                if args[0]=='stop':
                    outer.stops.append(args)
                    if getattr(outer,'lost_ack',False):raise P.Held('explicit-stop-ACK-lost')
                    r=next(r for r in outer.rows if r['Name']=='/komga');r['State'].update(Status='exited',Running=False,Pid=0,FinishedAt='stopped')
                    return ('c'*64).encode()
                raise AssertionError(args)
        x.engine=Engine();x.core=P.encode(dict(plan=x.plan,files=x.files,nodes=x.nodes,source=x.source_ref,input=x.plan_ref,engine=id(x.engine),thread=x.thread,deadline=x.deadline))
        P._CORES[x]=x.core;P._GENERATED[x]=P.encode(x.generated);P._PHASES[x]={};P._PROJECTORS[x]=lambda v:v
        # Exact checked source is still read; fixture substitutes only one source-bound
        # module instance so the already-genuine canary object shares its exact type.
        q=patch.object(P,'pinned_module',return_value=A);q.start();self.addCleanup(q.stop)
        q=patch.object(A,'run_active_factual',return_value=self.canary);q.start();self.addCleanup(q.stop)
    def active(self):N.run_active(self.x)
    def stopped(self):self.active();N.stop_owned(self.x)
    def request(self):
        x=self.x;inp=x.emit('execute-input.json',dict(fixture=True));command=['/lsiopy/bin/python3','-I','-B',x.mapping.child(x.plan['provider']['path']),'--phase','execute','--input',x.mapping.child(inp['path']),'--input-sha256',inp['sha256'],'--source-sha256',x.plan['provider']['sha256']]
        roles={k:ref(x.op.parent/(k+'.json'),b'{}') for k in P.ROLES}
        return dict(version=1,phase='nfs-ready',nonce=x.plan['nonce'],operation=str(x.op),parent_plan=x.plan_ref,parent_source=x.source_ref,
                    context=dict(input=inp,command=command,context=dict(backup={},controls=roles,observations=x.continuous())))
    def test_real_completed_canary_owning_stop_and_factual_ready(self):
        self.stopped();r=N.nfs_ready(self.x,self.request(),watch=self.x.continuous)
        v=P.decode(P.read(r['evidence']['evidence']));self.assertFalse(v['continuous_action_lock']);self.assertTrue(v['canary_writer_lease_released'])
        for key in ('native_grant','publication_authority','reader_resume_authority','actual_library_platform_verified'):self.assertIs(v[key],False)
        self.assertEqual(len(self.stops),1)
    def test_terminal_dict_cannot_be_canary(self):
        with patch.object(A,'run_active_factual',return_value=self.canary.binding),self.assertRaisesRegex(N.Held,'exact-completed'):self.active()
        self.assertEqual(self.stops,[])
    def test_missing_factory_refuses_before_stop(self):
        with patch.object(A,'run_active_factual',None),self.assertRaisesRegex(N.Held,'factory-required'):self.active()
        self.assertEqual(self.stops,[])
    def test_unknown_stop_ACK_keeps_uncertain_no_replay(self):
        self.active();self.lost_ack=True
        with self.assertRaises(P.Held):N.stop_owned(self.x)
        with self.assertRaisesRegex(N.Held,'owning-phase'):N.stop_owned(self.x)
        self.assertEqual(len(self.stops),1)
    def test_changed_native_process_before_stop_refuses(self):
        self.active();next(r for r in self.rows if r['Name']=='/mylar3')['State']['Pid']+=1
        with self.assertRaises((N.Held,A.Held)):N.stop_owned(self.x)
        self.assertEqual(self.stops,[])
    def test_reappeared_cleanup_after_stop_holds_ready(self):
        self.stopped();request=self.request();path=Path(self.canary.absent[-1]);path.mkdir()
        with self.assertRaises(A.Held):N.nfs_ready(self.x,request,watch=self.x.continuous)
    def test_forged_command_refuses(self):
        self.stopped();request=self.request();request['context']['command'].append('--caller-grant')
        with self.assertRaisesRegex(N.Held,'action-command'):N.nfs_ready(self.x,request,watch=self.x.continuous)
    def test_no_ready_replay(self):
        self.stopped();request=self.request();N.nfs_ready(self.x,request,watch=self.x.continuous)
        with self.assertRaisesRegex(N.Held,'owning-phase'):N.nfs_ready(self.x,request,watch=self.x.continuous)

    def test_wrong_thread_cannot_consume_canary(self):
        self.active();failures=[]
        def attempt():
            try:N.stop_owned(self.x)
            except (N.Held,P.Held,A.Held) as exc:failures.append(str(exc))
        worker=threading.Thread(target=attempt);worker.start();worker.join()
        self.assertEqual(len(failures),1);self.assertEqual(self.stops,[])
    def test_health_log_only_changes_preserve_incarnation(self):
        self.active()
        for row in self.rows:row['State']['Health']=dict(Log=[dict(Output='fixture-only')],FailingStreak=9)
        N.stop_owned(self.x);N.nfs_ready(self.x,self.request(),watch=self.x.continuous)
        self.assertEqual(len(self.stops),1)
    def test_last_deadline_callback_source_mode_refuses_before_stop(self):
        self.active();original=P.time.monotonic;fired=[]
        def changed():
            owner=self.x;value=original()
            if N._REG.get(owner,{}).get('phase')=='stop-uncertain' and not fired:
                Path(owner.source_ref['path']).chmod(0o640);fired.append(True)
            return value
        with patch.object(P.time,'monotonic',changed),self.assertRaises((N.Held,P.Held,A.Held)):
            N.stop_owned(self.x)
        self.assertEqual(fired,[True]);self.assertEqual(self.stops,[])
        Path(P.__file__).chmod(0o600)
    def test_final_ready_callback_cannot_refresh_emitted_original(self):
        self.stopped();request=self.request();original=P.time.monotonic;fired=[]
        def changed():
            owner=self.x;value=original()
            if N._REG.get(owner,{}).get('phase')=='consumed' and not fired:
                (owner.op/'nfs-ready.json').chmod(0o640);fired.append(True)
            return value
        with patch.object(P.time,'monotonic',changed),self.assertRaises((N.Held,P.Held,A.Held)):
            N.nfs_ready(self.x,request,watch=self.x.continuous)
        self.assertEqual(fired,[True])
    def test_final_ready_callback_cleanup_reappearance_holds(self):
        self.stopped();request=self.request();original=P.time.monotonic;fired=[]
        def changed():
            owner=self.x;value=original()
            if N._REG.get(owner,{}).get('phase')=='consumed' and not fired:
                Path(self.canary.absent[-1]).mkdir();fired.append(True)
            return value
        with patch.object(P.time,'monotonic',changed),self.assertRaises((N.Held,P.Held,A.Held)):
            N.nfs_ready(self.x,request,watch=self.x.continuous)
        self.assertEqual(fired,[True])

if __name__=='__main__':unittest.main()

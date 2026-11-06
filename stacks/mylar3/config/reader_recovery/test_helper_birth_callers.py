"""Real constructors and binders over declared Docker transport/UID projections."""
import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent))
import comic_retained_pack_parent as pack
import comic_retained_standalone_parent as standalone

HERE=Path(__file__).parent
FIXES=HERE.parent
REAL_POPEN=subprocess.Popen


def load_host(name):
    spec=importlib.util.spec_from_file_location('birth_'+name,FIXES/'standalone_launch_host'/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


class Engine:
    """Metadata transport only; never invokes Docker or application code."""
    def __init__(self,case,root):
        self.case=copy.deepcopy(case);self.calls=[];self.processes=[];self.phase='created'
        self.ids={'native':'7'*64,'reader':'8'*64,'worker':'9'*64}
        self.mounts=[dict(Type='bind',Source=str(root),Destination='/state',RW=True,Propagation='rprivate')]
        self.rows={}
        for role,cid in self.ids.items():
            row=copy.deepcopy(case['running'] if role!='worker'else case['created'])
            row.update(Id=cid,Name='/'+role);row['Config']['Hostname']=cid[:12];row['Mounts']=self.mounts
            if role=='worker':row['Config']['Env']=list(reversed(row['Config']['Env']))
            self.rows[cid]=row
        self.cid=case['cid'];self.networks=self.case['networks'];self.anchors=[];self.change=None

    def helper(self,phase):
        row=copy.deepcopy(self.case[phase]);row['Mounts']=copy.deepcopy(self.mounts+self.anchors)
        if phase=='running'and self.processes:row['State']['Pid']=self.processes[-1].pid
        if self.change:self.change(row,phase)
        return row

    def command(self,runtime,args):
        self.calls.append(list(args))
        if args[0]=='inspect':
            row=self.helper(self.phase)if args[1]==self.cid else self.rows[args[1]]
            return json.dumps([copy.deepcopy(row)]).encode()
        if args[:2]==['network','inspect']:
            row=copy.deepcopy(self.networks[args[-1]]);row['Containers']={};row['Status']={'IPAM':{'usage':len(self.calls)}}
            return json.dumps([row]).encode()
        if args[0]=='events':return b''
        if args[0]=='create':
            # Actual argument building remains under test, including primary order.
            self.create=args;self.phase='created'
            image=args.index(self.case['created']['Image']);cmd=args[image+1:]
            for row in (self.case[phase]for phase in('created','running','exited')):
                row['Config']['Entrypoint']=['python3'];row['Config']['Cmd']=list(cmd);row['Args']=list(cmd)
            return(self.cid+'\n').encode()
        if args[:2]==['network','connect']:return b''
        raise AssertionError('Undeclared Docker command: '+str(args[:2]))

    def attach(self,*args,**kwargs):
        process=REAL_POPEN([sys.executable,'-I','-B','-c',"import sys; print('READY',flush=True); sys.stdin.buffer.readline()"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.processes.append(process);self.phase='running';return process

    def finish(self):
        for process in self.processes:
            if process.poll()is None:
                process.stdin.write(b'FINISH\n');process.stdin.flush();process.stdin.close();process.wait(timeout=5)
            for stream in (process.stdin,process.stdout,process.stderr):
                if not stream.closed:stream.close()
        self.phase='exited'


class Callers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases=json.loads((HERE/'helper_profile_vectors.json').read_bytes())['cases']
        cls.host=load_host('comic_retained_standalone_parent')
        cls.broker=load_host('comic_retained_standalone_broker')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.input=self.root/'input.json';self.input.write_bytes(b'{}');self.input.chmod(0o600)
        self.bootstrap=self.root/'bootstrap.py';self.bootstrap.write_bytes(b'# public fixture');self.bootstrap.chmod(0o600)

    def reference(self,module,path):
        return dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=list(module.nine(path.stat())))

    def setup_runtime(self,module,kind,anchors=False):
        engine=Engine(self.cases[kind],self.root);self.addCleanup(engine.finish)
        if anchors:
            engine.anchors=[dict(Type='bind',Source='/etc/mylar-publication-launch/child/'+n,Destination='/opt/mylar-publication-launch/'+n,RW=False,Propagation='rprivate')for n in module.ANCHOR_NAMES]
        transport=patch.object(module.ConfiguredRuntime,'command',lambda runtime,args:engine.command(runtime,args));transport.start();self.addCleanup(transport.stop)
        uid=patch.object(os,'geteuid',return_value=0);uid.start();self.addCleanup(uid.stop)
        runtime=module.ConfiguredRuntime.observe(engine.ids,installed_anchors=anchors)if module is pack or module is self.host else module.ConfiguredRuntime.observe(engine.ids)
        return engine,runtime

    def direct(self,module,kind):
        engine,runtime=self.setup_runtime(module,kind)
        # Standalone launch follows its existing quiesced owner; this projection
        # tests helper construction, not pause/backup or operational authority.
        if module is not pack:
            close=patch.object(module.ConfiguredRuntime,'close',lambda self:None);close.start();self.addCleanup(close.stop)
            pin=patch.object(module,'BOOTSTRAP_SOURCE_SHA256',hashlib.sha256(self.bootstrap.read_bytes()).hexdigest());pin.start();self.addCleanup(pin.stop)
        with patch.object(subprocess,'Popen',side_effect=engine.attach):
            if module is pack:
                runtime.launch(str(self.input),'/state/input.json',hashlib.sha256(b'{}').hexdigest());runtime.bind_running()
            else:runtime.launch(self.reference(module,self.bootstrap),self.reference(module,self.input),'/state/input.json')
        return engine,runtime

    def test_direct_pack_composes_real_profile_and_binder(self):
        engine,runtime=self.direct(pack,'configured')
        self.assertEqual(engine.create[engine.create.index('--network')+1],'public-primary')
        self.assertEqual(runtime.selected_pid,engine.processes[-1].pid)
        with self.assertRaisesRegex(ValueError,'bind-once'):runtime.bind_running()
        pack._helper_records().check(runtime,engine.helper('running'))
        engine.finish();terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
        pack._helper_records().check(runtime,engine.helper('exited'),terminal)

    def test_direct_standalone_composes_real_profile_and_binder(self):
        for module in (standalone,self.host):
            with self.subTest(module=module.__name__):
                engine,runtime=self.direct(module,'none')
                self.assertEqual(runtime.selected_pid,engine.processes[-1].pid)
                module._helper_records().check(runtime,engine.helper('running'))
                engine.finish();terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
                module._helper_records().check(runtime,engine.helper('exited'),terminal)

    def test_broker_constructor_composes_real_profiles_and_binders(self):
        source=ast.parse((FIXES/'standalone_launch_host/comic_retained_standalone_broker.py').read_bytes())
        method=next(n for n in source.body if isinstance(n,ast.FunctionDef)and n.name=='_launch_bound')
        first=next(i for i,n in enumerate(method.body)if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='networks'for t in n.targets))
        last=next(i for i,n in enumerate(method.body)if isinstance(n,ast.Expr)and isinstance(n.value,ast.Call)and isinstance(n.value.func,ast.Attribute)and n.value.func.attr=='bind_running')
        code=compile(ast.Module(body=method.body[first:last+1],type_ignores=[]),'<actual-broker-constructor>','exec')
        for module,kind in ((pack,'configured'),(self.host,'none')):
            with self.subTest(kind=kind):
                engine,runtime=self.setup_runtime(module,kind,anchors=True)
                if module is self.host:
                    closer=patch.object(module.ConfiguredRuntime,'close',lambda self:None);closer.start();self.addCleanup(closer.stop)
                scope=dict(Path=Path,os=os,time=__import__('time'),subprocess=subprocess,select=__import__('select'),
                    runtime=runtime,parent=module,pack=module is pack,selected=runtime.baseline['worker'if module is pack else'native'],
                    name=engine.case['created']['Name'][1:],Held=self.broker.Held,hexadecimal=self.broker.hexadecimal,
                    ANCHOR_NAMES=self.broker.ANCHOR_NAMES,CHILD_ANCHORS=Path('/etc/mylar-publication-launch/child'),
                    bootstrap=self.bootstrap.read_bytes(),input_child='/state/input.json',input_ref=self.reference(module,self.input),
                    bootframe=((),(),()),inputframe=((),(),()),row=dict(frame=((),(),()),deadline=runtime.deadline),
                    installation=SimpleNamespace(close=lambda:None),nine=self.broker.nine,five=self.broker.five)
                with patch.object(subprocess,'Popen',side_effect=engine.attach):exec(code,scope)
                module._helper_records().check(runtime,engine.helper('running'))
                engine.finish();terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
                module._helper_records().check(runtime,engine.helper('exited'),terminal)

    def test_pending_record_replacement_holds_without_retry(self):
        engine,runtime=self.setup_runtime(pack,'configured')
        with patch.object(subprocess,'Popen',side_effect=engine.attach):
            runtime.launch(str(self.input),'/state/input.json',hashlib.sha256(b'{}').hexdigest())
        def replace(row,phase):
            if phase=='running':pack._helper_records().records[runtime]=('foreign',)
        engine.change=replace
        with self.assertRaisesRegex(ValueError,'original-pending'):runtime.bind_running()
        self.assertFalse(hasattr(runtime,'selected_started'))
        with self.assertRaisesRegex(ValueError,'bind-once'):runtime.bind_running()

    def test_network_configuration_drift_refuses_before_create(self):
        engine,runtime=self.setup_runtime(pack,'configured')
        engine.networks['public-primary']['Options']={'foreign':'true'}
        with self.assertRaisesRegex(ValueError,'network-originals-drift'):
            runtime.launch(str(self.input),'/state/input.json',hashlib.sha256(b'{}').hexdigest())
        self.assertFalse(any(args[0]=='create'for args in engine.calls))

    def test_terminal_snapshot_is_not_rebased(self):
        engine,runtime=self.direct(pack,'configured');engine.finish()
        terminal=(runtime.selected,runtime.selected_started,runtime.selected_static,runtime.process)
        records=pack._helper_records();row=engine.helper('exited');records.check(runtime,row,terminal)
        original=records.records[runtime]
        row['NetworkSettings']['Networks']['public-primary']['DNSNames']=['foreign']
        with self.assertRaisesRegex(ValueError,'exited-profile-drift'):records.check(runtime,row,terminal)
        self.assertIs(records.records[runtime],original)

    def test_post_bind_profile_drift_refuses(self):
        engine,runtime=self.direct(pack,'configured');row=engine.helper('running');row['HostConfig']['Privileged']=True
        with self.assertRaisesRegex(ValueError,'profile-drift'):pack._helper_records().check(runtime,row)

    def unbound(self,module,kind):
        engine,runtime=self.setup_runtime(module,kind)
        runtime.remember_selected_created(engine.helper('created'))
        runtime.process=engine.attach()
        return engine,runtime

    def test_foreign_checker_is_never_dispatched_after_inspect(self):
        for module,kind in ((pack,'configured'),(standalone,'none'),(self.host,'none')):
            with self.subTest(module=module.__name__):
                engine,runtime=self.unbound(module,kind);original=runtime.inspect;called=[]
                getter=module._helper_records
                def inspect(cid):
                    row=original(cid)
                    module._helper_records=lambda:called.append('foreign')
                    return row
                try:
                    with patch.object(runtime,'inspect',side_effect=inspect),self.assertRaisesRegex(ValueError,'original-checker'):
                        runtime.bind_running()
                finally:module._helper_records=getter
                self.assertEqual(called,[])
                with self.assertRaisesRegex(ValueError,'bind-once'):runtime.bind_running()

    def test_running_state_cannot_change_during_profile_callbacks(self):
        for module,kind in ((pack,'configured'),(standalone,'none'),(self.host,'none')):
            with self.subTest(module=module.__name__):
                engine,runtime=self.unbound(module,kind);original=runtime.static
                def static(row):
                    value=original(row)
                    if row['Id']==engine.cid:row['State']['Pid']+=1
                    return value
                with patch.object(runtime,'static',side_effect=static),self.assertRaisesRegex(ValueError,'bind-callback-drift'):
                    runtime.bind_running()
                self.assertFalse(hasattr(runtime,'selected_started'))

    def test_created_mutation_keeps_create_ack_without_start(self):
        engine,runtime=self.setup_runtime(pack,'configured');original=runtime.selected_profile
        def profile(row):
            original(row);row['State']['Pid']=123
        with patch.object(runtime,'selected_profile',side_effect=profile),self.assertRaisesRegex(ValueError,'create-ack-held:'+engine.cid) as held:
            runtime.launch(str(self.input),'/state/input.json',hashlib.sha256(b'{}').hexdigest())
        self.assertIn('created-callback-drift',str(held.exception.__cause__))
        self.assertEqual(engine.processes,[])
        self.assertIsNone(runtime.selected)

    def test_foreign_guard_factory_is_never_dispatched(self):
        for module,kind in ((pack,'configured'),(standalone,'none'),(self.host,'none')):
            with self.subTest(module=module.__name__):
                engine,runtime=self.unbound(module,kind);original=runtime.inspect;called=[]
                factory=module._helper_guard
                def inspect(cid):
                    row=original(cid);module._helper_guard=lambda:called.append('foreign');return row
                try:
                    with patch.object(runtime,'inspect',side_effect=inspect),self.assertRaisesRegex(ValueError,'original-checker'):
                        runtime.bind_running()
                finally:module._helper_guard=factory
                self.assertEqual(called,[])

    def test_commit_poll_cannot_change_validated_epoch(self):
        for module,kind in ((pack,'configured'),(standalone,'none'),(self.host,'none')):
            with self.subTest(module=module.__name__):
                engine,runtime=self.unbound(module,kind);original=runtime.process.poll;captured=[];calls=[]
                inspect=runtime.inspect
                def observe(cid):
                    row=inspect(cid);captured.append(row);return row
                def poll():
                    calls.append(None)
                    if len(calls)==3:captured[-1]['State']['Pid']+=1
                    return original()
                with patch.object(runtime,'inspect',side_effect=observe),patch.object(runtime.process,'poll',side_effect=poll):
                    with self.assertRaisesRegex(ValueError,'running-snapshot-drift'):runtime.bind_running()
                self.assertFalse(hasattr(runtime,'selected_started'))

    def test_last_poll_never_dispatches_replaced_primitive(self):
        for module,kind in ((pack,'configured'),(standalone,'none'),(self.host,'none')):
            for name in ('helper_snapshot','_pipe'):
                with self.subTest(module=module.__name__,name=name):
                    engine,runtime=self.unbound(module,kind);original=runtime.process.poll;calls=[];foreign=[]
                    owner=module.helper_profiles if name=='helper_snapshot'else module.helper_profiles.HelperBirths
                    saved=vars(owner)[name]
                    def poll():
                        calls.append(None)
                        if len(calls)==3:setattr(owner,name,lambda *args:foreign.append('foreign'))
                        return original()
                    try:
                        with patch.object(runtime.process,'poll',side_effect=poll),self.assertRaisesRegex(ValueError,'helper-source-'):
                            runtime.bind_running()
                    finally:setattr(owner,name,saved)
                    self.assertEqual(foreign,[])
                    self.assertFalse(hasattr(runtime,'selected_started'))


if __name__=='__main__':unittest.main()

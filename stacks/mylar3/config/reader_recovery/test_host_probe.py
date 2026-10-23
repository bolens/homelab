"""Finite projected engine tests; not Docker, Parent, or NFS acceptance."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from comic_nfs_host_probe import Held, ProbeProcess


class ProbeBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.control = Path(self.temp.name) / 'original'
        self.control.write_bytes(b'original source')
        self.original = self.control.stat()
        self.calls = []
        self.image = 'sha256:' + 'a' * 64
        self.cid = 'b' * 64
        self.spec = dict(image=self.image, probe='/child/probe.py', kernel='/child/kernel.py',
                         input='/child/output/probe-input.json', input_sha256='c' * 64, probe_sha256='d' * 64,
                         mounts=[['/host/fixture', '/child/fixture', True], ['/host/fixture', '/config', False],
                                 ['/host/output', '/child/output', True], ['/host/probe.py', '/child/probe.py', False],
                                 ['/host/kernel.py', '/child/kernel.py', False],
                                 ['/host/input.json', '/child/output/probe-input.json', False],
                                 ['/host/protected', '/child/protected', False]])
        self.process = ProbeProcess(self.spec, ['docker'], self.engine, self.close)
        self.row = None
        self.foreign = False
        self.fail_create = False

    def close(self):
        current = self.control.stat()
        if current.st_mode != self.original.st_mode or self.control.read_bytes() != b'original source':
            raise Held('test-original-source-drift')

    def profile(self):
        cmd = self.process.command()
        return dict(Id=self.cid, Image=self.image,
                    Config=dict(User='1000:1000', Labels={'com.homelab.nfs.probe': self.process.name,
                                                        'org.opencontainers.image.source': 'public-source'},
                                Entrypoint=['/lsiopy/bin/python3'], Cmd=cmd[cmd.index(self.image) + 1:]),
                    HostConfig=dict(ReadonlyRootfs=True, Privileged=False, NetworkMode='none', PidMode='',
                                    CapAdd=None, CapDrop=['ALL'], SecurityOpt=['no-new-privileges'], PidsLimit=64,
                                    Binds=None, Tmpfs=None, Devices=None),
                    Mounts=[dict(Type='bind', Source=src, Destination=dst, RW=rw) for src, dst, rw in self.spec['mounts']],
                    State=dict(Status='created', Running=False, Pid=0, Paused=False, Restarting=False, Dead=False, OOMKilled=False))

    def engine(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        verb = argv[1]
        if verb == 'create':
            if self.fail_create:
                raise TimeoutError('projected lost creation ACK')
            self.row = self.profile()
            return subprocess.CompletedProcess(argv, 0, (self.cid + '\n').encode(), b'')
        if verb == 'inspect':
            row = copy.deepcopy(self.row)
            if self.foreign:
                row['Id'] = 'f' * 64
            return subprocess.CompletedProcess(argv, 0, json.dumps([row]).encode(), b'')
        self.assertEqual(argv, ['docker', 'start', '-a', self.cid])
        self.row['State'].update(Status='exited', ExitCode=0)
        return subprocess.CompletedProcess(argv, 0, b'actual projected child ACK', b'')

    def test_exact_owned_birth_start_terminal_and_inherited_label(self):
        prepared=self.process.prepare()
        self.assertEqual(self.calls, [])
        self.assertEqual(prepared['argv'],self.process.command())
        result = self.process.create()
        self.assertEqual({k:result[k] for k in ('name','argv','mounts')},prepared)
        self.assertEqual(result['id'], self.cid)
        self.assertEqual(self.process.start()['stdout'], b'actual projected child ACK')
        self.assertTrue(self.process.terminal)
        self.assertEqual([c[0][1] for c in self.calls], ['create', 'inspect', 'inspect', 'start', 'inspect'])

    def test_foreign_CID_refuses_before_start(self):
        self.process.create()
        self.foreign = True
        with self.assertRaisesRegex(Held, 'original-CID'):
            self.process.start()
        self.assertFalse(any(c[0][1] == 'start' for c in self.calls))

    def test_foreign_image_security_mount_command_refuse_before_start(self):
        self.process.create()
        original = copy.deepcopy(self.row)
        mutations = [('Image', 'sha256:' + 'f' * 64), ('Config', dict(self.row['Config'], Cmd=['foreign.py'])),
                     ('HostConfig', dict(self.row['HostConfig'], Privileged=True)), ('Mounts', [])]
        for key, value in mutations:
            self.row = copy.deepcopy(original)
            self.row[key] = value
            with self.assertRaises(Held):
                self.process.start()
        self.assertFalse(any(c[0][1] == 'start' for c in self.calls))

    def test_lost_birth_ack_never_replays(self):
        self.fail_create = True
        with self.assertRaises(TimeoutError):
            self.process.create()
        with self.assertRaisesRegex(Held, 'no-replay'):
            self.process.create()
        self.assertEqual(len(self.calls), 1)

    def test_prepare_exact_intent_is_retained_before_create_callback(self):
        prepared=self.process.prepare()
        intent=Path(self.temp.name)/'create-intent.json'
        intent.write_text(json.dumps(dict(argv=prepared['argv'])))
        original_engine=self.process.execute
        observed=[]
        def checked_engine(argv,**kwargs):
            if argv[1]=='create':
                observed.append(json.loads(intent.read_text())['argv']==argv)
                self.assertEqual(json.loads(intent.read_text())['argv'],argv)
            return original_engine(argv,**kwargs)
        self.process.execute=checked_engine
        self.process.create()
        self.assertEqual(observed,[True])

    def test_repeated_start_never_invokes_engine(self):
        self.process.create()
        self.process.start()
        count = len(self.calls)
        with self.assertRaisesRegex(Held, 'no-replay'):
            self.process.start()
        self.assertEqual(len(self.calls), count)

    def test_original_real_file_drift_before_create_refuses(self):
        self.control.write_bytes(b'changed retained source')
        with self.assertRaisesRegex(Held, 'original-source-drift'):
            self.process.create()
        self.assertEqual(self.calls, [])

    def test_spec_mutation_refuses_before_engine(self):
        self.process.spec['image'] = 'sha256:' + 'f' * 64
        with self.assertRaisesRegex(Held, 'original-spec'):
            self.process.create()
        self.assertEqual(self.calls, [])

    def test_created_CID_mutation_refuses_before_engine(self):
        self.process.create()
        self.process.cid = 'f' * 64
        count = len(self.calls)
        with self.assertRaisesRegex(Held, 'original-born-CID'):
            self.process.start()
        self.assertEqual(len(self.calls), count)

    def test_terminal_static_drift_refuses(self):
        self.process.create()
        original_engine = self.process.execute
        def changed(argv, **kwargs):
            value = original_engine(argv, **kwargs)
            if argv[1] == 'start':
                self.row['Config']['Labels']['foreign-new-label'] = 'drift'
            return value
        self.process.execute = changed
        with self.assertRaisesRegex(Held, 'terminal-static'):
            self.process.start()
        self.assertFalse(self.process.terminal)

    def test_profile_does_not_repeat_full_guards_for_command_construction(self):
        self.process.cid = self.process.cid_original = self.cid
        row = self.profile()
        checks = []
        original = self.process.close
        def counted():
            checks.append(True)
            original()
        self.process.close = counted
        self.process.profile(row)
        self.assertEqual(len(checks), 2)
        self.assertEqual(self.calls, [])

    def test_late_profile_callback_source_drift_refuses_acceptance(self):
        self.process.cid = self.process.cid_original = self.cid
        row = self.profile()
        owner=self
        class Labels(dict):
            def get(self,*args):
                owner.control.write_bytes(b'changed during profile comparison')
                return super().get(*args)
        row['Config']['Labels']=Labels(row['Config']['Labels'])
        with self.assertRaisesRegex(Held, 'original-source-drift'):
            self.process.profile(row)
        self.assertEqual(self.calls, [])

    def test_original_builder_instance_class_and_code_are_required(self):
        from unittest.mock import patch
        self.process.cid = self.process.cid_original = self.cid
        row = self.profile()
        def foreign(self):
            raise AssertionError('foreign builder must not execute')
        for target in (self.process,ProbeProcess):
            with self.subTest(target=type(target).__name__),patch.object(target,'_command',foreign):
                with self.assertRaisesRegex(Held,'original-command-builder'):
                    self.process.profile(row)
        builder=ProbeProcess._command;code=builder.__code__
        try:
            builder.__code__=foreign.__code__
            with self.assertRaisesRegex(Held,'original-command-builder'):
                self.process.profile(row)
        finally:builder.__code__=code
        self.assertEqual(self.calls,[])

    def test_builder_replaced_by_profile_callback_refuses(self):
        self.process.cid = self.process.cid_original = self.cid
        row = self.profile();original=ProbeProcess._command
        class Labels(dict):
            def get(self,*args):
                ProbeProcess._command=lambda self:[]
                return super().get(*args)
        row['Config']['Labels']=Labels(row['Config']['Labels'])
        try:
            with self.assertRaisesRegex(Held,'original-command-builder'):
                self.process.profile(row)
        finally:ProbeProcess._command=original
        self.assertEqual(self.calls,[])


class FullProfileTransitions(unittest.TestCase):
    def fixture(self):
        import comic_reader_lifecycle_parent as p
        import comic_nfs_host_probe as h
        original=ProbeBoundary();original.setUp();self.addCleanup(original.doCleanups)
        owner=object.__new__(p.LifecycleParent);owner.core=b'component-owning-parent';owner.engine=object.__new__(p.ScopedDocker);p._CORES[owner]=owner.core;self.addCleanup(p._CORES.pop,owner,None)
        process=h.ProbeProcess(original.spec,['docker'],owner.engine.canary,original.close,owner=owner);original.process=process;process.cid=process.cid_original=original.cid
        row=original.profile();row.update(Name='/'+process.name,Path='/lsiopy/bin/python3',Args=row['Config']['Cmd'],NetworkSettings=dict(Ports={},SandboxID='',SandboxKey='',Networks={'none':dict(EndpointID='',NetworkID='',IPAddress='',Gateway='',MacAddress='')}));row['HostConfig']['OomKillDisable']=False
        running=copy.deepcopy(row);running['State'].update(Status='running',Running=True,Pid=123,StartedAt='fixed-epoch');running['HostConfig']['OomKillDisable']=None;running['NetworkSettings'].update(SandboxID='e'*64,SandboxKey='/var/run/docker/netns/'+'e'*12);running['NetworkSettings']['Networks']['none'].update(EndpointID='c'*64,NetworkID='d'*64)
        terminal=copy.deepcopy(running);terminal['State'].update(Status='exited',Running=False,Pid=0,ExitCode=0);terminal['NetworkSettings'].update(SandboxID='',SandboxKey='');terminal['NetworkSettings']['Networks']['none']['EndpointID']=''
        return p,h,process,row,running,terminal
    def test_full_start_and_teardown_once_exact_retained_baselines(self):
        p,h,process,created,running,terminal=self.fixture()
        # The unchanged legacy contract still rejects this exact HostConfig change.
        original_parent=h._PARENT_PROFILES.pop(process);process.static=h.encode({k:created[k]for k in ('Config','HostConfig','Mounts')})
        try:
            with self.assertRaisesRegex(h.Held,'probe-original-terminal-static'):process.profile(running,running=True)
        finally:h._PARENT_PROFILES[process]=original_parent;process.static=None
        process.profile(created);born=process.full_created
        with self.assertRaises(h.Held):
            bad=copy.deepcopy(running);bad['Config']['foreign']='refuse';process.profile(bad,running=True)
        self.assertIsNone(process.full_running);process.profile(running,running=True);started=process.full_running
        self.assertEqual(born,h.encode(p.static(created)));self.assertEqual(started,h.encode(p.static(running)));process.profile(terminal,terminal=True)
        self.assertEqual(process.full_created,born);self.assertEqual(process.full_running,started);process.profile(terminal,terminal=True)
        bad=copy.deepcopy(terminal);bad['NetworkSettings']['Networks']['none']['NetworkID']='f'*64
        with self.assertRaises(h.Held):process.profile(bad,terminal=True)
    def test_running_refresh_types_and_forged_tape_refuse(self):
        p,h,process,created,running,terminal=self.fixture();process.profile(created);process.profile(running,running=True)
        bad=copy.deepcopy(running);bad['HostConfig']['OomKillDisable']=False
        with self.assertRaises(h.Held):process.profile(bad,running=True)
        process.full_running=h.encode(p.static(bad))
        with self.assertRaisesRegex(h.Held,'full-profile-seal'):process.original_close()
    def test_active_parent_owned_terminal_delegation_keeps_other_guards(self):
        import ast
        source=Path(__file__).with_name('comic_negative_nfs_active_parent.py').read_text();tree=ast.parse(source)
        checks=[n for n in ast.walk(tree)if isinstance(n,ast.Call)and isinstance(n.func,ast.Name)and n.func.id=='check'and len(n.args)>1 and isinstance(n.args[1],ast.Constant)and n.args[1].value=='child-terminal']
        self.assertEqual(len(checks),2)
        p,h,process,created,running,terminal=self.fixture();process.profile(created);process.profile(running,running=True);process.profile(terminal,terminal=True)
        for check in checks:
            env=dict(terminal=terminal,initial_child_static={k:created[k]for k in ('Config','HostConfig','Mounts')},owned_probe=process,child=process.cid,IMAGE=process.spec['image'])
            self.assertTrue(eval(compile(ast.Expression(check.args[0]),'<owning-terminal-predicate>','eval'),env))
            env['owned_probe']=None;self.assertFalse(eval(compile(ast.Expression(check.args[0]),'<owning-terminal-predicate>','eval'),env))
            env['owned_probe']=process;env['terminal']=copy.deepcopy(terminal);env['terminal']['Config']['foreign']='refuse';self.assertFalse(eval(compile(ast.Expression(check.args[0]),'<owning-terminal-predicate>','eval'),env))

    def test_source_authenticated_parent_required_no_generic_helper_callback(self):
        import comic_nfs_host_probe as h
        original=ProbeBoundary();original.setUp();self.addCleanup(original.doCleanups)
        with self.assertRaises((h.Held,AttributeError)):h.ProbeProcess(original.spec,['docker'],original.engine,original.close,owner=object())

class RetainedProfileContract(unittest.TestCase):
    def fixture(self):
        source=FullProfileTransitions();source._cleanups=[]
        self.addCleanup(source.doCleanups)
        p,h,obj,born,running,terminal=source.fixture()
        obj.profile(born)
        return p,obj,lambda:obj.profile(running,running=True),obj.original_close
    def test_same_globals_predicate_encoder_and_prefix_replacement_refuse(self):
        from unittest.mock import patch
        p,obj,run,close=self.fixture()
        scope=p.__dict__;temporary={}
        exec('def foreign(*args): return True',scope,temporary)
        for name,value in [('none_network_started_static',temporary['foreign']),
                           ('none_network_exited_static',temporary['foreign']),
                           ('_none_network_profile_bytes',temporary['foreign']),
                           ('NONE_NETWORK_SANDBOX_PARENT','/foreign')]:
            with self.subTest(name=name),patch.dict(scope,{name:value}):
                with self.assertRaisesRegex(p.Held,'original-profile-contract'):run()
                with self.assertRaisesRegex(p.Held,'original-profile-contract'):close()
        self.assertIsNone(obj.full_running)
        run()
    def test_in_place_code_mutation_refuses_and_restoration_retains_tape(self):
        p,obj,run,close=self.fixture();function=p.none_network_started_static;original=function.__code__
        def foreign(a,b,c):return True
        try:
            function.__code__=foreign.__code__
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):run()
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):close()
        finally:function.__code__=original
        run();close()
    def test_retained_guard_identity_code_and_token_are_required(self):
        from unittest.mock import patch
        p,obj,run,close=self.fixture();scope=p.__dict__;temporary={}
        exec('def foreign(): return object()',scope,temporary)
        with patch.dict(scope,none_network_profile_contract=temporary['foreign']):
            with self.assertRaises(ValueError):run()
            with self.assertRaises(ValueError):close()
        run();close()
        with patch.dict(scope,NONE_NETWORK_SANDBOX_PARENT='/foreign'):
            with self.assertRaisesRegex(p.Held,'original-profile-contract'):self.fixture()
    def test_in_place_dependency_and_checked_api_code_refuse(self):
        p,obj,run,close=self.fixture()
        for name in ('_none_network_profile_bytes','checked_none_network_started_static',
                     'checked_none_network_exited_static','none_network_profile_contract'):
            function=getattr(p,name);code=function.__code__
            try:
                function.__code__=code.replace(co_filename='<changed-source-code>')
                with self.subTest(name=name),self.assertRaises(ValueError):run()
                with self.assertRaises(ValueError):close()
            finally:function.__code__=code
        run();close()

if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

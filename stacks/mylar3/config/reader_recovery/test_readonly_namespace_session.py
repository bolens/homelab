"""Real source loader/session/closure; Parent admission and kernel/Docker IO projected.

Each case has a fresh interpreter so the production loader admits its seven
original module names. No module/callable seal is disabled or replaced.
"""
import contextlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))


def exercise(case):
    import comic_reader_lifecycle_parent as P
    with tempfile.TemporaryDirectory() as temporary, contextlib.ExitStack() as stack:
        base = Path(temporary)
        refs, raws = {}, {}
        def reference(path, raw):
            path.write_bytes(raw); path.chmod(0o600)
            return dict(path=str(path), sha256=P.hashlib.sha256(raw).hexdigest(),
                        signature9=P.nine(path.stat()))
        names = ('comic_negative_nfs_active_lifecycle.py', 'comic_nfs_host_engine.py',
                 'comic_nfs_host_lease.py', 'comic_nfs_lease_session.py',
                 'comic_nfs_host_probe.py', 'comic_nfs_parent_session.py',
                 'comic_nfs_child_input_projection.py')
        for name in names:
            raws[name] = (Path(__file__).parent / name).read_bytes()
            refs[name] = reference(base / name, raws[name])
        # Constructor admission is projected explicitly; subsequent Parent.left,
        # source reads, callable seals, session constructor and closure are real.
        owner = object.__new__(P.LifecycleParent)
        owner.thread = threading.get_ident(); owner.deadline = time.monotonic() + 120
        owner.op = base; owner.plan = dict(nonce='synthetic', operation=str(base))
        owner.engine = object.__new__(P.ScopedDocker)
        owner.files = {}; owner.nodes = {}; owner.plan_ref = {}; owner.generated = {}
        source = Path(P.__file__).absolute()
        owner.source_ref = dict(path=str(source), sha256=P.hashlib.sha256(source.read_bytes()).hexdigest(),
                                signature9=P.nine(source.stat()))
        def seal_owner():
            owner.core = P.encode(dict(plan=owner.plan, files=owner.files, nodes=owner.nodes,
                source=owner.source_ref, input=owner.plan_ref, engine=id(owner.engine),
                thread=owner.thread, deadline=owner.deadline))
            P._CORES[owner] = owner.core; P._GENERATED[owner] = P.encode(owner.generated)
        seal_owner()
        P._NFS_SOURCE_CONTEXTS[owner] = (refs, raws, P.encode({}), P.encode({}), str(base))
        P._NFS_EFFECTIVE_ABSENCES[owner] = P.encode([])
        P._NFS_SOURCE_SEALS[owner] = P.encode(dict(refs=refs,
            raw_sha={n:P.hashlib.sha256(r).hexdigest() for n,r in raws.items()},
            active={}, probe={}, output=str(base), effective_absences=[]))
        modules = owner.nfs_host_modules()
        assert len(P._NFS_HOST_MODULE_SEALS[owner][1]) == 7
        assert all(row[3] for row in P._NFS_HOST_MODULE_SEALS[owner][1])
        S = modules['comic_nfs_parent_session.py']
        process = subprocess.Popen([sys.executable, '-I', '-B', '-u', '-c',
            "import sys;print('ready',flush=True);sys.stdin.read()"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        def cleanup():
            if process.poll() is None: process.kill()
            process.wait(timeout=5)
            for stream in (process.stdin, process.stdout, process.stderr): stream.close()
        stack.callback(cleanup)
        assert process.stdout.readline() == b'ready\n'
        cid = 'a' * 64
        profile = dict(Id=cid, Name='/synthetic', Image='sha256:'+'b'*64,
            Path='private-helper', Args=[], Config={}, HostConfig={'NetworkMode':'none'},
            Mounts=[], NetworkSettings={}, State=dict(Status='running', Running=True,
            Paused=False, Restarting=False, Dead=False, OOMKilled=False, Pid=process.pid,
            StartedAt='synthetic', FinishedAt='', ExitCode=0, Error=''))
        inspections = []
        def docker(args, deadline):
            assert args == ['inspect', cid]; inspections.append(True)
            if case == 'registry' and len(inspections) == 1:
                P._NFS_LIVE_SESSIONS = dict(P._NFS_LIVE_SESSIONS)
            return P.encode([profile])
        owner.engine.run = docker  # Docker transport only; inspect/profile guards real.
        engine = object.__new__(modules['comic_nfs_host_engine.py'].EngineReplies)
        engine.owner = owner; engine.cid = cid; engine.nonce = owner.plan['nonce']
        lease = object.__new__(modules['comic_nfs_lease_session.py'].HostLeaseReplies)
        lease.dialogue = engine; lease.lease = None; lease.done = False
        probe = object.__new__(modules['comic_nfs_host_probe.py'].HostProbeReplies)
        probe.dialogue = engine
        packet = reference(base/'packet', P.encode(dict(nonce='synthetic',
            kind='owning-nfs-retained-host-lease-child-v2')))
        owner.generated[packet['path']] = packet; seal_owner()
        streams = (process.stdin, process.stdout, process.stderr)
        descriptors = tuple((v.fileno(), S.five(os.fstat(v.fileno()))) for v in streams)
        deadline = min(owner.deadline, time.monotonic()+60)
        P.dialogue_register(owner.engine, cid, process, streams, descriptors, deadline, process.pid)
        session = S.RetainedChild(owner, cid, process, engine, lease, probe, packet,
                                  str(base), P.encode(P.static(profile)))
        ticks = int(Path('/proc/'+str(process.pid)+'/stat').read_text().rsplit(')',1)[1].split()[19])
        epoch = (session, cid, process.pid, P.encode(P.lifecycle_state(profile)), ticks,
                 P.encode(P.static(profile)))
        P._NFS_CHILD_EPOCHS[owner] = epoch; P._NFS_LIVE_SESSIONS[owner] = session
        protected = base/'protected'; protected.mkdir()
        roots = {str(protected):P.nine(protected.stat())}
        namespace = base/'namespace'; namespace.write_bytes(b'synthetic namespace')
        mountinfo = base/'mountinfo'
        initial = ('1 99 0:1 / / ro - overlay overlay rw\n'
            '2 1 0:2 / '+str(protected)+' ro master:7 - nfs4 server:/export/library rw,addr=192.0.2.1\n'
            '3 1 0:3 /private/tree /work rw - btrfs /dev/disk rw\n'
            '4 1 0:2 / /retention rw - nfs4 server:/export/retention rw,addr=192.0.2.1\n').encode()
        if case == 'writable': initial = initial.replace(b' ro master:7', b' rw master:7')
        if case == 'structure': initial += b'5 1 0:9 / /work rw - tmpfs tmpfs rw\n'
        mountinfo.write_bytes(initial)
        real_open, real_stat = os.open, os.stat
        opened, actions, node_calls = [], [], []
        proc = '/proc/'+str(process.pid)
        def mapped(path):
            return {proc+'/ns/mnt':str(namespace), proc+'/root':'/',
                    proc+'/mountinfo':str(mountinfo)}.get(str(path), path)
        def opened_path(path, flags, *args, **kwargs):
            if case == 'partial-open' and str(path) == proc+'/root':
                raise OSError('synthetic root-open failure')
            fd = real_open(mapped(path), flags, *args, **kwargs)
            if str(path) in (proc+'/ns/mnt', proc+'/root'): opened.append(fd)
            return fd
        def runner(argv, **kwargs):
            request = P.decode(argv[-1].encode())
            if 'namespace' not in request:
                node_calls.append(True)
                return subprocess.CompletedProcess(argv, 0, P.encode(dict(uid=[1000]*3,
                    gid=[1000]*3, groups=[], root5=request['root5'],
                    nodes={path:list(S.five(real_stat(path))) for path in request['paths']})), b'')
            actions.append(True)
            assert kwargs['pass_fds'] == (request['namespace'], request['root'])
            assert request['pid'] == process.pid and request['ticks'] == ticks
            after = initial.replace(b' master:7', b'')
            if case == 'topology': after = after.replace(b'0:2 /', b'0:8 /')
            mountinfo.write_bytes(after)
            if case == 'profile': profile['State']['StartedAt'] = 'replaced'
            return subprocess.CompletedProcess(argv, 0,
                b'' if case == 'lost-ack' else b'nfs-private-sealed\n', b'')
        stack.enter_context(patch.object(os, 'open', opened_path))
        stack.enter_context(patch.object(os, 'stat', lambda path,*a,**k:real_stat(mapped(path),*a,**k)))
        stack.enter_context(patch.object(os, 'getresuid', return_value=(0,0,0)))
        stack.enter_context(patch.object(os, 'getresgid', return_value=(0,0,0)))
        stack.enter_context(patch.object(subprocess, 'run', runner))
        # Mutations happen after the original constructor/loader admission.
        if case == 'epoch': P._NFS_CHILD_EPOCHS[owner] = tuple([*epoch[:4], ticks+1, epoch[5]])
        if case == 'dialogue': P._DIALOGUE_SEALS[owner.engine][cid] = tuple([*P._DIALOGUE_SEALS[owner.engine][cid][:6], deadline-1])
        if case == 'defaults': S.RetainedChild.close.__defaults__ = ()
        if case == 'code': S._propagation_geometry.__code__ = (lambda raw: ()).__code__
        if case == 'source': (base/names[0]).write_bytes(b'changed source')
        try:
            result = S.seal_readonly_namespace(session, roots, ['/work','/retention'], deadline)
        except (S.Held, P.Held, OSError):
            assert case != 'success', case
            assert len(actions) == (1 if case in ('lost-ack','topology','profile') else 0), (case,actions)
        else:
            assert case == 'success', (case,result)
            assert result['namespace_sealed'] is True and result['mutation_authority'] is False
            assert len(actions) == 1 and len(inspections) == 3 and len(node_calls) == 2
            session.close()
        for fd in opened:
            try: os.fstat(fd)
            except OSError: pass
            else: raise AssertionError('retained namespace descriptor leaked')


class OwningSession(unittest.TestCase):
    def run_case(self, case):
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).absolute()), '--case', case],
                                capture_output=True, timeout=30, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode())


for _case in ('success','registry','epoch','dialogue','defaults','code','source','writable',
              'structure','partial-open','lost-ack','topology','profile'):
    setattr(OwningSession, 'test_'+_case.replace('-','_'),
            lambda self, case=_case:self.run_case(case))

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--case': exercise(sys.argv[2])
    else: unittest.main()

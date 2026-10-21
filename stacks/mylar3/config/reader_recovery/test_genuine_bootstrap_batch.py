"""Disposable local pipes and modeled saved IDs; no Docker or factory proof.

The separately explicit Root identity-self-check exercises actual Linux IDs.
These unprivileged unit controls never invoke Polkit or the Docker daemon.
"""
import ast
import io
import json
import hashlib
import os
import signal
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import genuine_bootstrap_batch as b
import genuine_bootstrap_creator as c


class IDs:
    def __init__(self):
        self.uid = (0, 0, 0)
        self.gid = (0, 0, 0)
        self.groups = [0]
        self.events = []

    def resuid(self, real, effective, saved):
        self.uid = (real, effective, saved)
        self.events.append(('uid', self.uid))

    def resgid(self, real, effective, saved):
        self.gid = (real, effective, saved)
        self.events.append(('gid', self.gid))

    def euid(self, uid):
        self.uid = (self.uid[0], uid, self.uid[2])
        self.events.append(('euid', uid))

    def egid(self, gid):
        self.gid = (self.gid[0], gid, self.gid[2])
        self.events.append(('egid', gid))

    def setgroups(self, groups):
        self.groups = groups

    def patches(self):
        return patch.multiple(b.os, getresuid=lambda: self.uid, getresgid=lambda: self.gid,
                              getgroups=lambda: self.groups, setgroups=self.setgroups,
                              setresuid=self.resuid, setresgid=self.resgid,
                              seteuid=self.euid, setegid=self.egid)


class Transport:
    """Real Python pipe process doubles only the fixed Docker effect."""
    def __init__(self, program='import sys;sys.stdout.write("[]")'):
        self.program = program
        self.calls = []
        self.client = None
        self.terminated = []

    def check(self):
        return None

    def spawn_docker(self, args, data):
        self.calls.append((list(args), data))
        self.client = subprocess.Popen([sys.executable, '-I', '-B', '-c', self.program],
                                stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return self.client

    def terminate_client(self, process):
        if process is not self.client:
            raise ValueError('fixture-foreign-client')
        self.terminated.append(process)
        process.kill()


def owning(identity):
    driver = b.driver_type(c)(identity)
    owner = SimpleNamespace(document={'images': {'native': {'id': 'sha256:'+'a'*64}}},
                            metadata={'native': []}, check=lambda: None,
                            note=lambda *args: None, seconds=lambda: 2, journal=None, serial=0)
    owner.engine = c.PurposeEngine(owner, driver)
    driver.owner = owner
    return owner, driver


class BatchTests(unittest.TestCase):
    def test_real_uid1000_cannot_enter_root_session(self):
        # No mocking of this process's actual UID; Root may run the same suite.
        if os.geteuid() != 0:
            with self.assertRaisesRegex(ValueError, 'batch-original-root-required'):
                b.Identity()
        with patch.object(b.os, 'getresuid', return_value=(1000, 1000, 1000)):
            with self.assertRaisesRegex(ValueError, 'batch-original-root-required'):
                b.Identity()

    def test_exact_saved_ids_and_irreversible_final_drop(self):
        ids = IDs()
        with ids.patches():
            identity = b.Identity()
            identity.enter()
            self.assertEqual(ids.uid, (1000, 1000, 0))
            self.assertEqual(ids.gid, (1000, 1000, 0))
            self.assertEqual(ids.groups, [])
            with identity._root_window():
                self.assertEqual(ids.uid, (1000, 0, 0))
                self.assertEqual(ids.gid, (1000, 0, 0))
            identity.check()
            identity.close()
            self.assertEqual(ids.uid, (1000, 1000, 1000))
            self.assertEqual(ids.gid, (1000, 1000, 1000))
            identity.close()
            with self.assertRaisesRegex(ValueError, 'batch-uid1000-lifetime'):
                identity.check()

    def test_pending_finaldrop_signal_runs_only_after_saved_root_is_gone(self):
        ids = IDs()
        delivered = []
        previous_handler = signal.getsignal(signal.SIGUSR1)
        def handler(number, frame):
            delivered.append((ids.uid, ids.gid, list(ids.groups), identity.closed))
            raise KeyboardInterrupt()
        signal.signal(signal.SIGUSR1, handler)
        try:
            with ids.patches():
                identity = b.Identity()
                identity.enter()
                original = ids.euid
                def queue_when_elevated(uid):
                    original(uid)
                    if uid == 0:
                        os.kill(os.getpid(), signal.SIGUSR1)
                        self.assertEqual(delivered, [])
                with patch.object(b.os, 'seteuid', side_effect=queue_when_elevated):
                    with self.assertRaises(KeyboardInterrupt):
                        identity.close()
                self.assertTrue(identity.closed)
                self.assertEqual(delivered, [((1000, 1000, 1000), (1000, 1000, 1000), [], True)])
        finally:
            signal.signal(signal.SIGUSR1, previous_handler)

    def test_failed_credential_restoration_exits_without_unblocking(self):
        class FatalDrop(BaseException):
            pass
        for phase in ('window', 'final'):
            ids = IDs()
            masks = []
            def mask(operation, values):
                masks.append(operation)
                return set()
            with ids.patches(), patch.object(b.signal, 'pthread_sigmask', side_effect=mask), \
                 patch.object(b.os, '_exit', side_effect=FatalDrop) as exit_call:
                identity = b.Identity()
                identity.enter()
                if phase == 'window':
                    def fail_restore(gid):
                        if gid == 1000:
                            raise PermissionError('fixture-drop-failed')
                        ids.egid(gid)
                    with patch.object(b.os, 'setegid', side_effect=fail_restore):
                        with self.assertRaises(FatalDrop):
                            with identity._root_window():
                                pass
                else:
                    with patch.object(b.os, 'setresuid', side_effect=PermissionError('fixture-drop-failed')):
                        with self.assertRaises(FatalDrop):
                            identity.close()
                exit_call.assert_called_once_with(126)
                self.assertEqual(masks, [signal.SIG_BLOCK])
                self.assertFalse(identity.closed)

    def test_spawn_is_fixed_root_and_restores_before_wait(self):
        ids = IDs()
        def spawn(argv, **kwargs):
            self.assertEqual(ids.uid, (1000, 0, 0))
            self.assertEqual(ids.gid, (1000, 0, 0))
            self.assertEqual(argv, [*b.DOCKER, 'inspect', 'a'*64])
            self.assertEqual(kwargs['user'], 0)
            self.assertEqual(kwargs['group'], 0)
            self.assertEqual(kwargs['extra_groups'], [])
            self.assertEqual(kwargs['env'], {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
            self.assertTrue(kwargs['close_fds'])
            self.assertIs(kwargs['preexec_fn'], b._child_signal_mask)
            return SimpleNamespace(poll=lambda: 0)
        with ids.patches(), patch.object(b.subprocess, 'Popen', side_effect=spawn):
            identity = b.Identity()
            identity.enter()
            self.assertEqual(identity.spawn_docker(['inspect', 'a'*64], None).poll(), 0)
            identity.check()  # Waiting begins only after this restoration.
            identity.close()

    def test_spawn_error_and_keyboard_interrupt_restore_ids(self):
        for error in (OSError('fixture'), KeyboardInterrupt()):
            ids = IDs()
            with ids.patches(), patch.object(b.subprocess, 'Popen', side_effect=error):
                identity = b.Identity()
                identity.enter()
                with self.assertRaises(type(error)):
                    identity.spawn_docker(['inspect', 'a'*64], None)
                identity.check()
                identity.close()

    def test_threads_foreign_saved_id_or_groups_refuse(self):
        ids = IDs()
        with ids.patches(), patch.object(threading, 'active_count', return_value=2):
            with self.assertRaisesRegex(ValueError, 'batch-single-thread-required'):
                b.Identity()
        with ids.patches():
            identity = b.Identity()
            identity.enter()
            ids.groups = [0]
            with self.assertRaisesRegex(ValueError, 'batch-uid1000-lifetime'):
                identity.spawn_docker(['inspect', 'a'*64], None)
            ids.groups = []
            ids.uid = (1000, 1000, 1000)
            with self.assertRaisesRegex(ValueError, 'batch-uid1000-lifetime'):
                identity.check()

    def test_actual_owning_engine_and_real_bounded_pipe(self):
        transport = Transport()
        owner, driver = owning(transport)
        owner.engine.image('native')
        self.assertEqual(transport.calls, [(['image', 'inspect', 'sha256:'+'a'*64], None)])
        self.assertEqual(owner.engine.counts, {'image-native': 1})
        self.assertFalse(owner.engine.poisoned)
        with self.assertRaisesRegex(c.p.Held, 'creator-call-budget'):
            owner.engine.image('native')
        self.assertEqual(len(transport.calls), 1)

    def test_direct_driver_spawn_and_generic_call_are_not_a_relay(self):
        for action in ('spawn', 'docker', 'call'):
            transport = Transport()
            owner, driver = owning(transport)
            with self.assertRaisesRegex(ValueError, 'batch-owning-dispatch-required'):
                if action == 'spawn':
                    driver._spawn(['run', '--privileged', 'foreign'], None)
                elif action == 'docker':
                    driver.docker(['run', '--privileged', 'foreign'], 1)
                else:
                    owner.engine.call('invented', 1, ['run', '--privileged', 'foreign'])
            self.assertEqual(transport.calls, [])

    def test_foreign_owner_source_failure_never_spawns(self):
        transport = Transport()
        owner, driver = owning(transport)
        driver.owner = SimpleNamespace(engine=owner.engine)
        with self.assertRaisesRegex(ValueError, 'batch-owning-dispatch-required'):
            owner.engine.image('native')
        self.assertEqual(transport.calls, [])
        transport = Transport()
        owner, driver = owning(transport)
        def refuse():
            raise c.p.Held('fixture-original-source-changed')
        owner.check = refuse
        with self.assertRaisesRegex(c.p.Held, 'fixture-original-source-changed'):
            owner.engine.image('native')
        self.assertEqual(transport.calls, [])

    def test_lost_pipe_response_no_mutation_replay(self):
        class Lost(Transport):
            def spawn_docker(self, args, data):
                self.calls.append((list(args), data))
                raise OSError('fixture')
        transport = Lost()
        owner, _ = owning(transport)
        # Use the owning image method's readonly call: failure diagnostic remains
        # original Driver's fixed unknown result; there is no batch retry loop.
        with self.assertRaisesRegex(c.p.Held, 'creator-engine-outcome-unknown-no-replay') as caught:
            owner.engine.image('native')
        self.assertIsNone(caught.exception.creator_engine_failure['returncode'])
        self.assertEqual(len(transport.calls), 1)
        transport = Lost()
        owner, _ = owning(transport)
        owner.nonce = 'a'*64
        owner.labels = lambda: ['--label', 'fixture='+owner.nonce]
        owner.name = lambda role: 'fixture-'+role
        with self.assertRaisesRegex(c.p.Held, 'creator-engine-outcome-unknown-no-replay'):
            owner.engine.create_network()
        self.assertTrue(owner.engine.poisoned)
        with self.assertRaisesRegex(c.p.Held, 'creator-unknown-outcome-held'):
            owner.engine.create_network()
        self.assertEqual(len(transport.calls), 1)

    def test_genuine_creator_prepare_and_connected_dispatch_use_same_batch(self):
        from test_genuine_bootstrap_creator import CreatorTests
        fixture = CreatorTests(methodName='runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.searchable_request()
        owner, effects = fixture.creator()
        class FullTransport(Transport):
            def spawn_docker(self, args, data):
                self.calls.append((list(args), data))
                raw = effects.docker(args, seconds=30, data=data)
                # Actual bounded OS pipes; only Docker's effects and the NFS
                # observation are doubled, never owning admission methods.
                self.client = subprocess.Popen([sys.executable, '-I', '-B', '-c',
                    'import sys;sys.stdin.buffer.read();sys.stdout.buffer.write(bytes.fromhex(sys.argv[1]))', raw.hex()],
                    stdin=subprocess.PIPE if data is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return self.client
        transport = FullTransport()
        driver = b.driver_type(c)(transport)
        driver.owner = owner
        driver.mount = effects.mount
        owner.engine.driver = driver
        plan = owner.prepare()
        self.assertEqual(set(plan['roles']), {'native', 'reader', 'worker'})
        self.assertEqual(owner.engine.started, {'native', 'reader'})
        args, value = fixture.queue_call(owner)
        answer = c.p.decode(owner.engine.run(args, 30, c.p.encode(value)))
        self.assertTrue(answer['queue_empty_observed'])
        installed = ['exec', '--interactive', '--user', '1000:1000', owner.engine.ids['native'],
                     '/lsiopy/bin/python3', '-I', '-B', '-c', c.b.IMAGE_PROGRAM]
        self.assertEqual(c.p.decode(owner.engine.run(installed, 30, c.p.encode(sorted(owner.sdk)))), owner.sdk)
        count = len(transport.calls)
        with self.assertRaises(c.p.Held):
            owner.engine.start('worker')
        bad = list(installed)
        bad[-1] = 'print("foreign")'
        with self.assertRaises(c.p.Held):
            owner.engine.run(bad, 30, b'{}')
        self.assertEqual(len(transport.calls), count)
        self.assertFalse(any(args[0] in ('stop', 'rm') for args, _ in transport.calls))
        self.assertEqual(transport.terminated, [])

    def test_timeout_terminates_only_exact_owned_pipe_client(self):
        transport = Transport('import time;time.sleep(30)')
        owner, driver = owning(transport)
        owner.seconds = lambda: 1
        with self.assertRaisesRegex(c.p.Held, 'creator-engine-outcome-unknown-no-replay'):
            owner.engine.image('native')
        self.assertEqual(transport.terminated, [transport.client])
        self.assertIsNotNone(transport.client.poll())
        with self.assertRaisesRegex(ValueError, 'batch-owning-termination-required'):
            driver._kill_process(transport.client)
        self.assertEqual(len(transport.terminated), 1)

    def test_client_cleanup_secondary_preserves_original_unknown(self):
        class FailingCleanup(Transport):
            def terminate_client(self, process):
                super().terminate_client(process)
                raise ValueError('fixture-cleanup-secondary')
        transport = FailingCleanup('import time;time.sleep(30)')
        owner, _ = owning(transport)
        owner.seconds = lambda: 1
        with self.assertRaisesRegex(c.p.Held, 'creator-engine-outcome-unknown-no-replay') as caught:
            owner.engine.image('native')
        self.assertEqual(caught.exception.creator_client_cleanup_failure, 'ValueError')
        self.assertIsNotNone(transport.client.poll())
        self.assertEqual(len(transport.calls), 1)

    def test_identity_termination_is_exact_object_and_root_window(self):
        ids = IDs()
        called = []
        process = SimpleNamespace(kill=lambda: called.append((ids.uid, ids.gid)), poll=lambda: 0)
        with ids.patches():
            identity = b.Identity()
            identity.enter()
            identity._client = process
            with self.assertRaisesRegex(ValueError, 'batch-owned-client-required'):
                identity.terminate_client(SimpleNamespace(pid=1))
            identity.terminate_client(process)
            identity.check()
            identity.close()
        self.assertEqual(called, [((1000, 0, 0), (1000, 0, 0))])

    def test_default_polkit_transport_is_unchanged(self):
        with patch.object(c.subprocess, 'Popen', return_value='default') as popen:
            self.assertEqual(c.Driver()._spawn(['inspect', 'a'*64], b'fixed'), 'default')
        self.assertEqual(popen.call_args.args[0], [*c.PREFIX, 'inspect', 'a'*64])
        self.assertEqual(popen.call_args.kwargs, dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'}))
        process = SimpleNamespace(kill=unittest.mock.Mock())
        c.Driver()._kill_process(process)
        process.kill.assert_called_once_with()

    def test_child_signal_mask_is_cleared_only_by_fixed_callback(self):
        with patch.object(b.signal, 'pthread_sigmask') as mask:
            b._child_signal_mask()
        mask.assert_called_once_with(b.signal.SIG_SETMASK, set())

    def test_cli_is_disabled_and_fixed_errors_do_not_expose_values(self):
        for args in ([], ['--activate'], ['--identity-self-check', '--activate']):
            with patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
                self.assertEqual(b.main(args), 2)
            lines = output.getvalue().splitlines()
            self.assertEqual(lines[0], 'disposable-batch-held; resources-retained; no-replay')
            self.assertEqual(json.loads(lines[1]), dict(exception_class='ValueError', source_frame=None))
        with self.assertRaisesRegex(ValueError, 'batch-explicit-isolated-activation-required'):
            b.run({}, 'a'*64)

    def test_run_failure_preserves_primary_and_drops_saved_authority(self):
        identity = SimpleNamespace(enter=lambda: None, close=lambda: None)
        closed = []
        identity.close = lambda: closed.append(True)
        primary = c.p.Held('fixture-original-held')
        owner = SimpleNamespace(execute=lambda: None)
        def fail():
            raise primary
        owner.execute = fail
        pin = hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest()
        with patch.object(b, 'Identity', return_value=identity), \
             patch.object(b, 'driver_type', return_value=lambda identity: SimpleNamespace(owner=None)), \
             patch.object(c.p, 'read', return_value=b'{}'), \
             patch.object(c, 'Creator', return_value=owner):
            with self.assertRaises(c.p.Held) as caught:
                b.run({}, pin, activate=True)
        self.assertIs(caught.exception, primary)
        self.assertEqual(closed, [True])
        # Independent source-final and ID-final errors must not hide Creator's
        # first refusal. Real source bytes are never modified by this fixture.
        original_close = b._close_source
        failed = []
        def fail_then_drift():
            failed.append(True)
            raise primary
        def close_source(*args):
            if failed:
                raise ValueError('fixture-source-final-drift')
            return original_close(*args)
        def close_error():
            closed.append(True)
            raise ValueError('fixture-id-close')
        owner.execute = fail_then_drift
        identity.close = close_error
        with patch.object(b, 'Identity', return_value=identity), \
             patch.object(b, 'driver_type', return_value=lambda identity: SimpleNamespace(owner=None)), \
             patch.object(c.p, 'read', return_value=b'{}'), \
             patch.object(b, '_close_source', side_effect=close_source), \
             patch.object(c, 'Creator', return_value=owner):
            with self.assertRaises(c.p.Held) as caught:
                b.run({}, pin, activate=True)
        self.assertIs(caught.exception, primary)
        self.assertEqual(primary.batch_secondary_failure_classes, ('ValueError', 'ValueError'))
        self.assertEqual(closed, [True, True])

    def test_ancestor_symlink_replacement_refuses_same_held_file(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            parent = base/'parent'
            parent.mkdir(mode=0o700)
            path = parent/'source.py'
            path.write_text('public fixture')
            path.chmod(0o600)
            original = b._nine(path.lstat())
            ancestors = b._source_ancestors(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                b._close_source(path, fd, original, ancestors)
                held = base/'held-original-parent'
                parent.rename(held)
                parent.symlink_to(held, target_is_directory=True)
                self.assertEqual(b._nine(os.fstat(fd)), b._nine(path.lstat()))
                with self.assertRaisesRegex(ValueError, 'batch-source-canonical'):
                    b._close_source(path, fd, original, ancestors)
            finally:
                os.close(fd)

    def test_ancestor_mode_drift_and_noncanonical_source_refuse(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            parent = base/'parent'
            parent.mkdir(mode=0o700)
            path = parent/'source.py'
            path.write_text('public fixture')
            original = b._nine(path.lstat())
            ancestors = b._source_ancestors(path)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                parent.chmod(0o711)
                self.assertEqual(b._nine(os.fstat(fd)), b._nine(path.lstat()))
                with self.assertRaisesRegex(ValueError, 'batch-source-final-closure'):
                    b._close_source(path, fd, original, ancestors)
                link = base/'link.py'
                link.symlink_to(path)
                with self.assertRaisesRegex(ValueError, 'batch-source-canonical'):
                    b._source_ancestors(link)
            finally:
                os.close(fd)

    def test_prejournal_diagnostic_authenticates_only_own_code_and_pin(self):
        pin = hashlib.sha256(Path(b.__file__).read_bytes()).hexdigest()
        try:
            b.require(False, 'PRIVATE-FIXTURE-SECRET')
        except ValueError as error:
            original = error
        report = b.safe_failure(original, pin)
        self.assertEqual(report['exception_class'], 'ValueError')
        self.assertEqual(report['source_frame']['function'], 'require')
        self.assertEqual(report['source_frame']['source_sha256'], pin)
        self.assertNotIn('PRIVATE-FIXTURE', json.dumps(report))
        self.assertIsNone(b.safe_failure(original, '0'*64)['source_frame'])
        foreign = {'__name__': 'foreign'}
        exec(compile('def fake():raise ValueError("PRIVATE-FIXTURE-SECRET")', b.__file__, 'exec'), foreign)
        try:
            foreign['fake']()
        except ValueError as error:
            self.assertIsNone(b.safe_failure(error, pin)['source_frame'])

    def test_unknown_argument_and_dynamic_exception_never_print_values(self):
        with patch.object(sys, 'stdout', new_callable=io.StringIO) as output:
            self.assertEqual(b.main(['--PRIVATE-FIXTURE-SECRET']), 2)
        self.assertNotIn('PRIVATE-FIXTURE', output.getvalue())
        error = type('PRIVATE-FIXTURE-SECRET', (Exception,), {})('PRIVATE-FIXTURE-MESSAGE')
        answer = b.safe_failure(error, None)
        self.assertEqual(answer, dict(exception_class='unclassified-exception', source_frame=None))

    def test_no_socket_broker_prefix_or_request_extension(self):
        tree = ast.parse(Path(b.__file__).read_bytes(), feature_version=(3, 10))
        imports = {node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)}
        self.assertFalse({'socket', 'multiprocessing'} & imports)
        self.assertEqual(b.DOCKER, ('/usr/bin/docker', '--host', 'unix:///run/docker.sock'))
        self.assertNotIn('prefix', b.run.__code__.co_varnames)
        self.assertIn('driver=driver', Path(b.__file__).read_text())


if __name__ == '__main__':
    unittest.main()

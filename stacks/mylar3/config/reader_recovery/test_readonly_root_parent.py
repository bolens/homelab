"""Actual finite Parent reply with synthetic profiles and controlled observations."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import copy
import importlib.util
import os
import tempfile
import time
import types
import unittest
from unittest.mock import patch
import comic_nfs_parent_session as observer
import test_nfs_current_roles as profiles


class ParentReply(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).with_name('comic_reader_lifecycle_parent.py')
        spec = importlib.util.spec_from_file_location('readonly_parent_fixture', source)
        self.m = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.m)
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.protected = root / 'protected'; self.protected.mkdir()
        self.tree = root / 'tree'; self.tree.mkdir()
        self.grand = root / 'grand'; self.grand.mkdir()
        class Owner:
            pass
        self.owner = Owner(); self.owner.engine = Owner(); self.owner.plan = dict(nonce='a' * 64); self.owner.deadline = 999999999999
        self.row = profiles.row(4, 'observer', 'running')
        self.row['Mounts'] = [dict(Type='bind', Source=str(p), Destination=str(p), RW=rw)
                              for p, rw in ((self.protected, False), (self.tree, True), (self.grand, True))]
        self.dialogue = types.SimpleNamespace(sequence=0)
        self.session = types.SimpleNamespace(owner=self.owner, g=self.m.__dict__, cid=self.row['Id'], close=lambda: None,
            lease_replies=types.SimpleNamespace(lease=None), engine_replies=self.dialogue,
            pump=types.SimpleNamespace(deadline=888888888888),
            profile_after_release=lambda: copy.deepcopy(self.row))
        m = self.m
        m._NFS_LIVE_SESSIONS[self.owner] = self.session
        m._DIALOGUE_SEALS[self.owner.engine] = {self.session.cid: (None,)*6 + (888888888888,)}
        m._NFS_DATA_ROOTS[self.owner] = (str(self.protected), str(self.grand))
        self.epoch = (self.session, self.session.cid, self.row['State']['Pid'],
                      m.encode(m.lifecycle_state(self.row)), 123, m.encode(m.static(self.row)))
        m._NFS_CHILD_EPOCHS[self.owner] = self.epoch
        m._CHILD_TREES[self.owner] = types.SimpleNamespace(root=self.tree, child_root=self.tree)
        self.owner.baselines = {'held_native': profiles.row(1, 'native', 'running'),
                                'reader': profiles.row(3, 'reader', 'running')}
        self.owner.baselines['reader']['Mounts'] = [dict(Source=str(self.protected), Destination='/config', RW=True)]
        self.observations = []; self.callback = None; self.emitted = []
        self.seals = []; self.seal_callback = None; self.order = []
        def observe(pid, ticks, roots, writable, deadline):
            self.order.append('observe')
            self.observations.append((pid, ticks, roots, writable, deadline))
            if self.callback is not None:
                self.callback()
            return dict(roots=roots, mutation_authority=False, publication_authority=False)
        def seal(session, roots, writable, deadline):
            self.order.append('seal');self.seals.append((session, copy.deepcopy(roots), tuple(writable), deadline))
            if self.seal_callback is not None:self.seal_callback()
            return dict(namespace_sealed=True, mutation_authority=False, publication_authority=False)
        self.module = types.SimpleNamespace(observe_readonly_namespace=observe,seal_readonly_namespace=seal)
        self.owner.nfs_host_modules = lambda: {'comic_nfs_parent_session.py': self.module}
        self.owner.emit = lambda name, value: self.emitted.append((name, value))
        self.frame = dict(type='nfs-readonly-roots', nonce='a' * 64, sequence=1, payload={})
        # Metadata-route ownership is covered separately by its owning controls.
        self.metadata = patch.object(m, 'nfs_lstat', lambda p: os.lstat(p)); self.metadata.start()
        self.addCleanup(self.metadata.stop)

    def call(self):
        return self.m.LifecycleParent.nfs_readonly_roots_reply(self.owner, self.frame)

    def test_original_deadline_and_exact_live_roots_are_retained(self):
        result = self.call(); proof = result['payload']
        self.assertEqual(proof['parent_deadline'], self.owner.deadline)
        self.assertEqual(self.observations[0][-1], 888888888888)
        self.assertEqual(proof['volatile_roots'], {str(self.protected): [dict(role='reader', id='3' * 64, destination='/config')]})
        self.assertFalse(proof['mutation_authority']); self.assertFalse(proof['publication_authority'])
        self.assertEqual(self.dialogue.sequence, 1)
        self.assertIs(self.m._NFS_READONLY_ROOTS[self.owner][0], self.session)
        self.assertEqual(len(self.emitted), 2)
        self.assertEqual(self.order, ['seal', 'observe'])
        self.assertEqual(self.seals[0][0], self.session)
        self.assertEqual(self.seals[0][-1], 888888888888)
        self.assertEqual(self.emitted[0][0], 'nfs-readonly-namespace-seal.json')

    def test_before_lease_only(self):
        self.session.lease_replies.lease = object()
        with self.assertRaisesRegex(self.m.Held, 'before-lease'):
            self.call()
        self.assertEqual(self.observations, [])

    def test_once_only(self):
        self.call(); self.frame['sequence'] = 2
        with self.assertRaisesRegex(self.m.Held, 'finite-once'):
            self.call()
        self.assertEqual(len(self.observations), 1)

    def test_no_child_selected_path_pid_or_bool_sequence(self):
        for field, value in (('payload', {'pid': 1}), ('sequence', True), ('nonce', 'b' * 64)):
            original = copy.deepcopy(self.frame); self.frame[field] = value
            with self.assertRaises(self.m.Held):
                self.call()
            self.frame = original
        self.assertEqual(self.observations, [])

    def test_unexpected_writable_bind_refuses_before_observation(self):
        self.row['Mounts'][0]['RW'] = True
        with self.assertRaisesRegex(self.m.Held, 'writable-binds'):
            self.call()
        self.assertEqual(self.observations, [])

    def test_profile_or_epoch_drift_during_observation_refuses(self):
        self.callback = lambda: self.row['State'].update(Pid=999)
        with self.assertRaisesRegex(self.m.Held, 'profile-epoch'):
            self.call()
        self.assertNotIn(self.owner, self.m._NFS_READONLY_ROOTS)

    def test_source_observer_replacement_during_callback_refuses(self):
        self.callback = lambda: setattr(self.module, 'observe_readonly_namespace', lambda *args: {})
        with self.assertRaisesRegex(self.m.Held, 'original-observer'):
            self.call()
        self.assertNotIn(self.owner, self.m._NFS_READONLY_ROOTS)

    def test_live_directory_churn_allowed_but_identity_change_refuses(self):
        self.callback = lambda: (self.protected / 'journal').touch()
        self.call()
        # A distinct attempt, not replay of the admitted reply.
        self.m._NFS_READONLY_ROOTS.pop(self.owner); self.dialogue.sequence = 0
        self.callback = lambda: os.chmod(self.protected, 0o500)
        with self.assertRaisesRegex(self.m.Held, 'original-host-node'):
            self.call()

    def test_sealer_replacement_refuses_before_passive_observation(self):
        self.seal_callback = lambda: setattr(self.module, 'seal_readonly_namespace', lambda *args: {})
        with self.assertRaisesRegex(self.m.Held, 'original-namespace-sealer'):
            self.call()
        self.assertEqual(self.observations, [])
        self.assertNotIn(self.owner, self.m._NFS_READONLY_ROOTS)

    def test_sealer_cannot_replace_original_epoch(self):
        self.seal_callback = lambda: self.m._NFS_CHILD_EPOCHS.__setitem__(self.owner, tuple(list(self.epoch)))
        with self.assertRaisesRegex(self.m.Held, 'original-namespace-sealer'):
            self.call()
        self.assertEqual(self.observations, [])

    def test_sealer_cannot_rewrite_captured_root_facts(self):
        def changed(session, roots, writable, deadline):
            roots[str(self.protected)][3] += 1
            return dict(namespace_sealed=True)
        self.module.seal_readonly_namespace = changed
        with self.assertRaisesRegex(self.m.Held, 'original-namespace-sealer'):
            self.call()
        self.assertEqual(self.observations, [])

    def test_observer_cannot_rewrite_captured_root_facts(self):
        def changed(pid, ticks, roots, writable, deadline):
            roots[str(self.protected)][3] += 1
            return dict(roots=roots)
        self.module.observe_readonly_namespace = changed
        with self.assertRaisesRegex(self.m.Held, 'original-observed-roots'):
            self.call()
        self.assertNotIn(self.owner, self.m._NFS_READONLY_ROOTS)


class ObserverAdmission(unittest.TestCase):
    def test_observer_requires_actual_root_identity(self):
        with patch.object(observer.os, 'getresuid', return_value=(1000, 1000, 1000)):
            with self.assertRaisesRegex(observer.Held, 'root-observer'):
                observer.observe_readonly_namespace(os.getpid(), 1, {}, [], time.monotonic()+30)


class NamespaceCollector(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        base = Path(self.temp.name)
        self.roots = [base / name for name in ('protected', 'tree', 'grand')]
        for root in self.roots:
            root.mkdir()
        self.mountinfo = base / 'mountinfo'
        self.raw = ('1 999 0:1 / / ro - overlay overlay rw\n' +
                    ''.join(f'{i + 2} 1 8:{i + 2} / {root} {"ro" if i == 0 else "rw"} - ext4 /dev/fixture rw\n'
                            for i, root in enumerate(self.roots))).encode()
        self.mountinfo.write_bytes(self.raw)
        self.protected = {str(self.roots[0]): list(profiles.m.stamp(self.roots[0]))}
        self.writable = list(map(str, self.roots[1:]))
        self.pid = os.getpid()
        self.ticks = int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19])
        self.open = os.open
        self.stat = os.stat
        self.reads = 0; self.callback = None
        def opened(path, flags, *args, **kwargs):
            if path == '/proc/' + str(self.pid) + '/mountinfo':
                self.reads += 1
                if self.callback is not None:
                    self.callback(self.reads)
                path = self.mountinfo
            return self.open(path, flags, *args, **kwargs)
        def stated(path, *args, **kwargs):
            if path == '/proc/' + str(self.pid) + '/mountinfo':path = self.mountinfo
            return self.stat(path, *args, **kwargs)
        def owner_nodes(fd, root5, paths, deadline):
            return {p:list(observer.five(os.stat(p.lstrip('/'),dir_fd=fd,follow_symlinks=False))) for p in paths}
        for patcher in (patch.object(observer, 'readonly_namespace_nodes', owner_nodes),
                        patch.object(observer.os, 'open', opened),
                        patch.object(observer.os, 'stat', stated),
                        patch.object(observer.os, 'getresuid', return_value=(0, 0, 0)),
                        patch.object(observer.os, 'getresgid', return_value=(0, 0, 0))):
            patcher.start(); self.addCleanup(patcher.stop)

    def call(self):
        return observer.observe_readonly_namespace(self.pid, self.ticks, self.protected, self.writable, time.monotonic()+30)

    def test_real_proc_process_and_original_node_join(self):
        result = self.call()
        self.assertEqual(result['namespace_pid'], os.getpid())
        self.assertEqual(result['roots'], self.protected)
        self.assertEqual(self.reads, 2)
        self.assertFalse(result['mutation_authority']); self.assertFalse(result['publication_authority'])

    def test_stale_process_ticks_refuse(self):
        self.ticks += 1
        with self.assertRaisesRegex(observer.Held, 'original-starttick'):
            self.call()

    def test_mount_topology_change_between_reads_refuses(self):
        def change(number):
            if number == 2:
                self.mountinfo.write_bytes(self.raw.replace(b'/dev/fixture', b'/dev/replaced'))
        self.callback = change
        with self.assertRaisesRegex(observer.Held, 'namespace-closure'):
            self.call()

    def test_protected_node_mode_change_during_observation_refuses(self):
        self.callback = lambda _: os.chmod(self.roots[0], 0o500)
        with self.assertRaisesRegex(observer.Held, 'original-mounted-node'):
            self.call()

    def test_non_directory_original_refuses(self):
        self.protected[str(self.roots[0])][5] = 0o100600
        with self.assertRaisesRegex(observer.Held, 'original-roots'):
            self.call()

    def test_callback_cannot_rewrite_original_roots_or_writable_scope(self):
        expected = copy.deepcopy(self.protected)
        old_writable = tuple(self.writable)
        def changed(number):
            if number == 1:
                self.protected.clear();self.writable[:] = ['/foreign', '/other']
        self.callback = changed
        result = self.call()
        self.assertEqual(result['roots'], expected)
        self.assertEqual(set(result['mounts']['writable']), set(old_writable))


if __name__ == '__main__':
    unittest.main()

import sys
from pathlib import Path as _SourcePath
sys.path.insert(0, str(_SourcePath(__file__).parent))
"""Real finite interface admission and retained root-vector semantics; no engine."""
import copy
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch

import comic_negative_nfs_active_parent as active
import test_nfs_scope_lifetime as lifetime


class RootVectors(unittest.TestCase):
    def setUp(self):
        self.owner = lifetime.Lifetime(methodName='runTest')
        self.owner.setUp()
        self.addCleanup(self.owner.doCleanups)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.live = Path(self.temp.name) / 'live'
        self.fixed = Path(self.temp.name) / 'fixed'
        self.live.mkdir(); self.fixed.mkdir()
        self.roots = [self.live, self.fixed]
        self.roles = {'roles': {role: {'id': token * 64, 'profile': {'Mounts': []}}
                               for role, token in (('native', 'c'), ('reader', 'd'))}}
        mount = dict(RW=True, Source=str(self.live), Destination='/config')
        self.roles['roles']['reader']['profile']['Mounts'].append(mount)
        self.proof = dict(version=1, kind='parent-original-readonly-protected-roots', nonce='a' * 64,
            helper=dict(id='e' * 64, pid=99999,
                        start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]), epoch={}),
            parent_deadline=1000,
            observation=dict(namespace_pid=os.getpid(), roots={str(p): active.stamp(p) for p in self.roots},
                             namespace_root5=[1, 2, stat.S_IFDIR, 0, 0],
                             mounts=dict(protected={str(p): dict(readonly=True) for p in self.roots},
                                         mutation_authority=False, publication_authority=False),
                             mutation_authority=False, publication_authority=False),
            volatile_roots={str(self.live): [dict(role='reader', id='d' * 64, destination='/config')]},
            mutation_authority=False, publication_authority=False)
        self.owner.channel.readonly_proof = self.proof

    def invoke(self, body):
        with self.assertRaises(lifetime.Finished):
            self.owner.invoke(body)
        self.assertNotIn(self.owner.lease, active._READONLY_ROOT_PROOFS)

    def test_standalone_has_no_relaxation(self):
        files, nodes = active.protected_root_vectors(self.roots, self.roles)
        self.assertEqual(set(files), set(self.roots)); self.assertEqual(nodes, {})
        (self.live / 'journal').touch()
        with self.assertRaisesRegex(active.Held, 'forbidden-root-drift'):
            active.close_protected_roots(files, nodes)

    def test_live_churn_uses_same_original_nodes_without_second_rpc(self):
        def body(lease):
            files, nodes = active.protected_root_vectors(self.roots, self.roles, lease)
            self.assertEqual(set(files), {self.fixed}); self.assertEqual(set(nodes), {self.live})
            (self.live / 'journal').touch()
            active.close_protected_roots(files, nodes)
            lease.started = lease.acquired = True
            files2, nodes2 = active.protected_root_vectors(self.roots, self.roles, lease)
            self.assertEqual(files, files2); self.assertEqual(nodes, nodes2)
            self.assertEqual(self.owner.channel.calls, [('nfs-readonly-roots', {})])
            (self.fixed / 'unexpected').touch()
            with self.assertRaisesRegex(active.Held, 'forbidden-root-drift'):
                active.close_protected_roots(files, nodes)
        self.invoke(body)

    def test_replacement_mode_owner_or_identity_refuses(self):
        def body(lease):
            files, nodes = active.protected_root_vectors(self.roots, self.roles, lease)
            os.chmod(self.live, 0o500)
            with self.assertRaisesRegex(active.Held, 'forbidden-root-node-drift'):
                active.close_protected_roots(files, nodes)
            with self.assertRaisesRegex(active.Held, 'readonly-original-root-node'):
                active.protected_root_vectors(self.roots, self.roles, lease)
        self.invoke(body)

    def test_detached_saved_proof_is_not_a_lifetime(self):
        with self.assertRaisesRegex(active.Held, 'readonly-original-lifetime'):
            active.protected_root_vectors(self.roots, self.roles, self.owner.lease)
        self.assertEqual(self.owner.channel.calls, [])

    def test_false_or_foreign_proofs_refuse(self):
        cases = [('nonce', lambda p: p.update(nonce='b' * 64)),
                 ('process', lambda p: p['helper'].update(start_ticks=1)),
                 ('namespace', lambda p: p['observation'].update(namespace_pid=-1)),
                 ('grant', lambda p: p.update(publication_authority=True)),
                 ('roles', lambda p: p.update(volatile_roots={})),
                 ('mount', lambda p: p['observation']['mounts']['protected'][str(self.live)].update(readonly=False))]
        for name, mutate in cases:
            with self.subTest(name=name):
                original = copy.deepcopy(self.proof); mutate(self.proof)
                try:
                    with self.assertRaises(active.Held):
                        self.owner.invoke(lambda lease: active.protected_root_vectors(self.roots, self.roles, lease))
                finally:
                    self.proof.clear(); self.proof.update(original)
                    self.owner.lease.readonly_requested = False

    def test_lost_reply_cannot_be_retried(self):
        def body(lease):
            with patch.object(self.owner.channel, 'readonly_proof', None):
                with self.assertRaises(EOFError):
                    active.protected_root_vectors(self.roots, self.roles, lease)
            with self.assertRaisesRegex(active.Held, 'readonly-original-cache'):
                active.protected_root_vectors(self.roots, self.roles, lease)
            self.assertEqual(len(self.owner.channel.calls), 1)
        self.invoke(body)

    def test_foreign_cache_equality_is_never_called(self):
        calls = []
        class Foreign:
            def __eq__(self, other):
                calls.append(other)
                raise AssertionError('foreign equality')
        def corrupt():
            active._READONLY_ROOT_PROOFS[self.owner.lease] = Foreign()
        self.owner.channel.readonly_callback = corrupt
        with self.assertRaisesRegex(active.Held, 'readonly-original-slot'):
            self.owner.invoke(lambda lease: active.protected_root_vectors(self.roots, self.roles, lease))
        self.assertEqual(calls, [])
        self.assertNotIn(self.owner.lease, active._READONLY_ROOT_PROOFS)


if __name__ == '__main__':
    unittest.main()

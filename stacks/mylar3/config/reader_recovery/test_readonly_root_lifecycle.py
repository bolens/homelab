"""Pure staging/cleanup helpers; synthetic local filesystem, no NFS grant."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent))
import hashlib
import os
import tempfile
import types
import unittest
from unittest.mock import patch
import comic_negative_nfs_active_lifecycle as m


class LifecycleVectors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.live, self.fixed, self.staging = [self.base / n for n in ('live', 'fixed', 'staging')]
        for p in (self.live, self.fixed, self.staging):
            p.mkdir(mode=0o700)
        self.roots = [self.live, self.fixed]
        self.files = ((str(self.fixed), tuple(m.stamp(self.fixed))),)
        self.nodes = ((str(self.live), tuple(m.stamp(self.live)[i] for i in (0, 1, 5, 6, 7))),)
        self.parent = self.staging / ('.comic-nfs-private-' + 'a' * 32)
        self.plan = dict(path=str(self.parent), grandparent_signature=m.stamp(self.staging),
                         expected_device=self.staging.stat().st_dev, mount_identity=dict(fstype='nfs4'))

    def prepare(self, observe=None):
        return m._prepare_parent(self.plan, self.roots, observe or (lambda _: self.plan['mount_identity']),
                                 self.files, self.nodes)

    def fixture(self):
        self.parent.mkdir(mode=0o700)
        child = self.parent / ('.comic-nfs-probe-' + 'b' * 32); child.mkdir(mode=0o700)
        for name in ('source', 'target'):
            (child / name).mkdir(mode=0o700)
        names = {'source/source.bin', 'source/collision.bin', 'target/foreign.bin',
                 'stage-intent.json', 'collision-intent.json', 'retire-intent.json',
                 'restore-intent.json', 'unstage-intent.json', 'result.json'}
        facts = {}
        for name in names:
            p = child / name; p.write_bytes(b'synthetic original\n'); p.chmod(0o600)
            facts[name] = dict(signature=m.stamp(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        parent = dict(path=str(self.parent), signature=m.stamp(self.parent),
                      grandparent_identity=m.stamp(self.staging)[:2],
                      grandparent_node5=[m.stamp(self.staging)[i] for i in (0, 1, 5, 6, 7)])
        return parent, dict(path=str(child), signature=m.stamp(child)), facts, {n: m.stamp(child / n) for n in ('source', 'target')}

    def cleanup(self, fixture, callback):
        return m._cleanup_hardlink_owned(*fixture, self.roots, types.SimpleNamespace(pulse=callback), self.files, self.nodes)

    def test_configured_prepare_accepts_live_churn_without_rebasing_node(self):
        def observe(_):
            (self.live / 'journal').touch(); return self.plan['mount_identity']
        result = self.prepare(observe)
        self.assertEqual(result['path'], str(self.parent)); self.assertEqual(os.listdir(self.parent), [])

    def test_standalone_prepare_retains_full_metadata_guards(self):
        def observe(_):
            (self.live / 'journal').touch(); return self.plan['mount_identity']
        with self.assertRaises(m.Held):
            m.prepare_parent(self.plan, self.roots, observe)
        self.assertFalse(self.parent.exists())

    def test_missing_duplicate_or_foreign_root_vector_refuses(self):
        for files, nodes in (((), self.nodes), (self.files, self.nodes + self.nodes),
                             (self.files + self.files, self.nodes),
                             (self.files, ((str(self.staging), self.nodes[0][1]),))):
            with self.subTest(files=len(files), nodes=len(nodes)), self.assertRaises(m.Held):
                m._protected_vectors(self.roots, files, nodes)

    def test_node_mode_and_regular_file_vectors_refuse(self):
        os.chmod(self.live, 0o711)
        with self.assertRaises(m.Held):
            m._protected_vectors(self.roots, self.files, self.nodes)
        malformed = list(self.files[0][1]); malformed[5] = 0o100600
        with self.assertRaises(m.Held):
            m._protected_vectors(self.roots, ((str(self.fixed), tuple(malformed)),), self.nodes)

    def test_complete_roots_still_guard_overlap(self):
        self.plan['path'] = str(self.live / self.parent.name)
        with self.assertRaisesRegex(m.Held, 'protected-overlap'):
            self.prepare()
        self.assertEqual(os.listdir(self.live), [])

    def test_node_only_root_still_guards_physical_alias(self):
        original = m.stamp
        def stamp(path):
            return original(self.live) if Path(path) == self.base else original(path)
        with patch.object(m, 'stamp', stamp), self.assertRaisesRegex(m.Held, 'physical-protected-alias'):
            self.prepare()
        self.assertFalse(self.parent.exists())

    def test_cleanup_closes_node_after_every_pulse_and_keeps_other_roots(self):
        fixture = self.fixture(); calls = []
        def churn():
            calls.append(1); (self.live / ('journal-' + str(len(calls)))).touch()
        result = self.cleanup(fixture, churn)
        self.assertTrue(result['owned_fixture_absence_verified']); self.assertFalse(self.parent.exists())
        self.assertGreater(len(calls), 9); self.assertEqual(os.listdir(self.fixed), [])

    def test_cleanup_fixed_root_churn_refuses_before_unlink(self):
        fixture = self.fixture()
        def change():
            (self.fixed / 'unexpected').touch()
        with self.assertRaises(m.Held):
            self.cleanup(fixture, change)
        self.assertTrue((Path(fixture[1]['path']) / 'result.json').exists())

    def test_cleanup_file_mutation_refuses_before_unlink(self):
        fixture = self.fixture(); leaf = Path(fixture[1]['path']) / 'result.json'
        with self.assertRaises(m.Held):
            self.cleanup(fixture, lambda: leaf.write_bytes(b'changed'))
        self.assertEqual(len(fixture[2]), len([p for p in Path(fixture[1]['path']).rglob('*') if p.is_file()]))

    def test_cleanup_node_mode_drift_refuses_before_unlink(self):
        fixture = self.fixture()
        with self.assertRaises(m.Held):
            self.cleanup(fixture, lambda: os.chmod(self.live, 0o711))
        self.assertTrue((Path(fixture[1]['path']) / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()

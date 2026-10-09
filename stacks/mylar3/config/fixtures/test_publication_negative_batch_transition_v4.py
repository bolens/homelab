"""Real local five-file syscalls, explicit fake SDK. NOT native acceptance."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import os
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(_PORTABLE_ROOT / 'fixtures'))

def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
base = load('prepare_tests', str(_PORTABLE_ROOT / 'test_publication_negative_batch.py'))
projection = load('projection', str(_PORTABLE_ROOT / 'fixtures/publication_negative_batch_projection_v2.py'))
m = load('transition', str(_PORTABLE_ROOT / 'fixtures/publication_negative_batch_transition_v4.py'))

class Tests(unittest.TestCase):

    def setUp(self):
        self.c = base.Tests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        c = self.c
        self.targets = c.root / 'targets'
        self.targets.mkdir(mode=448)
        c.mods[2].writer_identity = lambda w: [1, 2, 3, 4]
        c.mods[3]._protected_paths = lambda *a: set()
        c.mods[3].attrs = lambda p: 'fixture-attrs'
        c.controller.observe = lambda w, body: dict(observed=[dict(catalog=dict(path=str(c.root / f"correct-{body['allowed'][0]['issueid']}.cbz")))])
        self.members = []
        k = projection.kernel()
        for i, prep in enumerate(c.preps):
            correct = c.root / f'correct-{i}.cbz'
            correct.write_bytes(b'correct')
            correct.chmod(384)
            prep.binding.update(counterpart=str(correct), protected_paths=[], xattrs={str(Path(prep.binding['source'])): 'fixture-attrs', str(correct): 'fixture-attrs'})
            prep.binding['file_facts'][str(correct)] = dict(signature9=m.sig(correct), sha256=__import__('hashlib').sha256(correct.read_bytes()).hexdigest())
            self.members.append(dict(source=prep.binding['source'], target=str(self.targets / f'original-{i}.cbz'), original=k._fact(Path(prep.binding['source']), 1)))
        c.reader.native_syscall_controls = lambda f: ({}, {})
        c.reader.revalidate_rollback_ready = lambda f: None
        c.reader.revalidate_committed = lambda f: (_ for _ in ()).throw(m.Held('reader-not-committed'))

    def make(self):
        b = self.c.make()
        q = projection.BatchNamespace(projection._KEY, self.members, self.c.journal)
        return m.NegativeBatchReservation(m._KEY, b, q)

    def test_five_shared_parent_staged_exact_aliases(self):
        r = self.make()
        result = r.stage_all()
        self.assertFalse(result['publication_acceptance'])
        self.assertEqual(r.projection.phases, ['linked'] * 5)
        for v in self.members:
            self.assertEqual(os.stat(v['source']).st_ino, os.stat(v['target']).st_ino)
            self.assertEqual(os.stat(v['source']).st_nlink, 2)

    def test_exact_staged_rollback_returns_originals(self):
        r = self.make()
        r.stage_all()
        r.rollback_staging()
        self.assertEqual(r.projection.phases, ['source'] * 5)
        self.assertTrue(all((Path(v['source']).exists() and (not Path(v['target']).exists()) for v in self.members)))

    def test_retirement_requires_reader_commit_before_unlink(self):
        r = self.make()
        r.stage_all()
        with self.assertRaisesRegex(m.Held, 'not-committed'):
            r.retire_all()
        self.assertTrue(all((Path(v['source']).exists() for v in self.members)))

    def test_last_reader_foreign_namespace_holds_before_link(self):
        r = self.make()
        self.c.reader.native_syscall_controls = lambda f: ((self.c.lib / 'foreign').write_bytes(b'foreign') and {}, {})
        with self.assertRaises(m.Held):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())
        self.assertEqual(os.stat(self.members[0]['source']).st_nlink, 1)

    def test_last_reader_source_change_holds_before_link(self):
        r = self.make()

        def changed(f):
            Path(self.members[0]['source']).write_bytes(b'foreign')
            return ({}, {})
        self.c.reader.native_syscall_controls = changed
        with self.assertRaises(m.Held):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_last_reader_sidecar_holds_before_link(self):
        r = self.make()

        def changed(f):
            Path(str(self.c.native) + '-wal').write_bytes(b'foreign')
            return ({}, {})
        self.c.reader.native_syscall_controls = changed
        with self.assertRaises(m.Held):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_last_reader_other_claim_appearance_holds(self):
        shadow = self.c.root / 'shadow.cbz'
        for p in self.c.preps:
            p.binding['complete_catalog_absence']['passive_claim_files'][str(shadow)] = None
        r = self.make()

        def changed(f):
            os.symlink(self.members[0]['source'], shadow)
            return ({}, {})
        self.c.reader.native_syscall_controls = changed
        with self.assertRaises(m.Held):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_conflicting_reader_ancestor_holds_before_syscall(self):
        r = self.make()
        self.c.reader.native_syscall_controls = lambda f: ({}, {self.c.lib: [0] * 5})
        with self.assertRaisesRegex(m.Held, 'conflicting-reader'):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_original_binding_cannot_reseal(self):
        r = self.make()
        r.batch.bound[0]['owner'] = {'issueid': 'foreign'}
        with self.assertRaises(m.Held):
            r.stage_all()

    def test_marker_retained_no_terminal_grant(self):
        r = self.make()
        r.stage_all()
        with self.assertRaises(m.Held):
            r.terminal()
        self.assertTrue(r.batch.marker.exists())

    def test_retention_inside_publication_root_holds_before_link(self):
        self.targets = self.c.lib / 'targets'
        self.targets.mkdir(mode=448)
        for i, v in enumerate(self.members):
            v['target'] = str(self.targets / f'original-{i}.cbz')
        with self.assertRaisesRegex(m.Held, 'outside-all-publication'):
            self.make()
        self.assertTrue(all((os.stat(v['source']).st_nlink == 1 for v in self.members)))

    def test_nonprivate_retention_parent_holds_before_link(self):
        self.targets.chmod(493)
        with self.assertRaisesRegex(m.Held, 'private-same'):
            self.make()
        self.assertTrue(all((os.stat(v['source']).st_nlink == 1 for v in self.members)))

    def test_same_five_purposes_consumed_without_reentering_Writer(self):
        r = self.make()
        r.stage_all()
        self.c.reader.revalidate_committed = lambda f: None
        for prep in self.c.preps:
            ack = r.consume_native(prep)
            self.assertFalse(ack['publication_acceptance'])
            self.assertTrue(ack['marker_retained'])
        self.assertEqual(r.projection.phases, ['retained'] * 5)
        self.assertTrue(all((not Path(v['source']).exists() and Path(v['target']).stat().st_nlink == 1 for v in self.members)))

    def test_foreign_preparation_cannot_consume(self):
        r = self.make()
        r.stage_all()
        self.c.reader.revalidate_committed = lambda f: None
        with self.assertRaisesRegex(m.Held, 'exact-original'):
            r.consume_native(object())
        self.assertTrue(all((Path(v['source']).exists() for v in self.members)))

    def test_consumption_retry_no_replay(self):
        r = self.make()
        r.stage_all()
        self.c.reader.revalidate_committed = lambda f: None
        r.consume_native(self.c.preps[0])
        with self.assertRaisesRegex(m.Held, 'finite-one-member'):
            r.consume_native(self.c.preps[0])
        self.assertEqual(Path(self.members[0]['target']).stat().st_nlink, 1)

    def test_final_syscall_seal_has_no_late_marker_read_callback(self):
        shadow = self.c.root / 'other-shadow.cbz'
        for prep in self.c.preps:
            prep.binding['complete_catalog_absence']['passive_claim_files'][str(shadow)] = None
        r = self.make()
        real = Path.read_bytes
        fired = False

        def changed(p):
            nonlocal fired
            value = real(p)
            if p == r.batch.marker and any((frame.function == '_direct' for frame in inspect.stack())):
                os.symlink(self.members[0]['source'], shadow)
                fired = True
            return value
        with patch.object(Path, 'read_bytes', changed):
            r.stage_all()
        self.assertFalse(fired)
        self.assertFalse(shadow.exists())
        self.assertEqual(r.projection.phases, ['linked'] * 5)

    def test_reader_marker_read_then_other_claim_change_before_syscall_holds(self):
        shadow = self.c.root / 'other-shadow.cbz'
        for prep in self.c.preps:
            prep.binding['complete_catalog_absence']['passive_claim_files'][str(shadow)] = None
        r = self.make()

        def changed(f):
            r.batch.marker.read_bytes()
            os.symlink(self.members[0]['source'], shadow)
            return ({}, {})
        self.c.reader.native_syscall_controls = changed
        with self.assertRaises(m.Held):
            r.stage_all()
        self.assertFalse(Path(self.members[0]['target']).exists())
        self.assertEqual(os.stat(self.members[0]['source']).st_nlink, 1)

    def test_public_factory_missing_installed_components_holds(self):
        with self.assertRaises(m.Held):
            m.from_prepared(None, [])
if __name__ == '__main__':
    unittest.main()

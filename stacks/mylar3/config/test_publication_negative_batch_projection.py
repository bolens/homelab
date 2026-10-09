"""Actual local alias geometry; private projection key is NOT native authority."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('batch_projection_fixture', str(_PORTABLE_ROOT / 'publication_negative_batch_projection.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ns = importlib.util.spec_from_file_location('fixture_loader', str(_PORTABLE_ROOT / 'publication_negative_namespace.py'))
loader = importlib.util.module_from_spec(ns)
ns.loader.exec_module(loader)

def fixture_kernel():
    if m.KERNEL_SHA != loader.KERNEL_SHA:
        raise m.Held('kernel-pin')
    return loader._load(Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py')), m.KERNEL_SHA)

class BatchTests(unittest.TestCase):

    def setUp(self):
        self.t = tempfile.TemporaryDirectory(prefix='negative-batch-projection-fixture-')
        self.addCleanup(self.t.cleanup)
        self.root = Path(self.t.name)
        self.root.chmod(448)
        self.library = self.root / 'library'
        self.library.mkdir(mode=448)
        self.private = self.root / 'private'
        self.private.mkdir(mode=448)
        self.journal = self.root / 'journal'
        self.journal.mkdir(mode=448)
        fixture = patch.object(m, 'kernel', side_effect=fixture_kernel)
        fixture.start()
        self.addCleanup(fixture.stop)
        path = patch.object(m, 'KERNEL', Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py')))
        path.start()
        self.addCleanup(path.stop)
        self.k = m.kernel()
        self.members = []
        for i in range(5):
            p = self.library / f'source-{i}.cbz'
            p.write_bytes(f'exact original {i}'.encode())
            p.chmod(384)
            self.members.append(dict(source=str(p), target=str(self.private / f'original-{i}.cbz'), original=self.k._fact(p, 1)))

    def make(self):
        return m.BatchNamespace(m._KEY, self.members, self.journal)

    def link(self, b, i):
        b.intent(i, 'link')
        v = self.members[i]
        os.link(v['source'], v['target'])
        b.observe_transition(i)

    def retire(self, b, i):
        b.intent(i, 'retire')
        os.unlink(self.members[i]['source'])
        b.observe_transition(i)

    def test_all_five_shared_parent_alias_states(self):
        b = self.make()
        for i in range(5):
            self.link(b, i)
            b.close()
        self.assertEqual(b.phases, ['linked'] * 5)
        for i in range(5):
            self.retire(b, i)
            b.close()
        self.assertEqual(b.phases, ['retained'] * 5)
        self.assertTrue(all((Path(v['target']).stat().st_nlink == 1 for v in self.members)))

    def test_shared_parent_rollback_staging(self):
        b = self.make()
        for i in range(5):
            self.link(b, i)
        for i in reversed(range(5)):
            b.intent(i, 'unstage')
            os.unlink(self.members[i]['target'])
            b.observe_transition(i)
        self.assertEqual(b.phases, ['source'] * 5)
        b.close()

    def test_no_factory_boolean(self):
        with self.assertRaises(m.Held):
            m.BatchNamespace(True, self.members, self.journal)

    def test_exact_five_only(self):
        with self.assertRaises(m.Held):
            m.BatchNamespace(m._KEY, self.members[:4], self.journal)

    def test_original_changed_before_capture(self):
        Path(self.members[2]['source']).write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            self.make()
        self.assertEqual(list(self.journal.iterdir()), [])

    def test_foreign_namespace_never_adopted(self):
        b = self.make()
        (self.library / 'foreign').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            b.intent(0, 'link')
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_unreviewed_alias_held(self):
        b = self.make()
        os.link(self.members[0]['source'], self.root / 'foreign-alias')
        with self.assertRaises(m.Held):
            b.close()

    def test_owned_intent_required(self):
        b = self.make()
        os.link(self.members[0]['source'], self.members[0]['target'])
        with self.assertRaises(m.Held):
            b.observe_transition(0)

    def test_no_second_intent_pending(self):
        b = self.make()
        b.intent(0, 'link')
        with self.assertRaises(m.Held):
            b.intent(1, 'link')

    def test_foreign_target_held_retains_source(self):
        b = self.make()
        b.intent(0, 'link')
        Path(self.members[0]['target']).write_bytes(b'foreign')
        with self.assertRaises(Exception):
            b.observe_transition(0)
        self.assertTrue(Path(self.members[0]['source']).exists())

    def test_original_changed_after_intent_held(self):
        b = self.make()
        b.intent(0, 'link')
        p = Path(self.members[0]['source'])
        p.write_bytes(b'foreign')
        os.link(p, self.members[0]['target'])
        with self.assertRaises(m.Held):
            b.observe_transition(0)

    def test_journal_foreignchild_held(self):
        b = self.make()
        (self.journal / 'foreign.json').write_bytes(b'{}')
        with self.assertRaises(m.Held):
            b.close()

    def test_original_receipt_rewrite_held(self):
        b = self.make()
        (self.journal / '00.json').write_bytes(b'{}')
        with self.assertRaises(m.Held):
            b.close()

    def test_state_reseal_not_accepted(self):
        b = self.make()
        b.phases[0] = 'retained'
        with self.assertRaises(m.Held):
            b.close()

    def test_late_namespace_callback_foreign_journal_held(self):
        b = self.make()
        real = b.k._namespace
        fired = False

        def changed(p):
            nonlocal fired
            value = real(p)
            if not fired:
                fired = True
                (self.journal / 'foreign.json').write_bytes(b'{}')
            return value
        with patch.object(b.k, '_namespace', side_effect=changed):
            with self.assertRaises(m.Held):
                b.close()
        self.assertTrue(fired)

    def test_initial_kernel_callback_rebuilt_parent_same_leaves_held(self):
        outer = self.root / 'external'
        outer.mkdir(mode=448)
        self.library.rename(outer / 'library')
        self.library = outer / 'library'
        for i, v in enumerate(self.members):
            v['source'] = str(self.library / f'source-{i}.cbz')
        real = m.kernel
        old = [m.sig(Path(v['source'])) for v in self.members]
        fired = False

        def changed():
            nonlocal fired
            module = real()
            retained = self.root / 'retained-external'
            outer.rename(retained)
            outer.mkdir(mode=448)
            (retained / 'library').rename(outer / 'library')
            fired = True
            return module
        with patch.object(m, 'kernel', side_effect=changed):
            with self.assertRaisesRegex(m.Held, 'initial-declared-ancestor'):
                self.make()
        self.assertTrue(fired)
        self.assertEqual(old, [m.sig(Path(v['source'])) for v in self.members])
        self.assertEqual(list(self.journal.iterdir()), [])

    def test_relative_receipt_create_transient_parent_alias_never_writes_foreign(self):
        b = self.make()
        real = os.open
        fired = False
        foreign = self.root / 'foreign'
        foreign.mkdir(mode=448)

        def changed(path, *args, **kw):
            nonlocal fired
            if path == '01.json' and (not fired):
                saved = self.root / 'saved-journal'
                self.journal.rename(saved)
                self.journal.symlink_to(foreign, target_is_directory=True)
                try:
                    fd = real(path, *args, **kw)
                finally:
                    self.journal.unlink()
                    saved.rename(self.journal)
                fired = True
                return fd
            return real(path, *args, **kw)
        with patch.object(os, 'open', side_effect=changed):
            b.intent(0, 'link')
        self.assertTrue(fired)
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertTrue((self.journal / '01.json').is_file())
        self.assertFalse(Path(self.members[0]['target']).exists())

    def test_journal_FD_replacement_before_open_refused_no_foreign_write(self):
        b = self.make()
        real = os.open
        foreign = self.root / 'foreign'
        foreign.mkdir(mode=448)
        fired = False

        def changed(path, *args, **kw):
            nonlocal fired
            if path == self.journal and (not fired):
                self.journal.rename(self.root / 'saved')
                self.journal.symlink_to(foreign, target_is_directory=True)
                fired = True
            return real(path, *args, **kw)
        with patch.object(os, 'open', side_effect=changed):
            with self.assertRaises(OSError):
                b.intent(0, 'link')
        self.assertTrue(fired)
        self.assertEqual(list(foreign.iterdir()), [])

    def test_sources_retained_no_SQL_import_or_marker_clear(self):
        b = self.make()
        ack = b.intent(0, 'link')
        self.assertFalse(ack['syscall_authority'])
        self.assertTrue(all((Path(v['source']).exists() for v in self.members)))
        source = Path(m.__file__).read_text()
        self.assertNotIn('sqlite3.connect', source)
        self.assertNotIn('os.unlink', source)
        self.assertNotIn('os.link(', source)

class ReverseTests(unittest.TestCase):
    setUp = BatchTests.setUp
    make = BatchTests.make
    link = BatchTests.link
    retire = BatchTests.retire

    def test_exact_retained_to_linked_reverse_records_new_ctime(self):
        b = self.make()
        self.link(b, 0)
        self.retire(b, 0)
        before = b.facts[0]['signature9']
        b.intent(0, 'restore')
        os.link(self.members[0]['target'], self.members[0]['source'])
        b.observe_transition(0)
        self.assertEqual(b.phases[0], 'linked')
        self.assertEqual(b.facts[0]['signature9'][8], 2)
        self.assertEqual(b.facts[0]['signature9'][:2], before[:2])
        b.close()

    def test_restore_wrong_predecessor_held_no_intent(self):
        b = self.make()
        with self.assertRaises(m.Held):
            b.intent(0, 'restore')
        self.assertFalse(Path(self.members[0]['target']).exists())
if __name__ == '__main__':
    unittest.main()

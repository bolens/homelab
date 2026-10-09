"""Disposable admission mechanics; fake parent/native wrappers issue no live grant."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
from contextlib import closing
import copy
import hashlib
import importlib.util
import inspect
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
m = load('admission_fixture', str(_PORTABLE_ROOT / 'fixtures/comic_komga_stopped_reader_admission_v3.py'))
d = load('disk_fixture', str(_PORTABLE_ROOT / 'fixtures/comic_komga_stopped_reader_disk_v3.py'))
f = load('kernel_fixture', str(_PORTABLE_ROOT / 'test_publication_reader_softdelete.py'))

class FixtureCoordinator:

    def __init__(self, control):
        self._files = {control: m.sig(control)}
        self._ancestors = m.parents([control])

    def close_passive(self):
        for p, v in self._files.items():
            m.check(m.sig(p) == v, 'fixture-native-control')

    def revalidate(self):
        self.close_passive()
        return {'mutation_authority': False}

class FixtureNegative:

    def __init__(self, path):
        self.path = path
        self.binding = {'file_facts': {str(path): {'signature9': list(m.sig(path)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}}, 'mutation_authority': False}

    def revalidate(self):
        m.check(list(m.sig(self.path)) == self.binding['file_facts'][str(self.path)]['signature9'], 'fixture-negative')
        return copy.deepcopy(self.binding)

class AdmissionTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='reader-admission-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(448)
        self.config = self.root / 'config'
        self.config.mkdir(mode=448)
        self.restore = self.root / 'restore'
        self.restore.mkdir(mode=448)
        self.scratch = self.root / 'scratch'
        self.scratch.mkdir(mode=448)
        self.operation = self.root / 'operation'
        self.operation.mkdir(mode=448)
        self.fixture = f.Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        with closing(sqlite3.connect(self.config / 'database.sqlite')) as c:
            self.fixture.conn.backup(c)
        with closing(sqlite3.connect(self.config / 'tasks.sqlite')) as c:
            for obj in sorted(f.SCHEMA['databases']['tasks.sqlite']['objects'], key=lambda v: v['type'] != 'table'):
                if obj['sql']:
                    c.execute(obj['sql'])
        for name in ('database.sqlite', 'tasks.sqlite'):
            (self.config / name).chmod(384)
            shutil.copy2(self.config / name, self.restore / name)
        self.control = self.root / 'control.json'
        self.control.write_text('{}')
        self.control.chmod(384)
        self.archive = self.root / 'original.cbz'
        self.archive.write_bytes(b'disposable retained bytes')
        self.archive.chmod(384)
        self.context = m.CheckedChildInvocation(m._KEY, 'a' * 64, {self.control: m.sig(self.control)}, m.parents([self.control]), dict(reader_root=str(self.config), scratch=str(self.scratch), operation=str(self.operation), restore_root=str(self.restore)))
        self.coordinator = FixtureCoordinator(self.control)
        self.negative = [FixtureNegative(self.archive)]
        self.plan = d.k.compile_plan(f.SCHEMA, self.fixture.manifest)

    def admission(self):
        return m.StoppedReaderAdmission(m._KEY, self.context, self.coordinator, self.negative, d, f.SCHEMA, self.plan)

    def commit(self):
        with closing(sqlite3.connect(self.config / 'database.sqlite')) as c:
            for p in self.plan['parameters']:
                c.execute(d.k.SQL, [d.k.untyped(v) for v in p])
            c.commit()

    def test_before_current_eleven_full_table_observation(self):
        a = self.admission()
        self.assertEqual(a.phase, 'before')
        self.assertFalse(a.binding['mutation_authority'])
        self.assertFalse(a.operational)
        self.assertEqual(a.binding['before']['database.sqlite'][2], self.plan['before_rows'])

    def test_first_commit_pair_callback_foreign_correct_row_holds(self):
        a = self.admission()
        self.commit()
        real = d.pair
        fired = False

        def altered(path):
            nonlocal fired
            if path == self.config / 'database.sqlite' and (not fired):
                fired = True
                with closing(sqlite3.connect(path)) as conn:
                    conn.execute("UPDATE BOOK SET NAME='foreign-late' WHERE ID='correct-0'")
                    conn.commit()
            return real(path)
        with patch.object(d, 'pair', side_effect=altered):
            with self.assertRaises(m.Held):
                a.bind_committed()
        self.assertTrue(fired)
        self.assertEqual(a.phase, 'before')

    def test_final_commit_pair_callback_foreign_correct_row_holds(self):
        a = self.admission()
        self.commit()
        real = d.pair
        count = 0

        def altered(path):
            nonlocal count
            value = real(path)
            if path == self.config / 'database.sqlite' and any((f.function == 'bind_committed' and f.code_context and ('self._disk.pair(self._root/name)' in f.code_context[0]) for f in inspect.stack())):
                count += 1
                if count == 2:
                    with closing(sqlite3.connect(path)) as conn:
                        conn.execute("UPDATE BOOK SET NAME='foreign-late' WHERE ID='correct-0'")
                        conn.commit()
            return value
        with patch.object(d, 'pair', side_effect=altered):
            with self.assertRaises(m.Held):
                a.bind_committed()
        self.assertEqual(a.phase, 'before')

    def test_exact_five_row_transition(self):
        a = self.admission()
        before = a.binding
        self.commit()
        a.bind_committed()
        a.revalidate(before)
        self.assertEqual(a.phase, 'committed')
        self.assertEqual(a.binding, before)
        self.assertEqual(a.binding['before']['tasks.sqlite'], a.binding['after']['tasks.sqlite'])

    def test_same_phase_reseal_refused(self):
        a = self.admission()
        self.commit()
        a.bind_committed()
        with self.assertRaises(m.Held):
            a.bind_committed()

    def test_missing_real_parent_default_holds(self):
        with self.assertRaisesRegex(m.Held, 'owning-producer-not-installed'):
            m.admit_child({'stopped': True}, self.coordinator, self.negative)

    def test_public_constructor_requires_owned_context(self):
        with self.assertRaises(m.Held):
            m.CheckedChildInvocation(None, 'a' * 64, {}, {}, {})

    def test_nonce_not_generic_boolean(self):
        with self.assertRaises(m.Held):
            m.CheckedChildInvocation(m._KEY, True, {}, {}, {})

    def test_mutated_invocation_document_held(self):
        self.context._document['reader_root'] = str(self.restore)
        with self.assertRaises(m.Held):
            self.context.close_passive()

    def test_mutated_invocation_control_map_held(self):
        self.context._facts.clear()
        with self.assertRaises(m.Held):
            self.context.close_passive()

    def test_changed_current_book_before_admission(self):
        with closing(sqlite3.connect(self.config / 'database.sqlite')) as c:
            c.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
            c.commit()
        with self.assertRaises(m.Held):
            self.admission()

    def test_unchanged_main_cannot_claim_commit(self):
        a = self.admission()
        with self.assertRaises(m.Held):
            a.bind_committed()

    def test_foreign_correct_book_not_expected_delta(self):
        a = self.admission()
        self.commit()
        with closing(sqlite3.connect(self.config / 'database.sqlite')) as c:
            c.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
            c.commit()
        with self.assertRaises(m.Held):
            a.bind_committed()

    def test_foreign_opaque_table_not_expected_delta(self):
        a = self.admission()
        self.commit()
        with closing(sqlite3.connect(self.config / 'database.sqlite')) as c:
            c.execute('CREATE TABLE FOREIGN_TABLE(a)')
            c.execute('INSERT INTO FOREIGN_TABLE VALUES (1)')
            c.commit()
        with self.assertRaises(m.Held):
            a.bind_committed()

    def test_tasks_pair_change_holds(self):
        a = self.admission()
        self.commit()
        with closing(sqlite3.connect(self.config / 'tasks.sqlite')) as c:
            c.execute('PRAGMA user_version=7')
            c.commit()
        with self.assertRaises(m.Held):
            a.bind_committed()

    def test_mutable_physical_before_CAS_cannot_reseal(self):
        a = self.admission()
        db = self.config / 'database.sqlite'
        replacement = self.config / 'replacement.sqlite'
        shutil.copy2(db, replacement)
        replacement.replace(db)
        a._pairs['database.sqlite'] = d.pair(db)
        a._reader_directory = m.sig(self.config)
        with self.assertRaises(m.Held):
            a.revalidate()

    def test_retained_restore_change_holds(self):
        a = self.admission()
        (self.restore / 'database.sqlite').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            a.revalidate()

    def test_duplicate_baseline_conflict_never_masks_original(self):
        original = m.sig(self.control)
        replacement = list(original)
        replacement[4] += 1
        with self.assertRaisesRegex(m.Held, 'conflicting-control-baseline'):
            m.merge_vectors({self.control: original}, {self.control: replacement})

    def test_changed_control_after_semantic_observation(self):
        a = self.admission()
        real = a._observe

        def altered():
            value = real()
            self.control.chmod(416)
            return value
        with patch.object(m.StoppedReaderAdmission, '_observe', side_effect=altered):
            with self.assertRaises(m.Held):
                a.revalidate()

    def test_new_companion_after_semantic_observation(self):
        a = self.admission()
        real = a._observe

        def altered():
            value = real()
            Path(str(self.config / 'database.sqlite') + '-journal').write_bytes(b'foreign')
            return value
        with patch.object(m.StoppedReaderAdmission, '_observe', side_effect=altered):
            with self.assertRaises((m.Held, d.Held)):
                a.revalidate()

    def test_native_preparation_rebinding_holds(self):
        a = self.admission()
        self.negative[0].binding['foreign'] = 'unreviewed'
        with self.assertRaises(m.Held):
            a.revalidate()

    def test_expected_projection_mutation_holds(self):
        a = self.admission()
        a._expected['tasks.sqlite'] = ('foreign',)
        with self.assertRaises(m.Held):
            a.revalidate()

    def test_binding_copy_not_mutable_core(self):
        a = self.admission()
        value = a.binding
        value['before'].clear()
        a.revalidate()
        self.assertTrue(a.binding['before'])

    def test_reader_output_overlap_holds_before_write(self):
        self.context._document['operation'] = str(self.config)
        with self.assertRaises(m.Held):
            self.admission()

    def test_restore_is_live_root_rejected(self):
        self.context._document['restore_root'] = str(self.config)
        with self.assertRaises(m.Held):
            self.admission()

    def test_scratch_parent_contains_live_root_rejected(self):
        self.context._document['scratch'] = str(self.root)
        with self.assertRaises(m.Held):
            self.admission()

    def test_initial_external_ancestor_rebuild(self):
        a = self.admission()
        self.root.rename(self.root.with_name(self.root.name + '-retained'))
        moved = self.root.with_name(self.root.name + '-retained')
        self.root.mkdir(mode=448)
        for p in list(moved.iterdir()):
            p.rename(self.root / p.name)
        moved.rmdir()
        with self.assertRaises(m.Held):
            a.close_passive()

    def test_late_reader_leaf_control_change_direct_closure(self):
        a = self.admission()
        real = m.sig
        fired = []

        def altered(p):
            v = real(p)
            if Path(p) == self.config / 'tasks.sqlite' and (not fired):
                fired.append(True)
                self.control.chmod(416)
            return v
        with patch.object(m, 'sig', side_effect=altered):
            with self.assertRaises(m.Held):
                a.close_passive()
        self.assertTrue(fired)

    def test_unexpected_config_child_before_commit_holds(self):
        a = self.admission()
        self.commit()
        (self.config / 'foreign.json').write_text('{}')
        with self.assertRaises(m.Held):
            a.bind_committed()
if __name__ == '__main__':
    unittest.main()

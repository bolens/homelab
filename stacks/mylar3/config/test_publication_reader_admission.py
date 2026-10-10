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
from types import SimpleNamespace
from unittest.mock import patch

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
m = load('admission_fixture', str(_PORTABLE_ROOT / 'publication_reader_admission.py'))
assert Path(m.__file__).resolve() == _PORTABLE_ROOT / 'publication_reader_admission.py'
assert hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() == '32af3350a60a709fbd39d7c6b6b36d83e41186732c9b7998fd677b2a875d775f'
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

class FixtureLifecycle:

    def __init__(self, control, absent):
        self.control = control
        self.absent = absent
        self.files = {control: list(m.sig(control))}
        self.nodes = {p: list(v) for p, v in m.parents([control]).items()}

    def invocation_binding(self):
        return dict(input_path=str(self.control), input_sha256=hashlib.sha256(b'{}').hexdigest(), parent_sha256='b' * 64, provider_sha256='c' * 64, command=['fixture-provider'], nonce='a' * 64)

    def revalidate_stopped(self):
        pass

    def control_vectors(self):
        return (copy.deepcopy(self.files), copy.deepcopy(self.nodes), (self.absent,))

    def vectors(self):
        raise AssertionError('original live SQL vector is forbidden')

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
        self.lifecycle = FixtureLifecycle(self.control, self.root / 'absent-lifecycle-proof')
        self.life_patch = patch.object(m, 'installed_component', return_value=SimpleNamespace(StoppedReaderCustody=FixtureLifecycle))
        self.life_patch.start()
        self.addCleanup(self.life_patch.stop)
        self.context = m.CheckedChildInvocation(m._KEY, 'a' * 64, {self.control: m.sig(self.control)}, m.parents([self.control]), dict(reader_root=str(self.config), scratch=str(self.scratch), operation=str(self.operation), restore_root=str(self.restore), provider_input_path=str(self.control), provider_input_sha256=hashlib.sha256(b'{}').hexdigest(), parent_source_sha256='b' * 64, child_source_sha256='c' * 64, command=['fixture-provider']), lifecycle=self.lifecycle)
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

    def checked_provider_document(self):
        own = self.root / 'admission.py'
        own.write_text('fixture-admission-source')
        own.chmod(384)
        parent = self.root / 'parent.py'
        parent.write_text('fixture-parent-source')
        parent.chmod(384)
        life = self.root / 'lifecycle.py'
        life.write_text('fixture-lifecycle-source')
        life.chmod(384)
        h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
        provider = self.lifecycle.invocation_binding()
        provider['parent_sha256'] = h(parent)
        self.lifecycle.invocation_binding = lambda: copy.deepcopy(provider)
        ref = dict(path=str(self.control), sha256=h(self.control), signature9=list(m.sig(self.control)))
        roles = ('stopped_runtime', 'backup_ack', 'backup_manifest', 'backup_acceptance', 'rows', 'schema', 'reviewed_plan', 'timestamp_evidence', 'custody')
        document = dict(version=1, kind='owning-stopped-reader-selected-child', nonce='a' * 64, parent_source_sha256=h(parent), child_source_sha256=provider['provider_sha256'], admission_source_sha256=h(own), provider_input_path=provider['input_path'], provider_input_sha256=provider['input_sha256'], command=provider['command'], controls={r: ref for r in roles}, reader_root=str(self.config), scratch=str(self.scratch), operation=str(self.operation), restore_root=str(self.restore))
        path = self.root / 'invocation.json'
        path.write_bytes(m.encode(document))
        path.chmod(384)
        return (own, parent, life, path, document, h)

    def test_distinct_provider_input_and_admission_source_bound(self):
        own, parent, life, path, doc, h = self.checked_provider_document()
        with patch.object(m, '__file__', str(own)), patch.object(m, 'PARENT_SOURCE', parent), patch.object(m, 'PARENT_SHA', h(parent)), patch.object(m, 'LIFECYCLE_SOURCE', life), patch.object(m, 'LIFECYCLE_SHA', h(life)), patch.object(m, 'installed_code_read', side_effect=m.private_read):
            context = m.enter_checked_child(path, h(path), 'a' * 64, parent_sha=h(parent), source_sha=h(own), argv=doc['command'], lifecycle=self.lifecycle)
        self.assertNotEqual(str(path), context._provider['input_path'])
        self.assertNotEqual(doc['admission_source_sha256'], doc['child_source_sha256'])
        self.assertEqual(context.document, doc)

    def test_last_control_read_provider_rebinding_not_adopted(self):
        own, parent, life, path, doc, h = self.checked_provider_document()
        real = m.private_read
        fired = []

        def changed(p, expected):
            value = real(p, expected)
            if Path(p) == self.control and (not fired):
                previous = self.lifecycle.invocation_binding()
                previous['provider_sha256'] = 'e' * 64
                self.lifecycle.invocation_binding = lambda: copy.deepcopy(previous)
                fired.append(True)
            return value
        with patch.object(m, '__file__', str(own)), patch.object(m, 'PARENT_SOURCE', parent), patch.object(m, 'PARENT_SHA', h(parent)), patch.object(m, 'LIFECYCLE_SOURCE', life), patch.object(m, 'LIFECYCLE_SHA', h(life)), patch.object(m, 'installed_code_read', side_effect=real), patch.object(m, 'private_read', side_effect=changed):
            with self.assertRaisesRegex(m.Held, 'invocation-provider-admission-CAS'):
                m.enter_checked_child(path, h(path), 'a' * 64, parent_sha=h(parent), source_sha=h(own), argv=doc['command'], lifecycle=self.lifecycle)
        self.assertTrue(fired)

    def test_false_admission_as_provider_rejected(self):
        own, parent, life, path, doc, h = self.checked_provider_document()
        doc['child_source_sha256'] = h(own)
        path.write_bytes(m.encode(doc))
        with patch.object(m, '__file__', str(own)), patch.object(m, 'PARENT_SOURCE', parent), patch.object(m, 'PARENT_SHA', h(parent)), patch.object(m, 'LIFECYCLE_SOURCE', life), patch.object(m, 'LIFECYCLE_SHA', h(life)):
            with self.assertRaisesRegex(m.Held, 'owning-invocation-binding'):
                m.enter_checked_child(path, h(path), 'a' * 64, parent_sha=h(parent), source_sha=h(own), argv=doc['command'], lifecycle=self.lifecycle)

    def test_last_ancestor_check_change_never_returns(self):
        real = m.check
        count = []

        def changed(value, why):
            real(value, why)
            if why == 'invocation-ancestor':
                count.append(1)
                if len(count) == len(self.context._ancestors):
                    self.control.chmod(416)
        with patch.object(m, 'check', side_effect=changed):
            with self.assertRaisesRegex(m.Held, 'invocation-control-final'):
                self.context.close_passive()
        self.assertEqual(len(count), len(self.context._ancestors))

    def test_document_copy_change_checked_before_return(self):
        real = m.copy.deepcopy
        fired = []

        def changed(value, *args, **kwargs):
            result = real(value, *args, **kwargs)
            if value is self.context._document and (not fired):
                fired.append(True)
                self.control.chmod(416)
            return result
        with patch.object(m.copy, 'deepcopy', side_effect=changed):
            with self.assertRaises(m.Held):
                _value = self.context.document
        self.assertTrue(fired)

    def test_reader_last_ancestor_check_change_never_returns(self):
        admission = self.admission()
        real = m.check
        count = []
        nodes = set(admission._invocation._ancestors) | set(admission._coordinator._ancestors) | set(admission._nodes) | set(admission._native_nodes)

        def changed(value, why):
            real(value, why)
            if why == 'terminal-reader-ancestor':
                count.append(1)
                if len(count) == len(nodes):
                    (self.config / 'database.sqlite').chmod(416)
        with patch.object(m, 'check', side_effect=changed):
            with self.assertRaisesRegex(m.Held, 'terminal-reader-control-final'):
                admission.close_passive()
        self.assertEqual(len(count), len(nodes))

    def test_reader_binding_copy_change_checked_before_return(self):
        admission = self.admission()
        real = m.copy.deepcopy
        fired = []

        def changed(value, *args, **kwargs):
            result = real(value, *args, **kwargs)
            if value is admission._binding and (not fired):
                fired.append(True)
                (self.config / 'database.sqlite').chmod(416)
            return result
        with patch.object(m.copy, 'deepcopy', side_effect=changed):
            with self.assertRaises(m.Held):
                _value = admission.binding
        self.assertTrue(fired)

    def test_samebytes_additional_input_replacement_cannot_reseal_context(self):
        extra = self.root / 'additional-owning-role'
        extra.write_bytes(b'opaque immutable input')
        extra.chmod(384)
        context = m.CheckedChildInvocation(m._KEY, 'a' * 64, {**self.context._facts, extra: m.sig(extra)}, self.context._ancestors, self.context._document, lifecycle=self.lifecycle)
        replacement = self.root / 'replacement'
        shutil.copy2(extra, replacement)
        replacement.replace(extra)
        context._facts[extra] = m.sig(extra)
        context._seal = context._seal_value()
        with self.assertRaisesRegex(m.Held, 'invocation-lifetime'):
            context.close_passive()

    def test_parent_pipe_late_control_mutation_held(self):

        def changed():
            self.control.chmod(416)
        self.lifecycle.revalidate_stopped = changed
        with self.assertRaisesRegex(m.Held, 'invocation-control'):
            self.context.close_passive()

    def test_parent_pipe_late_absent_proof_creation_held(self):

        def changed():
            self.lifecycle.absent.write_bytes(b'foreign')
        self.lifecycle.revalidate_stopped = changed
        with self.assertRaisesRegex(m.Held, 'invocation-control'):
            self.context.close_passive()

    def test_provider_rebinding_held(self):
        real = self.lifecycle.invocation_binding

        def changed():
            value = real()
            value['provider_sha256'] = 'd' * 64
            return value
        self.lifecycle.invocation_binding = changed
        with self.assertRaisesRegex(m.Held, 'unchanged-owning-provider'):
            self.context.close_passive()

    def test_lifecycle_control_vector_reseal_held(self):

        def changed():
            self.control.chmod(416)
            self.lifecycle.files[self.control] = list(m.sig(self.control))
        self.lifecycle.revalidate_stopped = changed
        with self.assertRaisesRegex(m.Held, 'conflicting-control'):
            self.context.close_passive()

    def test_original_live_SQL_vectors_never_consulted(self):
        self.commit()
        self.context.close_passive()
        self.assertIn(self.lifecycle.absent, self.context._facts)
        self.assertIsNone(self.context._facts[self.lifecycle.absent])

    def test_boolean_lifecycle_not_owning_custody(self):
        with self.assertRaisesRegex(m.Held, 'exact-live-parent'):
            m.CheckedChildInvocation(m._KEY, 'a' * 64, {}, {}, {}, lifecycle=True)

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
            m.CheckedChildInvocation(None, 'a' * 64, {}, {}, {}, lifecycle=None)

    def test_nonce_not_generic_boolean(self):
        with self.assertRaises(m.Held):
            m.CheckedChildInvocation(m._KEY, True, {}, {}, {}, lifecycle=None)

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

    def test_mutable_original_pair_and_public_seal_cannot_reseal(self):
        a = self.admission()
        db = self.config / 'database.sqlite'
        db.chmod(416)
        a._pairs['database.sqlite'] = a._disk.pair(db)
        a._state_seal = a._state_value()
        with self.assertRaisesRegex(m.Held, 'reader-admission-lifetime'):
            a.revalidate()

    def test_samebytes_replacement_and_public_seal_cannot_reseal(self):
        a = self.admission()
        db = self.config / 'database.sqlite'
        raw = db.read_bytes()
        db.unlink()
        db.write_bytes(raw)
        db.chmod(384)
        a._pairs['database.sqlite'] = a._disk.pair(db)
        a._reader_directory = m.sig(self.config)
        a._state_seal = a._state_value()
        with self.assertRaisesRegex(m.Held, 'reader-admission-lifetime'):
            a.revalidate()

    def test_forged_before_state_cannot_enter_committed_factory(self):
        a = self.admission()
        a._root_names.add('foreign')
        a._state_seal = a._state_value()
        with self.assertRaisesRegex(m.Held, 'one-way-reader-phase'):
            a.bind_committed()

    def test_initial_lifetime_callback_cannot_reseal_original_invocation(self):
        extra = self.root / 'extra-owning-role'
        extra.write_bytes(b'original')
        extra.chmod(384)
        context = m.CheckedChildInvocation(m._KEY, 'a' * 64, {**self.context._facts, extra: m.sig(extra)}, self.context._ancestors, self.context._document, lifecycle=self.lifecycle)
        real = m.check
        fired = []

        def late(value, why):
            real(value, why)
            if why == 'invocation-lifetime' and (not fired):
                extra.chmod(416)
                context._facts[extra] = m.sig(extra)
                context._seal = context._seal_value()
                fired.append(True)
        with patch.object(m, 'check', side_effect=late), self.assertRaises(m.Held):
            context.close_passive()
        self.assertTrue(fired)
class GeometryControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.source=self.root/'source.cbz';self.correct=self.root/'proper.cbz';self.source.write_bytes(b'original');self.correct.write_bytes(b'original')
        self.pair={'wrong_url':'file:/reader/comics/wrong.cbz','correct_url':'file:/reader/comics/proper.cbz'}
        class Prep:
            def revalidate(inner):return {'source':str(self.source),'counterpart':str(self.correct),'files':{str(p):[list(m.sig(p)),hashlib.sha256(p.read_bytes()).hexdigest()] for p in (self.source,self.correct)}}
        self.prep=Prep()
        class Life:
            def native_url(inner,path):return self.pair['wrong_url'] if path==str(self.source) else self.pair['correct_url']
        self.life=Life()
    def test_native_host_reader_distinct_spelling_accepted(self):
        m.verify_reader_native_pair(self.life,self.prep,self.pair)
    def test_wrong_observed_stored_URI_refused(self):
        with self.assertRaisesRegex(ValueError,'path-correspondence'):m.verify_reader_native_pair(self.life,self.prep,dict(self.pair,wrong_url='file:/guessed/wrong.cbz'))
    def test_source_mode_changed_during_second_URL_observation_refused(self):
        real=self.life.native_url
        def changed(path):
            result=real(path)
            if path==str(self.correct):self.source.chmod(0o640)
            return result
        self.life.native_url=changed
        with self.assertRaisesRegex(ValueError,'after-URL-callbacks'):m.verify_reader_native_pair(self.life,self.prep,self.pair)
    def test_samebytes_inode_replaced_during_URL_refused(self):
        real=self.life.native_url
        def changed(path):
            result=real(path)
            if path==str(self.correct):raw=self.source.read_bytes();self.source.rename(self.root/'retained');self.source.write_bytes(raw)
            return result
        self.life.native_url=changed
        with self.assertRaisesRegex(ValueError,'after-URL-callbacks'):m.verify_reader_native_pair(self.life,self.prep,self.pair)
    def test_portable_source_pins_not_historical(self):
        raw=Path(m.__file__).read_text()
        self.assertIn('f165a0cb5834dc62f400d6dbe9e4070310823f28ec4bc1c4ecb12ae250503be3',raw)
        self.assertIn('ebac3228fa3c6055b86e3636fb33368f4ccf21950b452e7d6c10070af4a2c99a',raw)
        self.assertNotIn('b60ed13b2c1611a0712f6c902d3ae70999ad69be2460a10d4af0533c6733c2a2',raw)
        self.assertEqual(m.NEGATIVE_SHA,'85615fc4403982153adae10d2b72248f877e712f16329c16fdb2a2e6742d3d41')
        self.assertEqual(m.LIFECYCLE_SHA,'fb770bef4b1533fd3ad01e85a42d056c660a8e3e8b6f5a06458eacd43f8ca799')
        self.assertIsNone(m.PARENT_SHA)

if __name__ == '__main__':
    unittest.main()

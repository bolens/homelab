from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import os
'Disposable projection/transaction tests; no owning operational phase is minted.'
import copy
import inspect
import sqlite3
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
m = load('reader_phase_proposal', str(_PORTABLE_ROOT / 'publication_reader_phase.py'))
f = load('reader_admission_fixtures', str(_PORTABLE_ROOT / 'fixtures/test_comic_komga_stopped_reader_admission_v3.py'))

class PhaseTests(unittest.TestCase):

    def setUp(self):
        self.fixture = f.AdmissionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.admission = self.fixture.admission()
        self.phase = m.StoppedReaderPhase(m._KEY, self.admission)

    def test_stable_carried_before(self):
        self.phase.close_native_phase_passive(None)
        self.assertEqual(self.phase.phase, 'before')

    def test_public_factory_missing_package_holds(self):
        with self.assertRaises(m.Held):
            m.from_admission(self.admission)

    def test_no_boolean_factory(self):
        with self.assertRaises(m.Held):
            m.StoppedReaderPhase(True, self.admission)

    def test_original_core_reseal_holds(self):
        self.admission._core = 'f' * 64
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_phase_reseal_holds(self):
        self.phase.pairs = {}
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_phase_plan_mutation_holds(self):
        self.phase.plan['active_wrong_ids'] = []
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_source_control_replacement_holds(self):
        p = self.fixture.control
        raw = p.read_bytes()
        p.unlink()
        p.write_bytes(raw)
        p.chmod(384)
        with self.assertRaises(Exception):
            self.phase.close_native_phase_passive(None)

    def test_reader_pair_change_holds(self):
        self.fixture.commit()
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_sidecar_addition_holds(self):
        Path(str(self.fixture.config / 'tasks.sqlite') + '-journal').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_foreign_namespace_holds(self):
        (self.fixture.config / 'foreign').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)

    def test_staging_cannot_commit_without_aggregate(self):
        with self.assertRaisesRegex(m.Held, 'owning-publication_negative_batch_transition-not-installed'):
            self.phase.commit_staged({'staged': True})
        self.admission.revalidate()

    def test_committed_proof_cannot_be_boolean(self):
        with self.assertRaises(m.Held):
            self.phase.revalidate_committed(None)

    def test_sql_real_exact_five_delta_and_reverse(self):
        c = self.fixture.fixture.conn
        d = self.fixture.plan
        disk = f.d
        before = (disk.master(c), disk.k.snapshot(c), disk.book_rows(c, d))
        after = copy.deepcopy(before)
        after = (before[0], disk.k.snapshot(c, {bid: disk.k.row_decode(d['after_rows'][bid]) for bid in d['active_wrong_ids']}), d['after_rows'])
        c.execute('BEGIN')
        ack = m.sql_five_transition(c, disk, d, before, after)
        self.assertFalse(ack['commit_performed'])
        self.assertTrue(c.in_transaction)
        m.sql_five_transition(c, disk, d, before, after, rollback=True)
        self.assertEqual((disk.master(c), disk.k.snapshot(c), disk.book_rows(c, d)), before)
        c.rollback()

    def test_sql_foreign_correct_row_before_holds(self):
        c = self.fixture.fixture.conn
        disk = f.d
        plan = self.fixture.plan
        before = (disk.master(c), disk.k.snapshot(c), disk.book_rows(c, plan))
        c.execute('BEGIN')
        c.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
        with self.assertRaises(m.Held):
            m.sql_five_transition(c, disk, plan, before, before)
        c.rollback()

    def test_sql_no_transaction_holds(self):
        c = self.fixture.fixture.conn
        with self.assertRaises(m.Held):
            m.sql_five_transition(c, f.d, self.fixture.plan, self.phase.before['database.sqlite'], self.phase.after['database.sqlite'])

    def test_sql_injected_unexpected_delta_requires_caller_rollback(self):
        c = self.fixture.fixture.conn
        disk = f.d
        plan = copy.deepcopy(self.fixture.plan)
        before = (disk.master(c), disk.k.snapshot(c), disk.book_rows(c, plan))
        c.execute('BEGIN')
        plan['parameters'].append(plan['parameters'][0])
        with self.assertRaises(Exception):
            m.sql_five_transition(c, disk, plan, before, self.phase.after['database.sqlite'])
        c.rollback()
        self.assertEqual(disk.k.snapshot(c), before[1])

class SQLSuccessorTests(unittest.TestCase):
    setUp = PhaseTests.setUp

    def begin(self):
        sqlmodule = load('pending_SQL', str(_PORTABLE_ROOT / 'fixtures/publication_reader_sql_custody_v5.py'))

        class Reservation:
            pass
        reservation = Reservation()
        reservation.reader = self.phase
        reservation.batch = SimpleNamespace(preparations=self.phase.preparations)
        db = self.phase.root / 'database.sqlite'
        disk = self.phase.disk
        conn = disk.connect(db)
        self.addCleanup(conn.close)
        conn.execute('BEGIN IMMEDIATE')
        sql = sqlmodule.SQLWritingCustody(sqlmodule._KEY, conn, db, disk, self.phase.plan, self.phase.before['database.sqlite'], self.phase.after['database.sqlite'], self.phase.pairs['database.sqlite'])
        modules = {'mylar.publication_reader_sql_custody': SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_custody.py', SQLWritingCustody=sqlmodule.SQLWritingCustody), 'mylar.publication_negative_batch_transition': SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=Reservation)}
        with patch.object(m.importlib, 'import_module', side_effect=lambda name: modules[name]):
            self.phase.register_sql(sql, reservation)
        return (sql, reservation)

    def test_pending_real_five_body_carried_without_original_reseal(self):
        origin = (self.admission._core, self.admission._state_seal)
        sql, r = self.begin()
        sql.apply_body(m.sql_five_transition)
        self.phase.revalidate_sql_writing(sql, r)
        files, nodes = self.phase.sql_syscall_controls(sql, r)
        self.assertIn(Path(str(sql.db) + '-journal'), files)
        self.assertEqual(origin, (self.admission._core, self.admission._state_seal))
        self.assertEqual(sql.logical(), self.phase.after['database.sqlite'])
        sql.connection.rollback()

    def test_different_SQL_object_holds(self):
        sql, r = self.begin()
        with self.assertRaises(m.Held):
            self.phase.revalidate_sql_writing(object(), r)
        sql.connection.rollback()

    def test_other_tasks_drift_holds_with_pending_journal(self):
        sql, r = self.begin()
        sql.apply_body(m.sql_five_transition)
        (self.phase.root / 'tasks.sqlite').chmod(416)
        with self.assertRaises(Exception):
            self.phase.revalidate_sql_writing(sql, r)
        sql.connection.rollback()

    def test_public_SQL_pointer_reseal_holds(self):
        sql, r = self.begin()
        self.phase.sql = object()
        with self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)
        sql.connection.rollback()

    def test_commit_boolean_cannot_handoff(self):
        sql, r = self.begin()
        sql.apply_body(m.sql_five_transition)
        with self.assertRaises(Exception):
            self.phase.accept_committed({'committed': True})
        self.assertEqual(self.phase.phase, 'sql-writing')
        self.assertTrue(sql.connection.in_transaction)
        sql.connection.rollback()

    def test_original_before_revalidate_is_not_used_for_pending(self):
        sql, r = self.begin()
        sql.apply_body(m.sql_five_transition)
        with patch.object(type(self.admission), 'revalidate', side_effect=AssertionError('ordinary-before forbidden')):
            self.phase.revalidate_sql_writing(sql, r)
        sql.connection.rollback()

class OriginalRollbackTests(unittest.TestCase):
    setUp = SQLSuccessorTests.setUp
    begin = SQLSuccessorTests.begin

    def test_exact_owned_pending_rollback_carries_reader_only_terminal(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        sql.rollback_owned()
        self.phase.accept_uncommitted_rollback(sql, reservation)
        reservation.projection = SimpleNamespace(phases=['source'] * 5)
        module = SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=type(reservation))
        with patch.object(m.importlib, 'import_module', return_value=module):
            binding = self.phase.original_rollback_binding(reservation)
        self.assertEqual(binding['phase'], 'rolled-back')
        self.assertFalse(binding['publication_acceptance'])

    def test_pending_SQL_cannot_claim_original_rollback_terminal(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        reservation.projection = SimpleNamespace(phases=['source'] * 5)
        module = SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=type(reservation))
        with patch.object(m.importlib, 'import_module', return_value=module):
            with self.assertRaises(m.Held):
                self.phase.close_original_rollback(reservation)
        sql.connection.rollback()

    def test_linked_projection_cannot_claim_original_terminal(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        sql.rollback_owned()
        self.phase.accept_uncommitted_rollback(sql, reservation)
        reservation.projection = SimpleNamespace(phases=['linked'] * 5)
        module = SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=type(reservation))
        with patch.object(m.importlib, 'import_module', return_value=module):
            with self.assertRaises(m.Held):
                self.phase.close_original_rollback(reservation)

class BeforeAbsenceTests(unittest.TestCase):
    setUp = PhaseTests.setUp

    def test_original_rollback_vectors_include_all_absent_companions(self):
        files, nodes = self.phase.native_syscall_controls(None)
        for base in (self.phase.root, self.phase.restore):
            for name in self.phase.pairs:
                for suffix in ('-wal', '-shm', '-journal'):
                    p = Path(str(base / name) + suffix)
                    self.assertIn(p, files)
                    self.assertIsNone(files[p])

class WALPhaseTests(unittest.TestCase):

    def setUp(self):
        self.fixture = f.AdmissionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        db = self.fixture.config / 'database.sqlite'
        c = sqlite3.connect(db)
        c.execute('PRAGMA journal_mode=WAL')
        c.close()
        self.admission = self.fixture.admission()
        self.reader = m.StoppedReaderPhase(m._KEY, self.admission)
        self.w = load('wal_reader_fixture', str(_PORTABLE_ROOT / 'publication_reader_wal_phase.py'))
        self.lower = load('wal_reader_lower', str(_PORTABLE_ROOT / 'publication_reader_sql_custody.py'))

        class Reservation:

            def revalidate_staged(s, reader, preparations):
                if reader is not s.reader or preparations != s.batch.preparations:
                    raise m.Held('fixture-staged')

            def close_native_precommit(s, reader):
                pass

            def native_sql_controls(s, reader):
                return ({}, {})
        self.native = Reservation()
        self.native.reader = self.reader
        self.native.core = 'n'
        self.native.batch = SimpleNamespace(preparations=self.reader.preparations)
        self.modules = {'publication_reader_wal_phase': SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_wal_phase.py', WALReaderPhase=self.w.WALReaderPhase), 'publication_negative_batch_transition': SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=Reservation)}
        self.patch = patch.object(m.importlib, 'import_module', side_effect=lambda n: self.modules[n.removeprefix('mylar.')])
        self.patch.start()
        self.addCleanup(self.patch.stop)
        start = SimpleNamespace(reader=self.reader, reservation=self.native, core='s', _life=lambda: None, _direct=lambda _: self.reader.validate_sql_start(self.native))
        self.wal = self.w.WALReaderPhase(self.w._KEY, start, self.lower)
        self.wal.open_begin()
        self.addCleanup(self.wal.connection.close)

    def test_real_typed_WAL_pair_successor_original_seal_unchanged(self):
        original = copy.deepcopy(self.admission._pairs)
        core = self.admission._core
        self.reader.accept_wal_begin(self.wal, self.native)
        self.assertIs(self.reader.wal_phase, self.wal)
        self.assertEqual(self.reader.pairs['database.sqlite'], self.wal.current)
        self.assertEqual(self.admission._pairs, original)
        self.assertEqual(self.admission._core, core)
        self.reader.close_native_phase_passive(None)

    def test_exact_WAL_reverse_baseline_readmark_successor(self):
        self.reader.accept_wal_begin(self.wal, self.native)
        sql = self.lower.from_wal_begin(self.wal, self.reader.disk, self.reader.plan, self.reader.before['database.sqlite'], self.reader.after['database.sqlite'])
        self.modules['publication_reader_sql_custody'] = SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_custody.py', SQLWritingCustody=self.lower.SQLWritingCustody)
        self.reader.register_sql(sql, self.native)
        sql.apply_body(m.sql_five_transition)
        sql.connection.commit()

        class Commit:

            def _life(s):
                pass

            def _close_observed(s, *a):
                if self.lower.raw_pair(sql.db) != s.current:
                    raise m.Held('fixture-committed-pair')

            def close_committed_for_reverse_open(s, *a):
                s._close_observed()
        c = Commit()
        c.reader = self.reader
        c.reservation = self.native
        c.sql = c.sql_custody = sql
        c.core = 'fixture-commit-core'
        c.before = self.reader.before['database.sqlite']
        c.after = self.reader.after['database.sqlite']
        c.tasks_pair = self.reader.tasks_pair
        c.current = self.lower.raw_pair(sql.db)
        c.directory = self.w.nine(os.lstat(self.reader.root))
        c.phase = 'committed'
        self.modules['publication_reader_sql_commit'] = SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_commit.py', ReaderSQLCommit=Commit)
        self.wal.accept_committed_pair(c)
        self.reader.commit_custody = c
        self.reader.commit_core = c.core
        self.reader.phase = 'committed'
        self.reader._seal()
        c.phase = 'reverse-uncertain'
        c.records = {self.fixture.root / 'reverse-intent.json': {}}
        self.wal.begin_reverse(c)
        reverse = self.lower.from_wal_begin(self.wal, self.reader.disk, self.reader.plan, c.after, c.before)
        self.addCleanup(lambda: reverse.connection.rollback() if reverse.connection.in_transaction else None)
        reverse.apply_body(lambda conn, disk, plan, before, after: m.sql_five_transition(conn, disk, plan, after, before, rollback=True))
        self.reader.revalidate_sql_reversing(c, reverse, self.native)
        self.assertEqual(reverse.baseline, self.wal.current)
        self.assertEqual(reverse.logical(), c.before)
        self.assertEqual(self.reader.original._pairs['database.sqlite'], self.wal.original)

    def test_WAL_successor_cannot_be_boolean(self):
        with self.assertRaises(m.Held):
            self.reader.accept_wal_begin(True, self.native)

    def test_second_WAL_handoff_denied(self):
        self.reader.accept_wal_begin(self.wal, self.native)
        with self.assertRaisesRegex(m.Held, 'one-exact-owned'):
            self.reader.accept_wal_begin(self.wal, self.native)

    def test_last_logical_callback_tasks_drift_does_not_adopt(self):
        real = self.admission._observe

        def changed(admission):
            value = real()
            (self.fixture.config / 'tasks.sqlite').chmod(416)
            return value
        with patch.object(type(self.admission), '_observe', new=changed):
            with self.assertRaises(self.w.Held):
                self.reader.accept_wal_begin(self.wal, self.native)
        self.assertIsNone(self.reader.wal_phase)

class TerminalClosureTests(unittest.TestCase):
    setUp = PhaseTests.setUp
    begin = SQLSuccessorTests.begin

    def late_check(self, reason, method, change):
        real = m.check
        count = [0]
        fired = []

        def late(value, why):
            real(value, why)
            if why == reason and inspect.stack()[1].function == method:
                count[0] += 1
                if count[0] == len(self.phase._vectors()[1]):
                    fired.append(True)
                    change()
        return (late, fired)

    def test_literal_last_before_ancestor_callback_changes_earlier_main_held(self):
        late, fired = self.late_check('reader-phase-ancestor', 'close_native_phase_passive', lambda: (self.phase.root / 'database.sqlite').chmod(416))
        with patch.object(m, 'check', late), self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)
        self.assertTrue(fired)

    def test_last_before_ancestor_callback_creates_declared_absence_held(self):
        missing = Path(str(self.phase.tasks_database) + '-journal')
        late, fired = self.late_check('reader-phase-ancestor', 'close_native_phase_passive', lambda: missing.write_bytes(b'foreign'))
        with patch.object(m, 'check', late), self.assertRaises(m.Held):
            self.phase.close_native_phase_passive(None)
        self.assertTrue(fired)

    def test_actual_pending_SQL_last_ancestor_callback_held_before_handoff(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        late, fired = self.late_check('reader-SQL-terminal-ancestor', '_sql_passive', lambda: (self.phase.root / 'database.sqlite').chmod(416))
        with patch.object(m, 'check', late), self.assertRaises(m.Held):
            self.phase._sql_passive()
        self.assertTrue(fired)
        self.assertTrue(sql.connection.in_transaction)
        sql.connection.rollback()

    def test_last_stable_ancestor_callback_changes_tasks_held(self):
        late, fired = self.late_check('stable-reader-SQL-ancestor', '_stable_vectors_direct', lambda: self.phase.tasks_database.chmod(416))
        with patch.object(m, 'check', late), self.assertRaises(m.Held):
            self.phase._stable_vectors_direct()
        self.assertTrue(fired)

    def test_native_return_vector_supplier_callback_held(self):
        real = self.phase._vectors
        fired = []

        def late():
            value = real()
            if inspect.stack()[1].function == 'native_syscall_controls' and (not fired):
                fired.append(True)
                (self.phase.root / 'database.sqlite').chmod(416)
            return value
        with patch.object(self.phase, '_vectors', late), self.assertRaises(m.Held):
            self.phase.native_syscall_controls(None)
        self.assertTrue(fired)

    def test_SQL_return_vector_supplier_callback_held(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        real = self.phase._sql_vectors
        fired = []

        def late():
            value = real()
            if inspect.stack()[1].function == 'sql_syscall_controls' and (not fired):
                fired.append(True)
                self.phase.tasks_database.chmod(416)
            return value
        with patch.object(self.phase, '_sql_vectors', late), self.assertRaisesRegex(ValueError, 'pending-SQL-other-file|reader-inline-file'):
            self.phase.sql_syscall_controls(sql, reservation)
        self.assertTrue(fired)
        self.assertTrue(sql.connection.in_transaction)
        sql.connection.rollback()

    def rollback(self):
        sql, reservation = self.begin()
        sql.apply_body(m.sql_five_transition)
        sql.rollback_owned()
        self.phase.accept_uncommitted_rollback(sql, reservation)
        reservation.projection = SimpleNamespace(phases=['source'] * 5)
        module = SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=type(reservation))
        return (sql, reservation, module)

    def test_original_rollback_last_vector_copy_callback_held(self):
        sql, reservation, module = self.rollback()
        real = m.copy.deepcopy
        fired = []

        def late(value, *args, **kwargs):
            result = real(value, *args, **kwargs)
            if inspect.stack()[1].function == 'close_original_rollback' and (not fired):
                fired.append(True)
                self.phase.tasks_database.chmod(416)
            return result
        with patch.object(m.importlib, 'import_module', return_value=module), patch.object(m.copy, 'deepcopy', late), self.assertRaisesRegex(ValueError, 'reader-phase-file|pending-SQL-other-file|reader-inline-file|original-rollback-reader-all-tables'):
            self.phase.close_original_rollback(reservation)
        self.assertTrue(fired)
        self.assertFalse(sql.connection.in_transaction)

    def test_original_rollback_binding_copy_callback_held(self):
        sql, reservation, module = self.rollback()
        real = m.copy.deepcopy
        fired = []

        def late(value, *args, **kwargs):
            result = real(value, *args, **kwargs)
            if inspect.stack()[1].function == 'original_rollback_binding' and (not fired):
                fired.append(True)
                self.phase.tasks_database.chmod(416)
            return result
        with patch.object(m.importlib, 'import_module', return_value=module), patch.object(m.copy, 'deepcopy', late), self.assertRaisesRegex(ValueError, 'reader-phase-file|pending-SQL-other-file|reader-inline-file|original-rollback-reader-all-tables'):
            self.phase.original_rollback_binding(reservation)
        self.assertTrue(fired)
        self.assertFalse(sql.connection.in_transaction)
if __name__ == '__main__':
    unittest.main()

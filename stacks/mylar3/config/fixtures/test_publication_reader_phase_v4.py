"""Disposable projection/transaction tests; no owning operational phase is minted."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
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
m = load('reader_phase_proposal', str(_PORTABLE_ROOT / 'fixtures/publication_reader_phase_v4.py'))
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
if __name__ == '__main__':
    unittest.main()

"""Actual local SQLite own journal and exact5 transition; no operational grant."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import inspect
import os
import sqlite3
from types import SimpleNamespace
from pathlib import Path
import unittest
from unittest.mock import patch

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
m = load('sql_custody', str(_PORTABLE_ROOT / 'publication_reader_sql_custody.py'))
f = load('admission_fixture', str(_PORTABLE_ROOT / 'fixtures/test_comic_komga_stopped_reader_admission_v3.py'))
r = load('reader_phase', str(_PORTABLE_ROOT / 'fixtures/publication_reader_phase_v1.py'))

class Tests(unittest.TestCase):

    def setUp(self):
        self.c = f.AdmissionTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.a = self.c.admission()
        self.db = self.c.config / 'database.sqlite'
        self.disk = f.d
        self.before = self.a._observed['database.sqlite']
        self.after = self.a._expected['database.sqlite']
        self.baseline = m.raw_pair(self.db)
        self.conn = self.disk.connect(self.db)
        self.addCleanup(self.conn.close)
        self.conn.execute('BEGIN IMMEDIATE')

    def make(self):
        return m.SQLWritingCustody(m._KEY, self.conn, self.db, self.disk, self.c.plan, self.before, self.after, self.baseline)

    def test_genuine_delete_journal_owned_after_exact_five_body(self):
        x = self.make()
        ack = x.apply_body(r.sql_five_transition)
        x.close_pending()
        self.assertFalse(ack['commit_performed'])
        self.assertTrue(self.conn.in_transaction)
        self.assertIn('-journal', x.pending)

    def test_owned_rollback_keeps_all_original_values(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        x.rollback_owned()
        self.assertEqual(x.logical(), self.before)

    def test_no_public_commit_grant(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        with self.assertRaisesRegex(m.Held, 'handshake'):
            x.commit()
        self.assertTrue(self.conn.in_transaction)

    def test_private_key_no_boolean(self):
        with self.assertRaises(m.Held):
            m.SQLWritingCustody(True, self.conn, self.db, self.disk, self.c.plan, self.before, self.after, self.baseline)

    def test_foreign_correct_row_after_body_holds(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        self.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
        with self.assertRaises(m.Held):
            x.close_pending()

    def test_pending_pair_reseal_holds(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        x.pending = {}
        with self.assertRaises(m.Held):
            x.close_pending()

    def test_late_logical_callback_other_file_change_holds(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = x.logical

        def changed():
            v = real()
            (self.c.config / 'foreign').write_bytes(b'foreign')
            return v
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.close_pending()

    def test_late_logical_callback_journal_change_holds(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = x.logical

        def changed():
            v = real()
            Path(str(self.db) + '-journal').write_bytes(b'foreign')
            return v
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.close_pending()

    def test_unowned_hot_journal_reader_holds(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        with self.assertRaisesRegex(m.Held, 'unowned-reader-journal'):
            m.raw_pair(self.db)

    def test_changed_mode_before_body_never_calls_SQL(self):
        x = self.make()
        self.db.chmod(416)
        fired = False

        def body(*a):
            nonlocal fired
            fired = True
            return r.sql_five_transition(*a)
        with self.assertRaises(m.Held):
            x.apply_body(body)
        self.assertFalse(fired)
        self.assertEqual(x.logical(), self.before)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_samebytes_replacement_before_body_never_calls_SQL(self):
        x = self.make()
        saved = self.db.read_bytes()
        self.db.rename(self.db.with_suffix('.retained'))
        self.db.write_bytes(saved)
        self.db.chmod(384)
        fired = False

        def body(*a):
            nonlocal fired
            fired = True
            return r.sql_five_transition(*a)
        with self.assertRaises(m.Held):
            x.apply_body(body)
        self.assertFalse(fired)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_foreign_namespace_before_body_never_calls_SQL(self):
        x = self.make()
        (self.c.config / 'foreign').write_bytes(b'foreign')
        fired = False

        def body(*a):
            nonlocal fired
            fired = True
            return r.sql_five_transition(*a)
        with self.assertRaises(m.Held):
            x.apply_body(body)
        self.assertFalse(fired)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_last_preflight_logical_callback_mode_drift_no_SQL(self):
        x = self.make()
        real = x.logical
        fired = False

        def changed():
            v = real()
            self.db.chmod(416)
            return v

        def body(*a):
            nonlocal fired
            fired = True
            return r.sql_five_transition(*a)
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.apply_body(body)
        self.assertFalse(fired)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_final_rollback_logical_mode_drift_no_ACK(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = x.logical
        calls = 0
        fired = False

        def changed():
            nonlocal calls, fired
            value = real()
            calls += 1
            if calls == 2:
                self.db.chmod(416)
                fired = True
            return value
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.rollback_owned()
        self.assertTrue(fired)

    def test_final_rollback_logical_foreign_child_no_ACK(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = x.logical
        calls = 0
        fired = False

        def changed():
            nonlocal calls, fired
            value = real()
            calls += 1
            if calls == 2:
                (self.c.config / 'foreign').write_bytes(b'foreign')
                fired = True
            return value
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.rollback_owned()
        self.assertTrue(fired)

    def test_final_rollback_logical_sql_write_no_ACK(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = x.logical
        calls = 0
        fired = False

        def changed():
            nonlocal calls, fired
            value = real()
            calls += 1
            if calls == 2:
                self.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
                fired = True
            return value
        with patch.object(x, 'logical', side_effect=changed):
            with self.assertRaises(m.Held):
                x.rollback_owned()
        self.assertTrue(fired)

    def test_real_disk_pair_contract_compatible(self):
        self.baseline = self.disk.pair(self.db)
        x = self.make()
        x.apply_body(r.sql_five_transition)
        x.close_pending()
        self.assertEqual(x.pending['']['xattrs'], self.baseline['']['xattrs'])

    def test_original_xattrs_before_body_drift_no_SQL(self):
        x = self.make()
        __import__('os').setxattr(self.db, 'user.custody', b'foreign')
        fired = False

        def body(*a):
            nonlocal fired
            fired = True
            return r.sql_five_transition(*a)
        with self.assertRaises(m.Held):
            x.apply_body(body)
        self.assertFalse(fired)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_last_missing_journal_callback_mode_drift_no_SQL(self):
        x = self.make()
        real = m.signature
        fired = False
        body_called = False

        def changed(p):
            nonlocal fired
            try:
                return real(p)
            except FileNotFoundError:
                if str(p) == str(self.db) + '-journal' and inspect.currentframe().f_back.f_code.co_name == '_close_before_write':
                    self.db.chmod(416)
                    fired = True
                raise

        def body(*a):
            nonlocal body_called
            body_called = True
            return r.sql_five_transition(*a)
        with patch.object(m, 'signature', new=changed):
            with self.assertRaises(m.Held):
                x.apply_body(body)
        self.assertTrue(fired)
        self.assertFalse(body_called)
        self.assertFalse(Path(str(self.db) + '-journal').exists())

    def test_last_rollback_missing_journal_callback_mode_drift_no_ACK(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        real = m.signature
        fired = False

        def changed(p):
            nonlocal fired
            try:
                return real(p)
            except FileNotFoundError:
                if str(p) == str(self.db) + '-journal' and inspect.currentframe().f_back.f_code.co_name == 'close_passive':
                    self.db.chmod(416)
                    fired = True
                raise
        with patch.object(m, 'signature', new=changed):
            with self.assertRaises(m.Held):
                x.rollback_owned()
        self.assertTrue(fired)

    def test_different_database_connection_held(self):
        with self.assertRaises(m.Held):
            m.SQLWritingCustody(m._KEY, self.conn, self.c.config / 'tasks.sqlite', self.disk, self.c.plan, self.before, self.after, self.baseline)

class WALTests(unittest.TestCase):

    def setUp(self):
        self.c = f.AdmissionTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        a = self.c.admission()
        self.before = a._observed['database.sqlite']
        self.after = a._expected['database.sqlite']
        self.db = self.c.config / 'database.sqlite'
        self.disk = f.d
        connection = sqlite3.connect(self.db)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.close()
        self.original = m.raw_pair(self.db)
        self.w = load('wal_for_custody', str(_PORTABLE_ROOT / 'fixtures/publication_reader_wal_phase_v3.py'))
        self.reader = SimpleNamespace(root=self.c.config, pairs={'database.sqlite': self.original}, names=set(os.listdir(self.c.config)), core='r', disk=self.disk, plan=self.c.plan, scratch=self.c.scratch)
        self.reader.native_syscall_controls = lambda _: ({self.c.control: self.w.nine(os.lstat(self.c.control)), self.c.config / 'tasks.sqlite': self.w.nine(os.lstat(self.c.config / 'tasks.sqlite'))}, {})

        def before(_=None):
            if m.raw_pair(self.db) != self.original:
                raise m.Held('fixture-WAL-preimage')
        self.reader.validate_sql_start = before
        self.native = SimpleNamespace(core='n', close_native_precommit=lambda _: None, native_sql_controls=lambda _: ({}, {}))
        start = SimpleNamespace(reader=self.reader, reservation=self.native, core='s', _life=lambda: None, _direct=lambda _: before())
        self.wal = self.w.WALReaderPhase(self.w._KEY, start, m)
        self.wal.open_begin()
        self.addCleanup(self.wal.connection.close)

    def make(self, before=None, after=None):
        with patch.object(m, 'installed_wal', return_value=SimpleNamespace(WALReaderPhase=self.w.WALReaderPhase)):
            return m.from_wal_begin(self.wal, self.disk, self.c.plan, before or self.before, after or self.after)

    def test_real_WAL_body_exact_all_tables_before_COMMIT(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        x.close_pending()
        self.assertEqual(x.logical(), self.after)
        self.assertTrue(x.connection.in_transaction)
        self.assertEqual(x.mode, 'wal')

    def reverse_begin(self, x):
        x.connection.commit()

        class Commit:

            def close_committed_for_reverse_open(self, native):
                if m.raw_pair(self.sql.db) != self.current:
                    raise m.Held('fixture-reverse-pair')
        c = Commit()
        c.sql = x
        c.reader = self.reader
        c.reservation = self.native
        c.phase = 'reverse-uncertain'
        c.current = m.raw_pair(self.db)
        c.directory = self.w.nine(os.lstat(self.c.config))
        c.records = {self.c.root / 'reverse-intent.json': {}}
        with patch.object(self.w, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            self.wal.begin_reverse(c)

    def test_same_connection_empty_TEMP_typed_reverse_exact_five(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        self.reverse_begin(x)
        self.assertIn('temp', [row[1] for row in x.connection.execute('PRAGMA database_list')])
        reverse = self.make(self.after, self.before)
        reverse.apply_body(lambda con, disk, plan, *_: r.sql_five_transition(con, disk, plan, self.before, self.after, rollback=True))
        reverse.close_pending()
        self.assertEqual(reverse.logical(), self.before)
        self.assertIs(reverse.connection, x.connection)

    def test_empty_TEMP_without_typed_WAL_phase_still_held(self):
        x = self.make()
        x.apply_body(r.sql_five_transition)
        self.reverse_begin(x)
        with self.assertRaisesRegex(m.Held, 'sole-owned-main'):
            m.SQLWritingCustody(m._KEY, x.connection, self.db, self.disk, self.c.plan, self.after, self.before, self.wal.current)

    def test_nonempty_TEMP_denied_even_with_typed_WAL_phase(self):
        self.wal.connection.execute('CREATE TEMP TABLE foreign_temp(x)')
        with self.assertRaisesRegex(m.Held, 'sole-owned-main'):
            self.make()

    def test_attached_database_denied_even_with_typed_WAL_phase(self):
        self.wal.connection.execute("ATTACH ':memory:' AS foreign_db")
        with self.assertRaisesRegex(m.Held, 'sole-owned-main'):
            self.make()

    def test_foreign_boolean_phase_never_reaches_constructor(self):
        with patch.object(m, 'installed_wal', return_value=SimpleNamespace(WALReaderPhase=self.w.WALReaderPhase)):
            with self.assertRaisesRegex(m.Held, 'exact-owning-WAL-BEGIN-type'):
                m.from_wal_begin(True, self.disk, self.c.plan, self.before, self.after)

    def test_changed_owned_phase_pair_cannot_reseal(self):
        self.wal.current['']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(self.w.Held, 'immutable-owning-WAL-phase'):
            self.make()

    def test_last_constructor_signature_cannot_adopt_changed_tasks(self):
        real = m.signature
        fired = []

        def changed(path):
            value = real(path)
            if Path(path) == self.db.parent and (not fired):
                (self.c.config / 'tasks.sqlite').chmod(416)
                fired.append(True)
            return value
        with patch.object(m, 'signature', new=changed):
            with self.assertRaises(self.w.Held):
                self.make()
        self.assertTrue(fired)
        self.assertTrue(self.wal.connection.in_transaction)

    def test_changed_main_mode_after_BEGIN_before_constructor_held(self):
        self.db.chmod(416)
        with self.assertRaisesRegex(m.Held, 'initial-owned-reader-pair-CAS'):
            self.make()
if __name__ == '__main__':
    unittest.main()

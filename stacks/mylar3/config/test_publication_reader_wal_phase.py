"""Real disposable WAL transitions; fake native/installed boundary explicit."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import inspect
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
m = load('wal_phase', str(_PORTABLE_ROOT / 'publication_reader_wal_phase.py'))
custody = load('custody', str(_PORTABLE_ROOT / 'fixtures/publication_reader_sql_custody_v5.py'))

class Disk:

    def connect(self, db):
        return sqlite3.connect('file:' + str(db) + '?mode=rw', uri=True, timeout=0)

    def observe_copy(self, db, plan, scratch):
        raw = Path(db).read_bytes()
        copy = scratch / 'observe.sqlite'
        copy.write_bytes(raw)
        c = sqlite3.connect('file:' + str(copy) + '?mode=ro&immutable=1', uri=True)
        try:
            return tuple(c.execute('SELECT x FROM t ORDER BY x'))
        finally:
            c.close()
            copy.unlink()

class Commit:

    def _life(self):
        pass

    def close_committed_for_reverse_open(self, native):
        if custody.raw_pair(self.sql.db) != self.current:
            raise m.Held('fixture-commit-pair')

    def _close_observed(self, *args):
        if custody.raw_pair(self.sql.db) != self.current:
            raise m.Held('fixture-commit-pair')

class Tests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(448)
        self.readerroot = self.root / 'reader'
        self.readerroot.mkdir(mode=448)
        self.db = self.readerroot / 'database.sqlite'
        c = sqlite3.connect(self.db)
        c.execute('CREATE TABLE t(x)')
        c.execute('INSERT INTO t VALUES(1)')
        c.commit()
        c.execute('PRAGMA journal_mode=WAL')
        c.close()
        self.db.chmod(384)
        self.tasks = self.readerroot / 'tasks.sqlite'
        self.tasks.write_bytes(b'opaque fixture')
        self.tasks.chmod(384)
        self.control = self.root / 'control'
        self.control.write_bytes(b'fixture')
        self.control.chmod(384)
        self.scratch = self.root / 'scratch'
        self.scratch.mkdir(mode=448)
        self.baseline = custody.raw_pair(self.db)
        self.names = set(os.listdir(self.readerroot))
        self.control9 = m.nine(os.lstat(self.control))
        reader = SimpleNamespace(root=self.readerroot, pairs={'database.sqlite': self.baseline}, names=self.names, core='r', disk=Disk(), plan={}, scratch=self.scratch)
        reader.native_syscall_controls = lambda _: ({self.control: self.control9, self.tasks: m.nine(os.lstat(self.tasks))}, {})
        reader.validate_sql_start = lambda _: self.before()
        self.native = SimpleNamespace(core='n', close_native_precommit=lambda _: None, native_sql_controls=lambda _: ({}, {}))
        self.start = SimpleNamespace(reader=reader, reservation=self.native, core='s', _life=lambda: None)
        self.start._direct = lambda _: self.before()

    def before(self):
        if custody.raw_pair(self.db) != self.baseline:
            raise m.Held('fixture-original-pair')

    def make(self):
        return m.WALReaderPhase(m._KEY, self.start, custody)

    def opening(self):
        x = self.make()
        x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        return x

    def safe_close(self, x):
        if x.connection is not None:
            try:
                x.connection.close()
            except sqlite3.Error:
                pass

    def commit(self, x):
        x.connection.execute('UPDATE t SET x=2')
        x.connection.commit()
        c = Commit()
        c.sql = SimpleNamespace(connection=x.connection, db=self.db)
        c.reader = x.reader
        c.reservation = self.native
        c.current = custody.raw_pair(self.db)
        c.directory = m.nine(os.lstat(self.readerroot))
        c.records = {self.root / 'reverse-intent.json': {}, self.root / 'connection-close-intent.json': {}}
        c.phase = 'committed'
        c.after = ((2,),)
        c.before = ((1,),)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            x.accept_committed_pair(c)
        return c

    def with_ancestor(self):
        real = self.start.reader.native_syscall_controls
        self.start.reader.native_syscall_controls = lambda f: (real(f)[0], {self.root: m.five(os.lstat(self.root))})

    def test_last_ancestor_before_BEGIN_changed_main_holds_before_BEGIN(self):
        self.with_ancestor()
        x = self.make()
        real = m.five
        calls = 0
        fired = []

        def change(z):
            nonlocal calls
            result = real(z)
            if inspect.currentframe().f_back.f_code.co_name == '_direct':
                calls += 1
            if calls == 2:
                self.db.chmod(416)
                fired.append(True)
            return result
        with patch.object(m, 'five', new=change):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file-final'):
                x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        self.assertTrue(fired)
        self.assertFalse(x.connection.in_transaction)

    def test_last_ancestor_before_reverse_BEGIN_holds_before_BEGIN(self):
        self.with_ancestor()
        x = self.opening()
        c = self.commit(x)
        c.phase = 'reverse-uncertain'
        real = m.five
        calls = 0
        fired = []

        def change(z):
            nonlocal calls
            result = real(z)
            if inspect.currentframe().f_back.f_code.co_name == '_direct':
                calls += 1
            if calls == 2:
                self.db.chmod(416)
                fired.append(True)
            return result
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)), patch.object(m, 'five', new=change):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file-final'):
                x.begin_reverse(c)
        self.assertTrue(fired)
        self.assertFalse(x.connection.in_transaction)

    def test_last_ancestor_before_close_holds_without_closing_connection(self):
        self.with_ancestor()
        x = self.opening()
        c = self.commit(x)
        real = m.five
        calls = 0
        fired = []

        def change(z):
            nonlocal calls
            result = real(z)
            if inspect.currentframe().f_back.f_code.co_name == '_direct':
                calls += 1
            if calls == 2:
                self.db.chmod(416)
                fired.append(True)
            return result
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)), patch.object(m, 'five', new=change):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file-final'):
                x.close_connection(c)
        self.assertTrue(fired)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(2,)])
        self.assertTrue(Path(str(self.db) + '-wal').exists())

    def test_lifetime_callback_cannot_adopt_changed_control_vector(self):
        x = self.make()
        real = x._life
        fired = []

        def change():
            real()
            if x.phase == 'BEGIN-uncertain' and (not fired):
                self.control.chmod(416)
                x.files[self.control] = m.nine(os.lstat(self.control))
                fired.append(True)
        x._life = change
        with self.assertRaisesRegex(m.Held, 'terminal-WAL-file'):
            x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        self.assertTrue(fired)
        self.assertFalse(x.connection.in_transaction)

    def test_lifetime_callback_cannot_adopt_mutated_native_argument(self):
        x = self.make()
        p = self.root / 'native-only'
        p.write_bytes(b'fixture')
        p.chmod(384)
        native = {p: m.nine(os.lstat(p))}
        real = x._life
        fired = []

        def changed():
            real()
            p.chmod(416)
            native[p] = m.nine(os.lstat(p))
            fired.append(True)
        x._life = changed
        with self.assertRaisesRegex(m.Held, 'terminal-WAL-file'):
            x._direct(self.baseline, m.nine(os.lstat(self.readerroot)), ((native, {}),))
        self.assertTrue(fired)

    def test_real_WAL_open_and_BEGIN_no_SQL_changes(self):
        x = self.opening()
        self.assertTrue(x.connection.in_transaction)
        self.assertEqual(x.phase, 'begun')
        self.assertEqual(x.current[''], self.baseline[''])
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(1,)])

    def test_same_connection_reverse_begin_readmark_and_reverse(self):
        x = self.opening()
        c = self.commit(x)
        c.phase = 'reverse-uncertain'
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            x.begin_reverse(c)
        self.assertEqual(x.phase, 'reverse-begun')
        self.assertIs(x.connection, c.sql.connection)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(2,)])
        x.connection.execute('UPDATE t SET x=1')
        x.connection.commit()
        c.current = custody.raw_pair(self.db)
        c.directory = m.nine(os.lstat(self.readerroot))
        c.phase = 'reversed'
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            x.accept_committed_pair(c)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            x.close_connection(c)
        self.assertEqual(x.phase, 'closed')
        self.assertEqual(set(x.current), {''})
        self.assertEqual(x.reader.disk.observe_copy(self.db, {}, self.scratch), ((1,),))

    def test_forward_last_close_checkpoints_before_terminal(self):
        x = self.opening()
        c = self.commit(x)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            x.close_connection(c)
        self.assertEqual(x.phase, 'closed')
        self.assertEqual(set(custody.raw_pair(self.db)), {''})
        self.assertEqual(x.reader.disk.observe_copy(self.db, {}, self.scratch), ((2,),))

    def test_foreign_connection_object_refused_before_mode_query(self):
        x = self.make()
        x.reader.disk.connect = lambda _: object()
        with self.assertRaisesRegex(m.Held, 'exact-owned-WAL-connection'):
            x.open_begin()
        self.assertFalse(Path(str(self.db) + '-wal').exists())

    def test_wrong_key_holds(self):
        with self.assertRaises(m.Held):
            m.WALReaderPhase(True, self.start, custody)

    def test_unknown_existing_companions_held(self):
        c = sqlite3.connect(self.db)
        c.execute('PRAGMA journal_mode')
        self.addCleanup(c.close)
        self.start.reader.pairs['database.sqlite'] = custody.raw_pair(self.db)
        with self.assertRaisesRegex(m.Held, 'existing-companions'):
            self.make()

    def test_original_source_mode_changed_before_connect(self):
        x = self.make()
        self.db.chmod(416)
        with self.assertRaises(m.Held):
            x.open_begin()
        self.assertIsNone(x.connection)
        self.assertFalse(Path(str(self.db) + '-wal').exists())

    def test_connect_callback_source_changed_prevents_mode_query(self):
        x = self.make()
        real = x.reader.disk.connect

        def changed(db):
            c = real(db)
            self.db.chmod(416)
            return c
        x.reader.disk.connect = changed
        with self.assertRaises(m.Held):
            x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        self.assertFalse(Path(str(self.db) + '-wal').exists())

    def test_last_native_callback_control_change_prevents_BEGIN(self):
        x = self.make()

        def changed(_):
            self.control.chmod(416)
            return ({}, {})
        self.native.native_sql_controls = changed
        with self.assertRaisesRegex(m.Held, 'terminal-WAL-file'):
            x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        self.assertFalse(x.connection.in_transaction)

    def test_foreign_namespace_prevents_BEGIN(self):
        x = self.make()

        def changed(_):
            (self.readerroot / 'foreign').write_bytes(b'foreign')
            return ({}, {})
        self.native.native_sql_controls = changed
        with self.assertRaisesRegex(m.Held, 'closed-reader-namespace'):
            x.open_begin()
        self.addCleanup(lambda: self.safe_close(x))
        self.assertFalse(x.connection.in_transaction)

    def test_mutated_phase_cannot_reseal(self):
        x = self.opening()
        x.current['']['sha256'] = 'f' * 64
        with self.assertRaisesRegex(m.Held, 'immutable-owning-WAL-phase'):
            x._life()

    def test_missing_reverse_intent_holds_before_BEGIN(self):
        x = self.opening()
        c = self.commit(x)
        c.phase = 'reverse-uncertain'
        c.records = {}
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'durable-WAL-reverse-intent'):
                x.begin_reverse(c)
        self.assertFalse(x.connection.in_transaction)

    def test_foreign_connection_reversal_held(self):
        x = self.opening()
        c = self.commit(x)
        c.sql.connection = sqlite3.connect(self.db)
        self.addCleanup(c.sql.connection.close)
        c.phase = 'reverse-uncertain'
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'same-connection'):
                x.begin_reverse(c)

    def test_other_connection_retains_companions_no_close_ACK(self):
        x = self.opening()
        c = self.commit(x)
        other = sqlite3.connect(self.db)
        other.execute('SELECT x FROM t').fetchall()
        self.addCleanup(other.close)
        c.current = custody.raw_pair(self.db)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'last-close-companions-retained'):
                x.close_connection(c)
        self.assertEqual(x.phase, 'close-uncertain')

    def test_readmark_projection_rejects_unrelated_byte(self):
        self.opening()
        pair = custody.raw_pair(self.db)
        raw = m.read_shm(self.db, pair)
        foreign = bytearray(raw)
        foreign[500] = 1
        with self.assertRaisesRegex(m.Held, 'no-other-SHM-change'):
            m.read_begin(pair, pair, raw, bytes(foreign))

    def test_readmark_projection_rejects_multiple_changes(self):
        self.opening()
        pair = custody.raw_pair(self.db)
        raw = m.read_shm(self.db, pair)
        foreign = bytearray(raw)
        foreign[104:112] = b'\x00' * 8
        with self.assertRaisesRegex(m.Held, 'single-readmark'):
            m.read_begin(pair, pair, raw, bytes(foreign))

    def test_empty_open_rejects_nonempty_WAL(self):
        self.opening()
        pair = custody.raw_pair(self.db)
        raw = m.read_shm(self.db, pair)
        pair['-wal']['signature9'][2] = 1
        with self.assertRaisesRegex(m.Held, 'empty-opening-log'):
            m.empty_open(self.baseline, pair, raw)

    def rolled_back_original(self):
        x = self.opening()
        x.connection.execute('UPDATE t SET x=9')
        x.connection.rollback()
        sql = SimpleNamespace(phase='rolled-back', connection=x.connection, pending=custody.raw_pair(self.db), directory=m.nine(os.lstat(self.readerroot)))
        x.reader.sql = sql
        x.reader.phase = 'rolled-back'
        x.reader.commit_custody = None
        x.reader.before = {'database.sqlite': ((1,),)}
        self.start.wal_phase = x
        self.start.sql = sql
        self.start.original_close_receipt = {'fixture': 'explicit fake receipt'}
        self.start.close_original_intent = lambda: None
        self.native.close_native_original_rollback = lambda r: None
        self.native.native_original_sql_controls = lambda r: ({}, {})
        return x

    def original_module(self):
        return SimpleNamespace(ReaderSQLStart=type(self.start))

    def test_WAL_COMMIT_pair_single_finite_successor(self):
        x = self.opening()
        c = self.commit(x)
        self.assertEqual(x.phase, 'committed-open')
        self.assertEqual(x.current, c.current)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'single-owned'):
                x.accept_committed_pair(c)

    def test_WAL_COMMIT_wrong_connection_refused(self):
        x = self.opening()
        c = self.commit(x)
        c.sql.connection = sqlite3.connect(self.db)
        self.addCleanup(c.sql.connection.close)
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'exact-owning'):
                x.accept_committed_pair(c)

    def test_WAL_COMMIT_last_observer_change_not_adopted(self):
        x = self.opening()
        x.connection.execute('UPDATE t SET x=2')
        x.connection.commit()
        c = Commit()
        c.sql = SimpleNamespace(connection=x.connection, db=self.db)
        c.reader = x.reader
        c.reservation = self.native
        c.phase = 'committed'
        c.after = ((2,),)
        c.current = custody.raw_pair(self.db)
        c.directory = m.nine(os.lstat(self.readerroot))
        real = c._close_observed

        def changed(*a):
            real(*a)
            self.control.chmod(416)
        c._close_observed = changed
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file'):
                x.accept_committed_pair(c)
        self.assertEqual(x.phase, 'begun')

    def test_WAL_COMMIT_companion_replacement_refused(self):
        x = self.opening()
        x.connection.execute('UPDATE t SET x=2')
        x.connection.commit()
        c = Commit()
        c.sql = SimpleNamespace(connection=x.connection)
        c.reader = x.reader
        c.reservation = self.native
        c.phase = 'committed'
        c.after = ((2,),)
        p = Path(str(self.db) + '-wal')
        raw = p.read_bytes()
        replacement = self.root / 'replacement'
        replacement.write_bytes(raw)
        replacement.chmod(384)
        replacement.replace(p)
        c.current = custody.raw_pair(self.db)
        c.directory = m.nine(os.lstat(self.readerroot))
        with patch.object(m, 'installed', return_value=SimpleNamespace(ReaderSQLCommit=Commit)):
            with self.assertRaisesRegex(m.Held, 'companion-incarnation'):
                x.accept_committed_pair(c)

    def test_original_rollback_owned_close_before_terminal(self):
        x = self.rolled_back_original()
        with patch.object(m, 'installed', return_value=self.original_module()):
            x.close_original(self.start)
        self.assertEqual(x.phase, 'closed-original')
        self.assertEqual(x.current, self.baseline)
        self.assertFalse(Path(str(self.db) + '-wal').exists())
        self.assertFalse(Path(str(self.db) + '-shm').exists())
        with self.assertRaises(sqlite3.ProgrammingError):
            x.connection.execute('SELECT 1')

    def test_original_close_missing_intent_leaves_connection_open(self):
        x = self.rolled_back_original()
        self.start.original_close_receipt = None
        with patch.object(m, 'installed', return_value=self.original_module()):
            with self.assertRaisesRegex(m.Held, 'durable-original'):
                x.close_original(self.start)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(1,)])

    def test_original_close_active_transaction_refused(self):
        x = self.rolled_back_original()
        x.connection.execute('BEGIN IMMEDIATE')
        with patch.object(m, 'installed', return_value=self.original_module()):
            with self.assertRaisesRegex(m.Held, 'proved-original'):
                x.close_original(self.start)
        self.assertTrue(x.connection.in_transaction)

    def test_original_close_last_native_callback_changed_main_no_close(self):
        x = self.rolled_back_original()

        def changed(_):
            self.db.chmod(416)
            return ({}, {})
        self.native.native_original_sql_controls = changed
        with patch.object(m, 'installed', return_value=self.original_module()):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file'):
                x.close_original(self.start)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(1,)])

    def test_original_close_last_ancestor_change_no_close(self):
        self.with_ancestor()
        x = self.rolled_back_original()
        real = m.five
        count = 0
        fired = []

        def changed(z):
            nonlocal count
            value = real(z)
            if inspect.currentframe().f_back.f_code.co_name == '_direct':
                count += 1
            if count == 2:
                self.db.chmod(416)
                fired.append(True)
            return value
        with patch.object(m, 'installed', return_value=self.original_module()), patch.object(m, 'five', new=changed):
            with self.assertRaisesRegex(m.Held, 'terminal-WAL-file-final'):
                x.close_original(self.start)
        self.assertTrue(fired)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(1,)])

    def test_original_close_unknown_namespace_no_close(self):
        x = self.rolled_back_original()

        def changed(_):
            (self.readerroot / 'foreign').write_bytes(b'x')
            return ({}, {})
        self.native.native_original_sql_controls = changed
        with patch.object(m, 'installed', return_value=self.original_module()):
            with self.assertRaisesRegex(m.Held, 'closed-reader-namespace'):
                x.close_original(self.start)
        self.assertEqual(x.connection.execute('SELECT x FROM t').fetchall(), [(1,)])

    def test_original_close_other_connection_hold_no_ACK(self):
        x = self.rolled_back_original()
        other = sqlite3.connect(self.db)
        other.execute('SELECT x FROM t').fetchall()
        self.addCleanup(other.close)
        x.reader.sql.pending = custody.raw_pair(self.db)
        with patch.object(m, 'installed', return_value=self.original_module()):
            with self.assertRaisesRegex(m.Held, 'last-close-companions'):
                x.close_original(self.start)
        self.assertEqual(x.phase, 'original-close-uncertain')

    def test_factory_refuses_missing_installed_start(self):
        with patch.object(m, 'installed', side_effect=ModuleNotFoundError):
            with self.assertRaises(ModuleNotFoundError):
                m.from_opening(self.start)
if __name__ == '__main__':
    unittest.main()

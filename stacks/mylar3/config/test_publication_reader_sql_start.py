"""Real local SQLite opening/body, explicit fake native phase only."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import copy
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
m = load('sql_start', str(_PORTABLE_ROOT / 'publication_reader_sql_start.py'))
f = load('reader_tests', str(_PORTABLE_ROOT / 'fixtures/test_publication_reader_phase_v6.py'))
r = f.m
sql = load('sql_custody', str(_PORTABLE_ROOT / 'publication_reader_sql_custody.py'))

class Reservation:

    def close_native_precommit(self, reader):
        if reader is not self.reader:
            raise m.Held('native-reader')

    def revalidate_staged(self, reader, preparations):
        if reader is not self.reader or preparations != self.batch.preparations:
            raise m.Held('exact-staged')

    def native_sql_controls(self, reader):
        return ({}, {})

    def close_native_original_rollback(self, reader):
        if self.projection.phases != ['source'] * 5:
            raise m.Held('original-source-required')

    def native_original_sql_controls(self, reader):
        self.close_native_original_rollback(reader)
        return ({}, {})

class Tests(unittest.TestCase):

    def setUp(self):
        self.c = f.PhaseTests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.reader = self.c.phase
        self.batch = Reservation()
        self.batch.reader = self.reader
        self.batch.core = 'a' * 64
        self.batch.batch = SimpleNamespace(preparations=self.reader.preparations, controller=SimpleNamespace(roots=[self.reader.root]))
        self.j = self.c.fixture.root / 'sql-start'
        self.j.mkdir(mode=448)
        self.commit = self.c.fixture.root / 'sql-commit'
        self.commit.mkdir(mode=448)
        self.modules = [SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_phase.py', StoppedReaderPhase=r.StoppedReaderPhase), SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=Reservation), SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_custody.py', SQLWritingCustody=sql.SQLWritingCustody, _KEY=sql._KEY)]
        self.map = dict(zip(('mylar.publication_reader_phase', 'mylar.publication_negative_batch_transition', 'mylar.publication_reader_sql_custody'), self.modules))

    def module(self, name):
        if name not in self.map:
            raise ModuleNotFoundError(name)
        return self.map[name]

    def make(self):
        return m.ReaderSQLStart(m._KEY, self.reader, self.batch, self.j, self.commit, self.modules)

    def run_pending(self, x):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            return x.open_pending()

    def test_real_five_SQL_after_durable_intent_no_commit(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            x = self.make()
            self.run_pending(x)
        self.addCleanup(x.sql.connection.close)
        self.assertTrue((self.j / 'opening.json').exists())
        self.assertTrue(x.sql.connection.in_transaction)
        self.assertEqual(x.sql.logical(), self.reader.after['database.sqlite'])
        self.assertEqual(self.reader.phase, 'sql-writing')
        x.close_pending()
        x.sql.connection.rollback()

    def test_wrong_key_before_open(self):
        with self.assertRaises(m.Held):
            m.ReaderSQLStart(True, self.reader, self.batch, self.j, self.commit, self.modules)

    def test_journal_inside_reader_root_holds_no_write(self):
        j = self.reader.root / 'j'
        j.mkdir(mode=448)
        with self.assertRaises(m.Held):
            m.ReaderSQLStart(m._KEY, self.reader, self.batch, j, self.commit, self.modules)
        self.assertFalse((j / 'opening.json').exists())

    def test_foreign_journal_holds_before_open(self):
        (self.j / 'foreign').write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            self.make()

    def test_public_factory_missing_package_no_SQL(self):
        with self.assertRaises(m.Held):
            m.prepare_existing(self.reader, self.batch, self.j, self.commit)
        self.assertFalse((self.j / 'opening.json').exists())

    def test_last_native_callback_main_mode_holds_no_SQL(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            x = self.make()
            calls = 0
            real = self.batch.native_sql_controls

            def drift(reader):
                nonlocal calls
                calls += 1
                v = real(reader)
                if calls == 2:
                    (self.reader.root / 'database.sqlite').chmod(416)
                return v
            self.batch.native_sql_controls = drift
            with self.assertRaises(Exception):
                x.open_pending()
        self.assertIsNone(x.sql)
        self.assertFalse(Path(str(self.reader.root / 'database.sqlite') + '-journal').exists())
        if hasattr(x, 'connection'):
            x.connection.close()

    def test_intent_rewrite_holds_pending_ACK(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            x = self.make()
            self.run_pending(x)
        self.addCleanup(x.sql.connection.close)
        (self.j / 'opening.json').write_bytes(b'{}')
        with self.assertRaises(m.Held):
            x.close_pending()
        x.sql.connection.rollback()

    def test_mutable_journal_reseal_holds(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            x = self.make()
        x.journal = self.commit
        with self.assertRaises(m.Held):
            x.open_pending()

    def test_last_native_body_callback_control_drift_no_update(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            x = self.make()
            real = self.batch.native_sql_controls
            calls = 0

            def drift(reader):
                nonlocal calls
                calls += 1
                v = real(reader)
                if calls == 3:
                    self.c.fixture.control.chmod(416)
                return v
            self.batch.native_sql_controls = drift
            with self.assertRaises(Exception):
                x.open_pending()
        self.assertIsNotNone(x.sql)
        self.assertEqual(x.sql.logical(), self.reader.before['database.sqlite'])
        self.assertFalse(Path(str(x.sql.db) + '-journal').exists())
        x.sql.connection.rollback()
        x.sql.connection.close()

    def enable_fixture_WAL_components(self):
        connection = self.reader.disk.connect(self.reader.root / 'database.sqlite')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.close()
        self.reader = r.StoppedReaderPhase(r._KEY, self.c.fixture.admission())
        self.batch.reader = self.reader
        self.batch.batch.preparations = self.reader.preparations
        w = load('wal_start_phase', str(_PORTABLE_ROOT / 'fixtures/publication_reader_wal_phase_v4.py'))
        self.modules[2].from_wal_begin = sql.from_wal_begin
        self.modules[2].raw_pair = sql.raw_pair
        self.map.update({'mylar.publication_reader_wal_phase': SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_wal_phase.py', WALReaderPhase=w.WALReaderPhase, from_opening=w.from_opening), 'mylar.publication_reader_sql_start': SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_start.py', ReaderSQLStart=m.ReaderSQLStart), 'mylar.publication_reader_sql_commit': SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_commit.py', from_pending_wal=lambda *args: None)})

    def original_WAL_rollback(self):
        self.enable_fixture_WAL_components()
        x = self.make()
        x.open_pending()
        x.close_pending()
        x.sql.rollback_owned()
        self.reader.accept_uncommitted_rollback(x.sql, self.batch)
        self.batch.projection = SimpleNamespace(phases=['source'] * 5)
        return x

    def test_real_original_WAL_close_durable_before_terminal(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            x = self.original_WAL_rollback()
            original = copy.deepcopy(self.reader.original._pairs)
            x.close_original_wal()
            binding = self.reader.original_rollback_binding(self.batch)
        self.assertEqual(x.wal_phase.phase, 'closed-original')
        self.assertEqual(binding['main_pair'], x.wal_phase.original)
        self.assertTrue((self.j / 'original-close-intent.json').is_file())
        self.assertFalse(binding['publication_acceptance'])
        self.assertEqual(self.reader.original._pairs, original)
        self.assertFalse(Path(str(x.sql.db) + '-wal').exists())

    def test_original_WAL_close_intent_corruption_no_close(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            x = self.original_WAL_rollback()
            real = x.close_original_intent

            def changed():
                (self.j / 'original-close-intent.json').write_bytes(b'{}')
                return real()
            x.close_original_intent = changed
            with self.assertRaisesRegex(m.Held, 'intended-bytes'):
                x.close_original_wal()
        self.assertFalse(x.sql.connection.in_transaction)
        self.assertTrue(Path(str(x.sql.db) + '-wal').exists())
        x.sql.connection.close()

    def test_original_WAL_close_linked_native_sources_hold_before_close_intent(self):
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            x = self.original_WAL_rollback()
            self.batch.projection.phases = ['linked'] * 5
            with self.assertRaisesRegex(m.Held, 'original-source'):
                x.close_original_wal()
        self.assertFalse((self.j / 'original-close-intent.json').exists())
        x.sql.connection.close()

    def test_real_WAL_opening_body_five_no_COMMIT(self):
        self.enable_fixture_WAL_components()
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            x = self.make()
            x.open_pending()
            x.close_pending()
        self.addCleanup(x.sql.connection.close)
        self.assertEqual(x.sql.logical(), self.reader.after['database.sqlite'])
        self.assertTrue(x.sql.connection.in_transaction)
        self.assertEqual(x.wal_phase.phase, 'begun')
        self.assertIs(self.reader.wal_phase, x.wal_phase)
        self.assertTrue((self.j / 'opening.json').exists())
        self.assertEqual(self.reader.phase, 'sql-writing')
        x.sql.rollback_owned()

    def test_delete_only_commit_module_refuses_WAL_before_intent(self):
        self.enable_fixture_WAL_components()
        self.map['mylar.publication_reader_sql_commit'] = SimpleNamespace(__file__='/app/mylar3/mylar/publication_reader_sql_commit.py', from_pending=lambda *a: None)
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            with self.assertRaisesRegex(m.Held, 'WAL-forward-refused'):
                self.make()
        self.assertFalse((self.j / 'opening.json').exists())
        self.assertFalse(Path(str(self.reader.root / 'database.sqlite') + '-wal').exists())

    def test_WAL_constructor_source_drift_refuses_before_intent(self):
        self.enable_fixture_WAL_components()
        (self.reader.root / 'database.sqlite').chmod(416)
        with patch.object(r.importlib, 'import_module', side_effect=lambda n: self.module(n)):
            with self.assertRaisesRegex(m.Held, 'SQL-mode-source-CAS'):
                self.make()
        self.assertFalse((self.j / 'opening.json').exists())

    def test_actual_WAL_header_refused_before_intent_or_begin(self):
        conn = self.reader.disk.connect(self.reader.root / 'database.sqlite')
        conn.execute('PRAGMA journal_mode=WAL')
        conn.close()
        self.reader = r.StoppedReaderPhase(r._KEY, self.c.fixture.admission())
        self.batch.reader = self.reader
        self.batch.batch.preparations = self.reader.preparations
        with patch.object(r.importlib, 'import_module', side_effect=lambda name: self.module(name)):
            with self.assertRaisesRegex(m.Held, 'WAL-forward-refused'):
                self.make()
        self.assertFalse((self.j / 'opening.json').exists())
if __name__ == '__main__':
    unittest.main()

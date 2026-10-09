"""Explicit typed boundary doubles, no installed or operational acceptance."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
s = importlib.util.spec_from_file_location('aggregate', str(_PORTABLE_ROOT / 'publication_negative_aggregate.py'))
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

class Reservation:

    def __init__(self):
        self.core = 'a' * 64
        self.reader = SimpleNamespace()
        self.events = []
        self.batch = SimpleNamespace(preparations=[SimpleNamespace(consume=lambda r, i=i: self.events.append(('consume', i))) for i in range(5)])

    def stage_all(self):
        self.events.append('stage')

    def rollback_staging(self):
        self.events.append('rollback')

class Commit:

    def __init__(self, reservation):
        self.r = reservation
        self.phase = 'committed'

    def commit(self):
        self.r.events.append('commit')

    def reverse(self):
        self.r.events.append('reverse')
        self.phase = 'reversed'

    def close_owned_connection(self):
        self.r.events.append('committed-WAL-close')

class Terminal:

    def __init__(self, r):
        self.r = r

    def clear(self):
        self.r.events.append('clear')
        return {'publication_acceptance': False}

class Tests(unittest.TestCase):

    def setUp(self):
        self.r = Reservation()
        self.start = SimpleNamespace(sql=SimpleNamespace(mode='delete'), open_pending=lambda: self.r.events.append('open'), close_pending=lambda: self.r.events.append('pending'))
        self.modules = [SimpleNamespace(NegativeBatchReservation=Reservation), SimpleNamespace(prepare_existing=lambda *a: self.start), SimpleNamespace(ReaderSQLCommit=Commit, from_pending=lambda *a: Commit(self.r)), SimpleNamespace(from_retired=lambda r, c: Terminal(r)), SimpleNamespace(from_original=lambda r, reader: Terminal(r), from_reversed=lambda r, commit: Terminal(r))]

    def make(self):
        return m.NegativeReaderAggregate(m._KEY, self.r, Path('/tmp/example-start'), Path('/tmp/example-commit'), self.modules)

    def test_exact_order_no_boolean_native_consumption(self):
        x = self.make()
        ack = x.execute()
        self.assertEqual(self.r.events, ['stage', 'open', 'pending', 'commit', *[('consume', i) for i in range(5)], 'clear'])
        self.assertFalse(ack['publication_acceptance'])

    def test_WAL_uses_exact_owned_factory_and_carried_phase(self):
        phase = object()
        self.start.sql.mode = 'wal'
        self.start.wal_phase = phase
        self.r.reader.wal_phase = phase
        seen = []

        def factory(sql, reader, reservation, wal):
            seen.append((sql, reader, reservation, wal))
            return Commit(self.r)
        self.modules[2].from_pending_wal = factory
        x = self.make()
        x.execute()
        self.assertEqual(seen, [(self.start.sql, self.r.reader, self.r, phase)])
        self.assertEqual(x.phase, 'terminal')
        self.assertEqual(self.r.events[-2:], ['committed-WAL-close', 'clear'])
        self.assertEqual(self.r.events[-3], ('consume', 4))

    def test_missing_WAL_factory_never_COMMIT_or_retire(self):
        self.start.sql.mode = 'wal'
        self.start.wal_phase = object()
        self.r.reader.wal_phase = self.start.wal_phase
        x = self.make()
        with self.assertRaisesRegex(m.Held, 'exact-owning-WAL-commit-factory'):
            x.execute()
        self.assertEqual(self.r.events, ['stage', 'open', 'pending'])

    def test_foreign_WAL_phase_never_COMMIT_or_retire(self):
        self.start.sql.mode = 'wal'
        self.start.wal_phase = object()
        self.r.reader.wal_phase = object()
        self.modules[2].from_pending_wal = lambda *a: Commit(self.r)
        x = self.make()
        with self.assertRaisesRegex(m.Held, 'exact-owning-WAL-commit-factory'):
            x.execute()
        self.assertEqual(self.r.events, ['stage', 'open', 'pending'])

    def test_missing_terminal_before_any_staging(self):
        self.modules[3] = SimpleNamespace()
        with self.assertRaises(m.Held):
            self.make()
        self.assertEqual(self.r.events, [])

    def test_boolean_constructor_rejected(self):
        with self.assertRaises(m.Held):
            m.NegativeReaderAggregate(True, self.r, Path('/tmp/a'), Path('/tmp/b'), self.modules)

    def test_mutable_phase_reseal_holds(self):
        x = self.make()
        x.phase = 'SQL-committed'
        with self.assertRaises(m.Held):
            x.rollback()
        self.assertEqual(self.r.events, [])

    def test_custody_path_substitution_holds(self):
        x = self.make()
        x.start_journal = Path('/tmp/foreign')
        with self.assertRaises(m.Held):
            x.execute()
        self.assertEqual(self.r.events, [])

    def test_fresh_ordinary_entry_missing_installed_modules_holds(self):
        with self.assertRaises(m.Held):
            m.from_staged_preparation(self.r, Path('/tmp/a'), Path('/tmp/b'))
        self.assertEqual(self.r.events, [])

    def test_WAL_original_rollback_close_after_FS_before_terminal(self):
        self.start.sql = SimpleNamespace(mode='wal', pending={'fixture': 'typed double'}, rollback_owned=lambda: self.r.events.append('SQL-rollback'))
        self.start.close_original_wal = lambda: self.r.events.append('owned-WAL-close')
        self.r.reader.accept_uncommitted_rollback = lambda *a: self.r.events.append('reader-rollback')
        x = self.make()
        x.start = self.start
        x.phase = 'SQL-pending'
        x._seal()
        x.rollback()
        self.assertEqual(self.r.events, ['pending', 'SQL-rollback', 'reader-rollback', 'rollback', 'owned-WAL-close', 'clear'])

    def test_WAL_original_close_failure_keeps_terminal_unrun(self):
        self.start.sql = SimpleNamespace(mode='wal', pending={'fixture': 'typed double'}, rollback_owned=lambda: None)
        self.start.close_original_wal = lambda: (_ for _ in ()).throw(m.Held('owned-close-held'))
        self.r.reader.accept_uncommitted_rollback = lambda *a: None
        x = self.make()
        x.start = self.start
        x.phase = 'SQL-pending'
        x._seal()
        with self.assertRaisesRegex(m.Held, 'owned-close-held'):
            x.rollback()
        self.assertIsNone(x.terminal)
        self.assertNotIn('clear', self.r.events)

    def test_missing_original_rollback_factory_before_stage(self):
        self.modules[4] = SimpleNamespace(from_reversed=lambda *a: None)
        with self.assertRaises(m.Held):
            self.make()
        self.assertEqual(self.r.events, [])

    def committed_wal(self):
        self.start.sql.mode = 'wal'
        x = self.make()
        x.start = self.start
        x.sql_commit = Commit(self.r)
        x.phase = 'SQL-committed'
        x._seal()
        return x

    def test_committed_WAL_reverse_closes_before_native_rollback(self):
        x = self.committed_wal()
        x.rollback()
        self.assertEqual(self.r.events, ['reverse', 'committed-WAL-close', 'rollback', 'clear'])
        self.assertEqual(x.phase, 'rollback-terminal')

    def test_forward_WAL_close_failure_keeps_success_terminal_unrun(self):
        phase = object()
        self.start.sql.mode = 'wal'
        self.start.wal_phase = phase
        self.r.reader.wal_phase = phase

        class FailingCommit(Commit):

            def close_owned_connection(self):
                self.r.events.append('close-held')
                raise m.Held('closed-pair-unproved')
        self.modules[2].ReaderSQLCommit = FailingCommit
        self.modules[2].from_pending_wal = lambda *a: FailingCommit(self.r)
        x = self.make()
        with self.assertRaisesRegex(m.Held, 'closed-pair-unproved'):
            x.execute()
        self.assertIsNone(x.terminal)
        self.assertNotIn('clear', self.r.events)
        self.assertEqual(self.r.events[-2:], [('consume', 4), 'close-held'])

    def test_reverse_WAL_close_failure_keeps_native_rollback_unrun(self):
        x = self.committed_wal()

        def fail():
            self.r.events.append('close-held')
            raise m.Held('reverse-close-unproved')
        x.sql_commit.close_owned_connection = fail
        with self.assertRaisesRegex(m.Held, 'reverse-close-unproved'):
            x.rollback()
        self.assertEqual(self.r.events, ['reverse', 'close-held'])
        self.assertIsNone(x.terminal)

    def test_missing_close_consumer_holds_before_any_staging(self):
        self.modules[2].ReaderSQLCommit = type('IncompleteCommit', (), {})
        with self.assertRaisesRegex(m.Held, 'all-owning-consumers-before-SQL'):
            self.make()
        self.assertEqual(self.r.events, [])
if __name__ == '__main__':
    unittest.main()

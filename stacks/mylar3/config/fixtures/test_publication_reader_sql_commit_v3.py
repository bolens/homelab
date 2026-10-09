"""Real temporary SQLite commit/reverse; EXPLICIT fake typed handshake only.

These fixtures prove mechanics, not installed factories, stopped service or
native/reader authority. The public factory must refuse this fixture package.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

def load(n, p):
    s = importlib.util.spec_from_file_location(n, p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
m = load('reader_commit', str(_PORTABLE_ROOT / 'fixtures/publication_reader_sql_commit_v3.py'))
f = load('custody_fixture', str(_PORTABLE_ROOT / 'fixtures/test_publication_reader_sql_custody_v5.py'))

class Tests(unittest.TestCase):

    def setUp(self):
        self.c = f.Tests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.sql = self.c.make()
        self.sql.apply_body(f.r.sql_five_transition)
        self.journal = self.c.c.root / 'commit-journal'
        self.journal.mkdir(mode=448)

        class Reader:

            def revalidate_sql_writing(r, s, b):
                s.close_pending()

            def sql_syscall_controls(r, s, b):
                return ({}, {}, ())

            def accept_committed(r, c):
                r.custody = c

            def revalidate_sql_observed(r, c, b):
                pass

            def sql_observed_controls(r, c, b):
                return ({}, {}, ())

            def revalidate_sql_reversing(r, c, s, b):
                s.close_pending()

            def sql_reverse_controls(r, c, s, b):
                return ({}, {}, ())

            def accept_reversed(r, c):
                r.custody = c

        class Batch:

            def close_native_precommit(b, r):
                pass

            def native_sql_controls(b, r):
                return ({}, {}, ())

            def close_native_reverse(b, r):
                pass
        self.reader = Reader()
        self.batch = Batch()
        self.reader.sql = self.sql
        self.reader.batch = self.batch
        self.batch.reader = self.reader
        self.reader.preparations = tuple((object() for _ in range(5)))
        self.batch.batch = types.SimpleNamespace(preparations=self.reader.preparations)
        self.reader.tasks_database = self.c.c.config / 'tasks.sqlite'
        self.reader.tasks_pair = f.m.raw_pair(self.reader.tasks_database)
        self.reader.sql_operation = self.journal
        self.reader.scratch = self.c.c.scratch
        self.modules = (f.m, types.SimpleNamespace(StoppedReaderPhase=Reader), types.SimpleNamespace(NegativeBatchReservation=Batch), f.r)

    def make(self):
        return m.ReaderSQLCommit(m._KEY, self.sql, self.reader, self.batch, self.modules)

    def test_real_commit_exact_five_and_all_tables(self):
        x = self.make()
        self.assertIs(x.commit(), x)
        self.assertFalse(self.c.conn.in_transaction)
        self.assertEqual(self.sql.logical(), self.c.after)
        x.close_committed(self.batch)
        self.assertEqual(x.binding['phase'], 'committed')
        self.assertFalse(x.binding['publication_acceptance'])
        self.assertFalse(x.binding['mutation_authority'])

    def test_real_reverse_exact_five_and_all_tables(self):
        x = self.make()
        x.commit()
        x.reverse()
        self.assertEqual(self.sql.logical(), self.c.before)
        x.close_reversed(self.batch)
        self.assertFalse(self.c.conn.in_transaction)
        self.assertEqual(x.binding['phase'], 'reversed')

    def test_tasks_bytes_attrs_never_change(self):
        before = f.m.raw_pair(self.reader.tasks_database)
        x = self.make()
        x.commit()
        x.reverse()
        self.assertEqual(f.m.raw_pair(self.reader.tasks_database), before)

    def test_public_factory_has_no_fixture_grant(self):
        with self.assertRaises(m.Held):
            m.from_pending(self.sql, self.reader, self.batch)

    def test_boolean_key_refuses(self):
        with self.assertRaises(m.Held):
            m.ReaderSQLCommit(True, self.sql, self.reader, self.batch, self.modules)

    def test_wrong_reservation_refuses(self):
        x = self.make()
        x.commit()
        with self.assertRaises(m.Held):
            x.close_committed(object())

    def test_foreign_main_mode_before_commit_retains_intent(self):
        x = self.make()
        self.c.db.chmod(416)
        with self.assertRaises(ValueError):
            x.commit()
        self.assertTrue(self.c.conn.in_transaction)
        self.assertEqual(list(self.journal.iterdir()), [])

    def test_native_last_callback_main_mode_refuses_before_commit(self):
        x = self.make()
        self.batch.native_sql_controls = lambda r: self.c.db.chmod(416) or ({}, {}, ())
        with self.assertRaises(ValueError):
            x.commit()
        self.assertTrue(self.c.conn.in_transaction)

    def test_late_intent_write_mode_refuses_before_commit(self):
        x = self.make()
        real = x._record

        def changed(name):
            real(name)
            self.c.db.chmod(416)
        with patch.object(x, '_record', side_effect=changed):
            with self.assertRaises(ValueError):
                x.commit()
        self.assertTrue(self.c.conn.in_transaction)
        self.assertTrue((self.journal / 'commit-intent.json').exists())

    def test_no_commit_replay(self):
        x = self.make()
        x.commit()
        with self.assertRaises(m.Held):
            x.commit()

    def test_committed_pair_samebytes_inode_replacement_held(self):
        x = self.make()
        x.commit()
        data = self.c.db.read_bytes()
        self.c.db.rename(self.c.db.with_suffix('.retained'))
        self.c.db.write_bytes(data)
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_committed_unrelated_row_mutation_held(self):
        x = self.make()
        x.commit()
        self.c.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='correct-0'")
        self.c.conn.commit()
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_last_reader_callback_catalog_tasks_change_held(self):
        x = self.make()
        x.commit()
        self.reader.sql_observed_controls = lambda *a: self.reader.tasks_database.chmod(416) or ({}, {}, ())
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_late_reader_callback_foreign_journal_held(self):
        x = self.make()
        x.commit()
        self.reader.sql_observed_controls = lambda *a: (self.journal / 'foreign').write_bytes(b'foreign') and ({}, {}, ())
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_receipt_rewrite_no_ack(self):
        x = self.make()
        x.commit()
        (self.journal / 'committed.json').write_bytes(b'{}')
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_commit_receipt_identity_and_five_ids_bound(self):
        x = self.make()
        x.commit()
        b = x.binding
        self.assertEqual(len(b['preparation_ids']), 5)
        self.assertEqual(b['reservation_id'], id(self.batch))
        self.assertEqual(b['receipt']['path'], str(self.journal / 'committed.json'))

    def test_copy_binding_cannot_reseal(self):
        x = self.make()
        x.commit()
        b = x.binding
        b['main_pair'] = {}
        x.close_committed(self.batch)

    def test_reverse_foreign_current_row_never_changes_back(self):
        x = self.make()
        x.commit()
        self.c.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='wrong-0'")
        self.c.conn.commit()
        with self.assertRaises(m.Held):
            x.reverse()
        self.assertEqual(self.c.conn.execute("SELECT NAME FROM BOOK WHERE ID='wrong-0'").fetchone()[0], 'foreign')

    def test_reverse_late_native_callback_mode_refuses(self):
        x = self.make()
        x.commit()
        self.batch.close_native_reverse = lambda r: self.c.db.chmod(416)
        with self.assertRaises(m.Held):
            x.reverse()
        self.assertFalse(self.c.conn.in_transaction)

    def test_clear_marker_does_not_break_reader_only_proof(self):
        x = self.make()
        x.commit()
        self.batch.close_native_precommit = lambda r: (_ for _ in ()).throw(AssertionError('native callback forbidden'))
        x.close_committed(self.batch)

    def test_unknown_commit_response_retained_no_replay(self):
        x = self.make()
        with patch.object(x, '_capture', side_effect=RuntimeError('lost response after actual commit')):
            with self.assertRaises(RuntimeError):
                x.commit()
        self.assertFalse(self.c.conn.in_transaction)
        self.assertEqual(self.sql.logical(), self.c.after)
        self.assertEqual(x.binding['phase'], 'commit-uncertain')
        self.assertTrue((self.journal / 'commit-intent.json').exists())
        self.assertFalse((self.journal / 'committed.json').exists())
        with self.assertRaises(m.Held):
            x.commit()

    def test_unknown_reverse_response_retained_no_replay(self):
        x = self.make()
        x.commit()
        with patch.object(x, '_capture', side_effect=RuntimeError('lost reversal ACK')):
            with self.assertRaises(RuntimeError):
                x.reverse()
        self.assertEqual(self.sql.logical(), self.c.before)
        self.assertEqual(x.binding['phase'], 'reverse-uncertain')
        self.assertTrue((self.journal / 'reverse-intent.json').exists())
        with self.assertRaises(m.Held):
            x.reverse()

    def test_current_pair_and_state_reseal_cannot_mint_successor(self):
        x = self.make()
        x.commit()
        raw = self.c.db.read_bytes()
        self.c.db.rename(self.c.db.with_suffix('.retained'))
        self.c.db.write_bytes(raw)
        self.c.db.chmod(384)
        x.current = f.m.raw_pair(self.c.db)
        x.directory = m.sig(x.root)
        x.state = x._state()
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_intent_FD_parent_alias_never_writes_foreign(self):
        import os
        x = self.make()
        real = os.open
        foreign = self.c.c.root / 'foreign-journal'
        foreign.mkdir(mode=448)
        saved = self.c.c.root / 'saved-journal'
        fired = False

        def raced(p, flags, *a, **kw):
            nonlocal fired
            if str(p) == 'commit-intent.json' and kw.get('dir_fd') is not None and (not fired):
                fired = True
                self.journal.rename(saved)
                self.journal.symlink_to(foreign, target_is_directory=True)
                try:
                    return real(p, flags, *a, **kw)
                finally:
                    self.journal.unlink()
                    saved.rename(self.journal)
            return real(p, flags, *a, **kw)
        with patch.object(m.os, 'open', side_effect=raced):
            x.commit()
        self.assertTrue(fired)
        self.assertEqual(list(foreign.iterdir()), [])
        self.assertTrue((self.journal / 'committed.json').exists())

    def test_last_reader_observed_callback_companion_creation_held(self):
        x = self.make()
        x.commit()

        def late(*a):
            Path(str(self.c.db) + '-wal').write_bytes(b'foreign')
            return ({}, {})
        self.reader.sql_observed_controls = late
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_last_reader_callback_source_inode_change_held(self):
        x = self.make()
        x.commit()

        def late(*a):
            raw = self.c.db.read_bytes()
            self.c.db.rename(self.c.db.with_suffix('.retained'))
            self.c.db.write_bytes(raw)
            return ({}, {})
        self.reader.sql_observed_controls = late
        with self.assertRaises(m.Held):
            x.close_committed(self.batch)

    def test_tasks_samebytes_replacement_before_commit_no_commit(self):
        x = self.make()
        db = self.reader.tasks_database
        raw = db.read_bytes()
        db.rename(db.with_suffix('.retained'))
        db.write_bytes(raw)
        with self.assertRaises(ValueError):
            x.commit()
        self.assertTrue(self.c.conn.in_transaction)

    def test_last_committed_receipt_write_main_drift_no_ACK(self):
        x = self.make()
        real = x._record

        def late(name):
            real(name)
            self.c.db.chmod(416) if name == 'committed' else None
        with patch.object(x, '_record', side_effect=late):
            with self.assertRaises(m.Held):
                x.commit()
        self.assertFalse(self.c.conn.in_transaction)
        self.assertTrue((self.journal / 'commit-intent.json').exists())

    def test_last_reversed_receipt_write_tasks_drift_no_ACK(self):
        x = self.make()
        x.commit()
        real = x._record

        def late(name):
            real(name)
            self.reader.tasks_database.chmod(416) if name == 'reversed' else None
        with patch.object(x, '_record', side_effect=late):
            with self.assertRaises(m.Held):
                x.reverse()
        self.assertEqual(self.sql.logical(), self.c.before)
        self.assertTrue((self.journal / 'reverse-intent.json').exists())

    def test_stale_native_binding_before_intent_no_COMMIT(self):
        x = self.make()
        self.batch.close_native_precommit = lambda r: (_ for _ in ()).throw(m.Held('stale-census'))
        with self.assertRaises(m.Held):
            x.commit()
        self.assertEqual(list(self.journal.iterdir()), [])
        self.assertTrue(self.c.conn.in_transaction)

    def test_five_original_ids_in_immutable_core(self):
        x = self.make()
        x.preparation_ids = tuple(range(5))
        x.core = x._core()
        x.state = x._state()
        with self.assertRaises(m.Held):
            x.commit()

    def test_negative_claim_absent_ancestor_preserved(self):
        absent = self.c.c.root / 'missing-parent'
        self.batch.native_sql_controls = lambda r: ({}, {absent: None})
        x = self.make()
        x.commit()
        files, nodes = x.vectors()
        self.assertIn(Path(str(self.c.db) + '-journal'), files)
        self.assertIsNone(files[Path(str(self.c.db) + '-journal')])

    def test_late_negative_claim_absent_ancestor_creation_refuses(self):
        absent = self.c.c.root / 'missing-parent'
        x = self.make()

        def changed(r):
            absent.mkdir()
            return ({}, {absent: None})
        self.batch.native_sql_controls = changed
        with self.assertRaises(m.Held):
            x.commit()
        self.assertTrue(self.c.conn.in_transaction)

    def wal_pending(self):
        import sqlite3
        self.c.conn.rollback()
        self.c.conn.close()
        connection = sqlite3.connect(self.c.db)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.close()
        self.c.conn = self.c.disk.connect(self.c.db)
        self.c.conn.execute('BEGIN IMMEDIATE')
        baseline = f.m.raw_pair(self.c.db)
        self.sql = f.m.SQLWritingCustody(f.m._KEY, self.c.conn, self.c.db, self.c.disk, self.c.c.plan, self.c.before, self.c.after, baseline)
        self.sql.apply_body(f.r.sql_five_transition)
        self.reader.sql = self.sql

    def test_real_WAL_mechanics_detached_observation_no_owning_grant(self):
        self.wal_pending()
        self.c.conn.commit()
        baseline = f.m.raw_pair(self.c.db)
        self.assertIn('-wal', baseline)
        self.assertIn('-shm', baseline)
        self.assertEqual(self.c.disk.observe_copy(self.c.db, self.c.c.plan, self.reader.scratch), self.c.after)
        self.assertEqual(f.m.raw_pair(self.c.db), baseline)

    def test_WAL_owning_factory_refuses_before_intent_or_commit(self):
        self.wal_pending()
        baseline = f.m.raw_pair(self.c.db)
        with self.assertRaisesRegex(m.Held, 'WAL-COMMIT-needs-supported-reverse-phase'):
            self.make()
        self.assertEqual(f.m.raw_pair(self.c.db), baseline)
        self.assertTrue(self.c.conn.in_transaction)
        self.assertEqual(list(self.journal.iterdir()), [])

    def test_detached_observation_late_foreign_SQL_refuses(self):
        x = self.make()
        x.commit()
        real = self.c.disk.observe_copy

        def late(*args):
            result = real(*args)
            self.c.conn.execute("UPDATE BOOK SET NAME='foreign-late' WHERE ID='correct-0'")
            self.c.conn.commit()
            return result
        with patch.object(self.c.disk, 'observe_copy', side_effect=late):
            with self.assertRaises(m.Held):
                x.close_committed(self.batch)
        self.assertEqual(self.c.conn.execute("SELECT NAME FROM BOOK WHERE ID='correct-0'").fetchone()[0], 'foreign-late')

    def test_last_detached_observation_scratch_alias_refuses(self):
        x = self.make()
        x.commit()
        real = self.c.disk.observe_copy
        scratch = self.reader.scratch
        saved = scratch.with_name('scratch-saved')

        def late(*args):
            result = real(*args)
            scratch.rename(saved)
            scratch.symlink_to(saved, target_is_directory=True)
            return result
        with patch.object(self.c.disk, 'observe_copy', side_effect=late):
            with self.assertRaises(m.Held):
                x.close_committed(self.batch)

    def test_literal_second_precommit_last_ancestor_helper_mode_no_COMMIT(self):
        x = self.make()
        real = m.s5
        count = 0
        target = 2 * len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            count += 1
            if count == target:
                self.c.db.chmod(416)
                fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.commit()
        self.assertTrue(fired)
        self.assertTrue(self.c.conn.in_transaction)
        self.assertEqual(x.phase, 'commit-uncertain')
        self.assertFalse((self.journal / 'committed.json').exists())

    def test_final_helper_missing_companion_creation_no_COMMIT(self):
        x = self.make()
        real = m.s5
        count = 0
        target = len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            count += 1
            if count == target:
                Path(str(self.c.db) + '-wal').write_bytes(b'foreign')
                fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.commit()
        self.assertTrue(fired)
        self.assertTrue(self.c.conn.in_transaction)

    def test_commit_uncertain_state_seal_callback_precedes_final_closure(self):
        x = self.make()
        real = x._state
        fired = []

        def late():
            result = real()
            if not fired and x.phase == 'commit-uncertain':
                self.reader.tasks_database.chmod(416)
                fired.append(True)
            return result
        with patch.object(x, '_state', side_effect=late), self.assertRaises(ValueError):
            x.commit()
        self.assertTrue(fired)
        self.assertTrue(self.c.conn.in_transaction)

    def test_last_ancestor_helper_pre_reverse_BEGIN_no_SQL(self):
        x = self.make()
        x.commit()
        real = m.s5
        count = 0
        target = len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            if x.phase == 'reverse-uncertain':
                count += 1
                if count == target:
                    self.c.db.chmod(416)
                    fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.reverse()
        self.assertTrue(fired)
        self.assertEqual(self.sql.logical(), self.c.after)
        self.assertFalse(self.c.conn.in_transaction)
        self.assertFalse((self.journal / 'reversed.json').exists())

    def test_last_ancestor_helper_pre_reverse_COMMIT_rolls_back_pending_body(self):
        x = self.make()
        x.commit()
        real = m.s5
        count = 0
        target = 3 * len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            if x.phase == 'reverse-uncertain':
                count += 1
                if count == target:
                    self.reader.tasks_database.chmod(416)
                    fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.reverse()
        self.assertTrue(fired)
        self.assertEqual(self.sql.logical(), self.c.after)
        self.assertFalse((self.journal / 'reversed.json').exists())

    def test_last_helper_after_committed_file_checks_no_final_ACK(self):
        x = self.make()
        x.commit()
        real = m.s5
        count = 0
        target = len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            count += 1
            if count == target:
                self.reader.tasks_database.chmod(416)
                fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.close_committed(self.batch)
        self.assertTrue(fired)

    def test_last_helper_foreign_journal_child_no_COMMIT(self):
        x = self.make()
        real = m.s5
        count = 0
        target = len(set(x.sql.nodes) | set(x.nodes))
        fired = []

        def late(z):
            nonlocal count
            result = real(z)
            count += 1
            if count == target:
                (self.journal / 'foreign').write_bytes(b'keep')
                fired.append(True)
            return result
        with patch.object(m, 's5', side_effect=late), self.assertRaises(m.Held):
            x.commit()
        self.assertTrue(fired)
        self.assertTrue(self.c.conn.in_transaction)

    def test_last_immutable_helper_cannot_rebase_admitted_ancestor_vector(self):
        import inspect
        x = self.make()
        real = x._life
        fired = []
        p = self.reader.scratch

        def late():
            result = real()
            if not fired and any((frame.function == '_direct' for frame in inspect.stack())):
                p.chmod(488)
                z = p.lstat()
                x.nodes[p][:] = [z.st_dev, z.st_ino, z.st_mode, z.st_uid, z.st_gid]
                fired.append(True)
            return result
        with patch.object(x, '_life', side_effect=late), self.assertRaises(m.Held):
            x.commit()
        self.assertTrue(fired)
        self.assertTrue(self.c.conn.in_transaction)
if __name__ == '__main__':
    unittest.main()

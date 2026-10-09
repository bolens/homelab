"""Disposable tests use real repository Controller/Writer, mocked census reads.

They do not assert installed image admission or construct a live capability.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
from pathlib import Path
import sys
import shutil
import tempfile
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(_PORTABLE_ROOT))
import publication_api as api
import publication_guard as guard
import media_writer as writers
SOURCE = Path(str(_PORTABLE_ROOT / 'publication_reader_native_coordinator.py'))
spec = importlib.util.spec_from_file_location('coordinator_fixture', SOURCE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class CoordinatorTests(unittest.TestCase):

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='reader-coordinator-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(448)
        self.data = self.root / 'data'
        self.data.mkdir(mode=448)
        self.library = self.root / 'library'
        self.library.mkdir(mode=448)
        self.writer_root = self.data / 'media-writer'
        self.writer_root.mkdir(mode=448)
        for p, raw in ((self.writer_root / 'writer-v1.lock', writers.PROTOCOL), (self.writer_root / 'publication-v1.json', b'{}'), (self.data / 'workflow.sqlite', b'fixture'), (self.data / 'mylar.db', b'fixture')):
            p.write_bytes(raw)
            p.chmod(384)
        self.controller = api.Controller(self.data, [str(self.library)])
        self.writer = writers.Writer(self.writer_root, create=False)
        self.modules = patch.object(m, 'sdk', return_value=(api, writers, guard))
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.snapshot = patch.object(guard, 'media_snapshot', return_value=({'version': 1}, {}))
        self.snapshot.start()
        self.addCleanup(self.snapshot.stop)

    def terminal_fixture(self, c, rollback=False, prove=None):

        class Aggregate:

            def _life(self):
                pass

        class Terminal:

            def _prove(self):
                if prove is not None:
                    prove()
        batch = SimpleNamespace(controller=self.controller, writer=self.writer, preparations=())
        reader = SimpleNamespace(original=SimpleNamespace(_coordinator=c), preparations=())
        reservation = SimpleNamespace(batch=batch, reader=reader)
        a = Aggregate()
        a.reader = reader
        a.reservation = reservation
        a.phase = 'rollback-terminal' if rollback else 'terminal'
        a.terminal = Terminal()
        a.terminal.phase = 'complete'
        a.terminal.batch = batch
        a.terminal.reservation = reservation
        a.terminal.writer = self.writer
        modules = {'publication_negative_aggregate': SimpleNamespace(NegativeReaderAggregate=Aggregate), 'publication_negative_batch_terminal': SimpleNamespace(TerminalClearance=Terminal), 'publication_negative_batch_rollback_terminal': SimpleNamespace(RollbackClearance=Terminal)}
        return (a, modules)

    def test_held_factory_never_reacquires_writer(self):
        with self.writer.hold(timeout=0):
            with patch.object(writers.Writer, 'hold', side_effect=AssertionError('nested hold')):
                c = m.from_held_existing(self.controller, self.writer)
                c.revalidate()
                c._open = False

    def test_held_factory_requires_actual_held_writer(self):
        with self.assertRaisesRegex(m.Held, 'raw-writer-not-held'):
            m.from_held_existing(self.controller, self.writer)

    def test_terminal_success_does_not_reseal_changed_namespace(self):
        with self.writer.hold(timeout=0):
            c = m.from_held_existing(self.controller, self.writer)
            old = dict(c._files)
            (self.library / 'legitimate-fixture-change').write_bytes(b'fixture')
            a, modules = self.terminal_fixture(c)
            with patch.object(m, 'installed_component', side_effect=modules.__getitem__):
                c.close_owned_terminal(a)
                c._open = True
                with self.assertRaisesRegex(m.Held, 'coordinator-lifetime'):
                    c.close_owned_terminal(a)
            self.assertEqual(c._files, old)

    def test_terminal_rollback_consumes_only_after_owning_proof(self):
        with self.writer.hold(timeout=0):
            c = m.from_held_existing(self.controller, self.writer)
            seen = []
            a, modules = self.terminal_fixture(c, True, lambda: seen.append('proof'))
            with patch.object(m, 'installed_component', side_effect=modules.__getitem__):
                c.close_owned_terminal(a)
            self.assertEqual(seen, ['proof'])
            self.assertFalse(c._open)

    def test_terminal_proof_failure_retains_coordinator(self):
        with self.writer.hold(timeout=0):
            c = m.from_held_existing(self.controller, self.writer)

            def failure():
                raise m.Held('fixture-terminal-drift')
            a, modules = self.terminal_fixture(c, prove=failure)
            with patch.object(m, 'installed_component', side_effect=modules.__getitem__):
                with self.assertRaisesRegex(m.Held, 'fixture-terminal-drift'):
                    c.close_owned_terminal(a)
            self.assertTrue(c._open)

    def test_uncompleted_or_foreign_aggregate_cannot_close(self):
        with self.writer.hold(timeout=0):
            c = m.from_held_existing(self.controller, self.writer)
            a, modules = self.terminal_fixture(c)
            with patch.object(m, 'installed_component', side_effect=modules.__getitem__):
                a.phase = 'sources-retained'
                with self.assertRaisesRegex(m.Held, 'aggregate-terminal-required'):
                    c.close_owned_terminal(a)
                a.phase = 'terminal'
                a.reader.original._coordinator = object()
                with self.assertRaisesRegex(m.Held, 'same-owning-coordinator-successor'):
                    c.close_owned_terminal(a)
            self.assertTrue(c._open)

    def test_mutable_file_baseline_cannot_reseal_replaced_catalog(self):
        with self.assertRaisesRegex(m.Held, 'coordinator-lifetime'):
            with m.hold_existing(self.controller, self.writer) as c:
                db = self.controller.native_database
                replacement = self.root / 'replacement'
                shutil.copy2(db, replacement)
                replacement.replace(db)
                c._files[db] = m.signature(db)
                c._files[self.data] = m.signature(self.data)
                c.revalidate()

    def test_mutable_census_baseline_cannot_reseal(self):
        with self.assertRaisesRegex(m.Held, 'coordinator-lifetime'):
            with m.hold_existing(self.controller, self.writer) as c:
                c._census['revision'] = 999
                c.revalidate()

    def test_real_existing_writer_and_controller(self):
        with m.hold_existing(self.controller, self.writer) as c:
            self.assertEqual(c.native_pair(), (self.controller, self.writer))
            self.assertFalse(c.binding['mutation_authority'])
            self.assertFalse(c.binding['reader_admission'])
        self.assertEqual(self.writer.local[1].depth, 0)

    def test_actual_native_catalog_0644_preserved(self):
        self.controller.native_database.chmod(420)
        with m.hold_existing(self.controller, self.writer) as c:
            c.revalidate()
        self.assertEqual(self.controller.native_database.stat().st_mode & 511, 420)

    def test_authority_database_0644_held(self):
        self.controller.database.chmod(420)
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer):
                pass

    def test_native_catalog_world_write_held(self):
        self.controller.native_database.chmod(438)
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer):
                pass

    def test_fresh_wrapper_same_registry_is_legitimate(self):
        with m.hold_existing(self.controller, self.writer) as c:
            other = writers.Writer(self.writer_root, create=False)
            self.assertIsNot(other, self.writer)
            self.assertIs(other.local, self.writer.local)
            self.assertEqual(guard.writer_identity(other), c.binding['writer_identity'])
            c.revalidate()

    def test_no_caller_mint(self):
        with self.assertRaises(m.Held):
            m.NativeReadCoordinator(None, self.controller, self.writer, (api, writers, guard))

    def test_subclass_controller_rejected(self):

        class Sub(api.Controller):
            pass
        with self.assertRaises(m.Held):
            with m.hold_existing(Sub(self.data, [str(self.library)]), self.writer):
                pass

    def test_missing_lock_never_created(self):
        self.writer.lock.unlink()
        with self.assertRaises((ValueError, OSError)):
            with m.hold_existing(self.controller, self.writer):
                pass
        self.assertFalse(self.writer.lock.exists())

    def test_pending_not_permitted(self):
        p = self.writer.pending
        p.write_bytes(writers.PROTOCOL)
        p.chmod(384)
        with self.assertRaises(writers.Busy):
            with m.hold_existing(self.controller, self.writer):
                pass

    def test_controller_paths_changed(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                self.controller.roots.append('/foreign')
                c.revalidate()

    def test_mutated_writer_root(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                self.writer.root = self.library
                c.close_passive()

    def test_mutated_pending_path(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                self.writer.pending = self.library / 'foreign'
                c.close_passive()

    def test_lock_replacement(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                self.writer.lock.rename(self.writer_root / 'retained-lock')
                self.writer.lock.write_bytes(writers.PROTOCOL)
                self.writer.lock.chmod(384)
                c.close_passive()

    def test_callback_late_control_mode(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:

                def altered(*args):
                    self.controller.native_database.chmod(416)
                    return ({'version': 1}, {})
                with patch.object(guard, 'media_snapshot', side_effect=altered):
                    c.revalidate()

    def test_callback_new_sidecar(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:

                def altered(*args):
                    Path(str(self.controller.native_database) + '-wal').write_bytes(b'late')
                    return ({'version': 1}, {})
                with patch.object(guard, 'media_snapshot', side_effect=altered):
                    c.revalidate()

    def test_ancestor_rebuild_unchanged_leaves(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                old = self.data
                moved = self.root / 'retained'
                old.rename(moved)
                old.mkdir(mode=448)
                for p in list(moved.iterdir()):
                    p.rename(old / p.name)
                c.close_passive()

    def test_other_thread_cannot_reuse(self):
        with m.hold_existing(self.controller, self.writer) as c:
            errors = []

            def run():
                try:
                    c.close_passive()
                except m.Held as exc:
                    errors.append(str(exc))
            t = threading.Thread(target=run)
            t.start()
            t.join()
            self.assertEqual(errors, ['coordinator-lifetime'])

    def test_expired_context(self):
        with m.hold_existing(self.controller, self.writer) as c:
            pass
        with self.assertRaises(m.Held):
            c.close_passive()

    def test_binding_copy_cannot_rewrite_census(self):
        with m.hold_existing(self.controller, self.writer) as c:
            b = c.binding
            b['census']['version'] = 99
            self.assertEqual(c.binding['census']['version'], 1)

    def test_census_change(self):
        with self.assertRaises(m.Held):
            with m.hold_existing(self.controller, self.writer) as c:
                with patch.object(guard, 'media_snapshot', return_value=({'version': 2}, {})):
                    c.revalidate()

    def test_no_native_lifecycle_flags_touched(self):
        with m.hold_existing(self.controller, self.writer):
            pass
        self.assertFalse(self.writer.local[1].allow_pending)
        self.assertFalse(self.writer.local[1].allow_tagger_pending)
        self.assertFalse(self.writer.local[1].allow_release_pending)
if __name__ == '__main__':
    unittest.main()

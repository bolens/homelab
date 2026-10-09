"""Prospective admission + actual local split-link mechanics. No native grants."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import os
from pathlib import Path
import tempfile
import sys
import types
import unittest
import zipfile
from unittest.mock import patch
P = Path(str(_PORTABLE_ROOT / 'publication_negative_phase.py'))
s = importlib.util.spec_from_file_location('negative_phase_fixture', P)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)
ns = importlib.util.spec_from_file_location('fixture_loader', str(_PORTABLE_ROOT / 'publication_negative_namespace.py'))
loader = importlib.util.module_from_spec(ns)
ns.loader.exec_module(loader)

def fixture_kernel():
    if m.KERNEL_SHA != loader.KERNEL_SHA:
        raise m.Held('kernel-pin')
    return loader._load(Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py')), m.KERNEL_SHA)

class PhaseTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='comic-hardlink-fixture-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(448)
        for name in ('library', 'private', 'journal'):
            (self.root / name).mkdir(mode=448)
        self.lock = self.root / 'lease.lock'
        self.lock.write_bytes(b'fixture')
        self.lock.chmod(384)
        self.source = self.root / 'library/source.bin'
        self.source.write_bytes(b'original preserved fixture')
        os.setxattr(self.source, 'user.fixture', b'keep')
        self.target = self.root / 'private/retained.bin'
        self.marker = self.root / m.NAME
        fixture = patch.object(m, 'kernel', side_effect=fixture_kernel)
        fixture.start()
        self.addCleanup(fixture.stop)
        self.km = m.kernel()

    def adapter(self):
        return self.km.LocalFixtureAdapter(self.root)

    def marker_write(self, body=None):
        body = body or dict(version=1, protocol=m.PROTOCOL, nonce='a' * 64, binding_sha256='b' * 64, journal=str(self.root / 'journal'))
        self.marker.write_bytes(m.compact(body))
        self.marker.chmod(384)

    def test_only_terminal_successor_never_ordinary_grant(self):
        marker = self.root / 'negative-retirement-v1.terminal-pending'
        marker.write_bytes(b'{')
        with self.assertRaisesRegex(m.Held, 'terminal-pending-held'):
            m.admission(self.root)

    def test_successor_directory_never_ordinary_grant(self):
        (self.root / 'negative-retirement-v1.terminal-pending').mkdir()
        with self.assertRaisesRegex(m.Held, 'terminal-pending-held'):
            m.admission(self.root)

    def test_absent_marker_no_creation(self):
        m.admission(self.root)
        self.assertFalse(self.marker.exists())

    def test_valid_pending_never_ordinary_grant(self):
        self.marker_write()
        with self.assertRaisesRegex(m.Held, 'pending-held'):
            m.admission(self.root)

    def test_malformed_json_ordinary_held(self):
        self.marker.write_text('{')
        self.marker.chmod(384)
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_true_version_held(self):
        self.marker_write(dict(version=True, protocol=m.PROTOCOL, nonce='a' * 64, binding_sha256='b' * 64, journal=str(self.root / 'journal')))
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_unknown_marker_field_held(self):
        self.marker_write(dict(version=1, protocol=m.PROTOCOL, nonce='a' * 64, binding_sha256='b' * 64, journal=str(self.root / 'journal'), complete=True))
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_mode_public_held(self):
        self.marker_write()
        self.marker.chmod(420)
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_symlink_marker_held(self):
        p = self.root / 'foreign'
        p.write_text('{}')
        self.marker.symlink_to(p)
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_hardlinked_marker_held(self):
        self.marker_write()
        os.link(self.marker, self.root / 'alias')
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_duplicate_protocol_field_held(self):
        self.marker.write_text('{"version":1,"version":1}')
        self.marker.chmod(384)
        with self.assertRaisesRegex(m.Held, 'malformed-held'):
            m.admission(self.root)

    def test_staged_pair_keeps_source_before_SQL(self):
        with self.adapter() as k:
            before = self.km._fact(self.source, 1)
            t = m.SplitTransition(m._KEY, k)
            ack = t.stage()
            self.assertTrue(self.source.exists())
            self.assertTrue(self.target.exists())
            self.assertEqual(self.source.stat().st_nlink, 2)
            self.assertEqual(self.source.stat().st_ino, self.target.stat().st_ino)
            self.assertTrue(self.km._preserved(self.km._fact(self.source, 2), before, 2))
            self.assertFalse(ack['native_grant'])
            self.assertEqual([r[0]['phase'] for r in k._rows()], ['prepared', 'link-intent', 'linked'])

    def test_staging_rollback_retains_original_attributes(self):
        with self.adapter() as k:
            before = self.km._fact(self.source, 1)
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            ack = t.abandon_staging()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())
            self.assertTrue(ack['staging_rollback_verified'])
            self.assertTrue(self.km._preserved(self.km._fact(self.source, 1), before, 1))

    def test_json_reader_receipt_cannot_retire(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            with self.assertRaisesRegex(m.Held, 'owning-native'):
                t.retire({'reader_preserved': True})
            self.assertTrue(self.source.exists())
            self.assertEqual(self.source.stat().st_nlink, 2)

    def test_local_fixture_cannot_retire(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            with self.assertRaises(m.Held):
                t.retire(True)
            self.assertTrue(self.source.exists())

    def test_foreign_destination_preserved(self):
        self.target.write_bytes(b'foreign')
        with self.adapter() as k:
            with self.assertRaises(self.km.Held):
                m.SplitTransition(m._KEY, k)
        self.assertEqual(self.target.read_bytes(), b'foreign')
        self.assertTrue(self.source.exists())

    def test_stage_twice_no_replay(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            with self.assertRaises(m.Held):
                t.stage()

    def test_foreign_source_prevents_staging_rollback_unlink(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            self.source.unlink()
            self.source.write_bytes(b'foreign')
            with self.assertRaises(self.km.Held):
                t.abandon_staging()
            self.assertEqual(self.source.read_bytes(), b'foreign')
            self.assertTrue(self.target.exists())

    def test_foreign_private_alias_prevents_rollback(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            self.target.unlink()
            self.target.write_bytes(b'foreign')
            with self.assertRaises(self.km.Held):
                t.abandon_staging()
            self.assertTrue(self.source.exists())
            self.assertEqual(self.target.read_bytes(), b'foreign')

    def test_unknown_journal_child_before_stage_retains_source(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            (self.root / 'journal/foreign.json').write_text('{}')
            with self.assertRaises(self.km.Held):
                t.stage()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())

    def test_lost_staging_ACK_remains_held_not_replayed(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            t.stage()
            pending = k.inspect_pending()
            self.assertTrue(pending['held'])
            self.assertFalse(pending['automatic_replay'])
            self.assertEqual(pending['phase'], 'linked')

    def test_parent_alias_before_stage_holds(self):
        with self.adapter() as k:
            t = m.SplitTransition(m._KEY, k)
            library = self.root / 'library'
            library.rename(self.root / 'retained-library')
            library.symlink_to(self.root / 'retained-library')
            with self.assertRaises(self.km.Held):
                t.stage()
            self.assertFalse(self.target.exists())

    def test_forged_phase_factory_key_refused(self):
        with self.adapter() as k:
            with self.assertRaises(m.Held):
                m.SplitTransition(None, k)

    def test_kernel_source_replacement_held(self):
        with patch.object(m, 'KERNEL_SHA', '0' * 64):
            with self.assertRaisesRegex(m.Held, 'kernel-pin'):
                m.kernel()

    def test_new_shared_marker_survives_independent_read(self):
        self.marker_write()
        raw = self.marker.read_bytes()
        with self.assertRaises(m.Held):
            m.admission(self.root)
        self.assertEqual(self.marker.read_bytes(), raw)

    def test_no_SQL_or_native_initialization_dependency(self):
        raw = P.read_text()
        self.assertNotIn('sqlite3.connect', raw)
        self.assertNotIn('_LOCAL', raw)
        self.assertNotIn('Store(', raw)
        self.assertNotIn('create=True', raw)

class NativeFenceFixtureTests(unittest.TestCase):
    """Real disposable native proofs; reader phase is explicit future-interface mock."""

    def setUp(self):
        fixture = patch.object(m, 'kernel', side_effect=fixture_kernel)
        fixture.start()
        self.addCleanup(fixture.stop)
        spec = importlib.util.spec_from_file_location('negative_full_fixture', str(_PORTABLE_ROOT / 'fixtures/test_publication_negative_v4.py'))
        self.f = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.f)
        self.c = self.f.Controls()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.neg = self.f.m
        self.root = self.c.root
        self.c.controller = self.f.api.Controller(self.root, [self.c.library], tool_root=self.f.g.TOOL_ROOT)
        self.journal = self.root / 'phase-journal'
        self.journal.mkdir(mode=448)
        self.private = self.root / 'quarantine'
        self.private.mkdir(mode=448)
        import media_writer
        self.writers = media_writer
        self.sdkpatch = patch.object(self.neg, '_sdk', return_value=(self.f.api, media_writer))
        self.sdkpatch.start()
        self.addCleanup(self.sdkpatch.stop)

        class ReaderPhase:

            def __init__(self):
                self.committed = False

            def revalidate_before_native(self, preparation):
                preparation.revalidate()

            def close_native_phase_passive(self, fence):
                pass

            def native_syscall_controls(self, fence):
                return ({}, {})

            def revalidate_committed(self, fence):
                m.check(self.committed, 'reader-not-committed')

            def revalidate_rollback_ready(self, fence):
                m.check(not self.committed, 'reader-rollback-not-ready')
        self.reader = ReaderPhase()
        module = types.ModuleType('mylar.publication_reader_phase')
        module.__file__ = '/app/mylar3/mylar/publication_reader_phase.py'
        module.StoppedReaderPhase = ReaderPhase
        ctx = patch.dict(sys.modules, {'mylar.publication_reader_phase': module})
        ctx.start()
        self.addCleanup(ctx.stop)

    def make(self):
        prep = self.neg.prepare_existing(self.c.controller, self.c.writer, self.c.wrong, self.c.owner, self.c.source, self.c.retained, self.c.restore)
        return m.NativePhaseFence(m._KEY, prep, self.reader, self.journal, 'a' * 64, (self.f.api, self.writers, self.f.g, self.neg))

    def test_real_native_proof_and_durable_pending(self):
        with self.c.writer.hold():
            fence = self.make()
            fence.check()
            with self.assertRaises(m.Held):
                m.admission(self.c.writer.root)
            self.assertTrue((self.c.writer.root / m.NAME).exists())

    def test_source_changed_during_prepared_kernel_cannot_stage(self):
        with self.c.writer.hold():
            fence = self.make()
            real = m.SplitTransition

            def altered(key, k):
                self.c.wrong.write_bytes(b'foreign source')
                return real(key, k)
            with patch.object(m, 'SplitTransition', side_effect=altered):
                with self.assertRaises(m.Held):
                    m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertTrue(self.c.wrong.exists())
            self.assertFalse((self.private / 'retained.cbz').exists())

    def test_real_native_phase_stages_but_uncommitted_reader_cannot_retire(self):
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertEqual(self.c.wrong.stat().st_nlink, 2)
            with self.assertRaises(m.Held):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())

    def test_correct_archive_drift_after_stage_holds_before_unlink(self):
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            with zipfile.ZipFile(self.c.source, 'a') as archive:
                archive.comment = b'changed correct archive'
            self.reader.committed = True
            with self.assertRaises((m.Held, self.f.g.Unavailable)):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())
            self.assertTrue((self.private / 'retained.cbz').exists())

    def test_retained_original_drift_after_stage_holds(self):
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.c.retained.write_bytes(b'changed retained backup')
            self.reader.committed = True
            with self.assertRaises(m.Held):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())

    def test_fence_replacement_cannot_be_adopted(self):
        with self.c.writer.hold():
            fence = self.make()
            p = self.c.writer.root / m.NAME
            q = self.root / 'replacement'
            q.write_bytes(p.read_bytes())
            q.chmod(384)
            q.replace(p)
            with self.assertRaises(m.Held):
                fence.check()

    def test_native_syscall_last_reader_callback_correct_change_holds_link(self):
        with self.c.writer.hold():
            fence = self.make()

            def altered(f):
                with zipfile.ZipFile(self.c.source, 'a') as archive:
                    archive.comment = b'late-correct'
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertTrue(self.c.wrong.exists())
            self.assertFalse((self.private / 'retained.cbz').exists())

    def test_native_syscall_last_reader_callback_custody_change_holds_retire(self):
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.reader.committed = True

            def altered(f):
                self.c.retained.write_bytes(b'late changed backup')
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())
            self.assertTrue((self.private / 'retained.cbz').exists())

    def test_last_reader_callback_foreign_source_child_holds_before_link(self):
        with self.c.writer.hold():
            fence = self.make()

            def altered(f):
                (self.c.wrong.parent / 'foreign-late.cbz').write_bytes(b'foreign')
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertFalse((self.private / 'retained.cbz').exists())
            self.assertEqual(self.c.wrong.stat().st_nlink, 1)

    def test_last_reader_callback_foreign_journal_holds_before_unlink(self):
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.reader.committed = True

            def altered(f):
                (self.journal / 'foreign.json').write_bytes(b'foreign')
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())
            self.assertEqual(self.c.wrong.stat().st_nlink, 2)

    def test_last_reader_callback_ancestor_override_held(self):
        with self.c.writer.hold():
            fence = self.make()
            p = next(iter(fence.nodes))
            self.reader.native_syscall_controls = lambda f: ({}, {p: (0, 0, 0, 0, 0)})
            with self.assertRaisesRegex(m.Held, 'conflicting-phase-reader-ancestor'):
                m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertFalse((self.private / 'retained.cbz').exists())

    def test_constructor_cannot_refresh_reviewed_catalog_baseline(self):
        import inspect
        with self.c.writer.hold():
            real = self.f.g.registry_snapshot
            fired = False

            def changed(*args, **kw):
                nonlocal fired
                value = real(*args, **kw)
                if not fired and any((frame.function == '__init__' and frame.code_context and ('self.census,self.records=' in frame.code_context[0]) for frame in inspect.stack())):
                    fired = True
                    self.c.sql('INSERT INTO comics VALUES (?,?,?)', ('foreign-parent', str(self.c.library), 'Active'))
                return value
            with patch.object(self.f.g, 'registry_snapshot', side_effect=changed):
                with self.assertRaisesRegex(m.Held, 'prepared-complete-catalog-CAS'):
                    self.make()
            self.assertTrue(fired)
            self.assertFalse((self.c.writer.root / m.NAME).exists())

    def shadow_claim(self):
        other = self.root / 'other-library'
        other.mkdir(mode=448)
        shadow = other / 'shadow.cbz'
        self.c.sql('INSERT INTO comics VALUES (?,?,?)', ('shadowparent', str(other), 'Active'))
        self.c.sql('INSERT INTO issues VALUES (?,?,?,?)', ('shadowissue', 'shadowparent', shadow.name, 'Wanted'))
        self.c.controller = self.f.api.Controller(self.root, [self.c.library, other], tool_root=self.f.g.TOOL_ROOT)
        return shadow

    def test_final_reader_cross_library_shadow_alias_holds_before_link(self):
        shadow = self.shadow_claim()
        with self.c.writer.hold():
            fence = self.make()

            def altered(f):
                os.symlink(self.c.wrong, shadow)
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                m.stage_existing(fence, self.private / 'retained.cbz')
            self.assertFalse((self.private / 'retained.cbz').exists())
            self.assertEqual(self.c.wrong.stat().st_nlink, 1)
            self.assertTrue(shadow.is_symlink())

    def test_final_reader_cross_library_shadow_alias_holds_before_retire(self):
        shadow = self.shadow_claim()
        with self.c.writer.hold():
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.reader.committed = True

            def altered(f):
                os.symlink(self.c.wrong, shadow)
                return ({}, {})
            self.reader.native_syscall_controls = altered
            with self.assertRaises(m.Held):
                reservation.consume_native(fence.preparation)
            self.assertTrue(self.c.wrong.exists())
            self.assertEqual(self.c.wrong.stat().st_nlink, 2)
            self.assertTrue((self.private / 'retained.cbz').exists())

    def test_reader_mock_committed_retire_keeps_durable_native_hold(self):
        with self.c.writer.hold():
            before = self.c.wrong.read_bytes()
            fence = self.make()
            reservation = m.stage_existing(fence, self.private / 'retained.cbz')
            self.reader.committed = True
            ack = reservation.consume_native(fence.preparation)
            self.assertFalse(self.c.wrong.exists())
            self.assertEqual((self.private / 'retained.cbz').read_bytes(), before)
            self.assertTrue(ack['negative_fence_retained'])
            self.assertFalse(ack['operation_verified'])
            with self.assertRaises(m.Held):
                m.admission(self.c.writer.root)

    def test_native_baseline_mutation_sealed(self):
        with self.c.writer.hold():
            fence = self.make()
            fence.native_control[self.c.database] = m.sig(self.c.database)
            fence.census['revision'] = 999
            with self.assertRaises(m.Held):
                fence.check()

    def test_foreign_writer_namespace_hold(self):
        with self.c.writer.hold():
            fence = self.make()
            (self.c.writer.root / 'foreign').write_bytes(b'foreign')
            with self.assertRaises(m.Held):
                fence.check()
if __name__ == '__main__':
    unittest.main()

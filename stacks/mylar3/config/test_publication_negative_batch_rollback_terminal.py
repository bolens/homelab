"""Actual disposable SQLite rollback/reverse + five files; EXPLICIT fake SDK handshake.

Public exact installed factories refuse these fixture adapters. No live/reader grant.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import importlib.util
import os
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m
f = load('native_fixture', str(_PORTABLE_ROOT / 'fixtures/test_publication_negative_batch_transition_v5.py'))
sql = load('SQL_fixture', str(_PORTABLE_ROOT / 'fixtures/test_publication_reader_sql_commit_v3.py'))
m = load('rollback_terminal', str(_PORTABLE_ROOT / 'publication_negative_batch_rollback_terminal.py'))

class Controls(unittest.TestCase):

    def setUp(self):
        self.f = f.Tests()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.shadow = self.f.c.root / 'shadow.cbz'
        for p in self.f.c.preps:
            p.binding['complete_catalog_absence']['passive_claim_files'][str(self.shadow)] = None
        self.r = self.f.make()
        self.r.stage_all()
        self.s = sql.Tests()
        self.s.setUp()
        self.addCleanup(self.s.doCleanups)

    def original(self):
        self.s.sql.rollback_owned()
        self.r.rollback_staging()
        r = self.r
        s = self.s
        reader = r.reader

        def close(reservation):
            m.check(reservation is r and s.sql.phase == 'rolled-back' and (not s.c.conn.in_transaction), 'fixture-owned-original-rollback')
            s.sql.close_passive()
            m.check(s.sql.logical() == s.c.before, 'fixture-original-all-tables')
            files = {s.sql.parent: s.sql.directory, **{s.sql.parent / name: v for name, v in s.sql.names.items()}}
            nodes = s.sql.nodes
            for suffix in ('', '-journal', '-wal', '-shm'):
                files[Path(str(s.sql.db) + suffix)] = s.sql.pending[suffix]['signature9'] if suffix in s.sql.pending else None
            for suffix in ('', '-journal', '-wal', '-shm'):
                files[Path(str(s.reader.tasks_database) + suffix)] = s.reader.tasks_pair[suffix]['signature9'] if suffix in s.reader.tasks_pair else None
            return (copy.deepcopy(files), copy.deepcopy(nodes))
        reader.close_original_rollback = close

        def binding(reservation):
            close(reservation)
            return dict(phase='rolled-back', reservation_id=id(r), preparation_ids=list(map(id, r.batch.preparations)), before=copy.deepcopy(s.c.before), main_pair=copy.deepcopy(s.sql.pending), tasks_pair=copy.deepcopy(s.reader.tasks_pair), sql_phase=s.sql.phase)
        reader.original_rollback_binding = binding
        return m.RollbackClearance(m._KEY, r, reader, 'original')

    def reversed(self):
        x = self.s.make()
        x.commit()
        self.f.c.reader.revalidate_committed = lambda f: None
        self.r.retire_all()
        x.reverse()
        self.r.rollback_staging()
        r = self.r

        class ExactFixtureAdapter:
            reservation = r
            reader = r.reader

            @property
            def binding(proof):
                out = copy.deepcopy(x.binding)
                out['reservation_id'] = id(r)
                out['preparation_ids'] = list(map(id, r.batch.preparations))
                return out

            def close_reversed(proof, reservation):
                m.check(reservation is r, 'fixture-exact-reverse-reservation')
                return x.close_reversed(x.reservation)
        self.x = x
        self.proof = ExactFixtureAdapter()
        return m.RollbackClearance(m._KEY, r, self.proof, 'reversed')

    def assert_originals(self, t):
        self.assertEqual(t.projection.phases, ['source'] * 5)
        for i, member in enumerate(t.projection.members):
            self.assertEqual(Path(member['source']).stat().st_nlink, 1)
            self.assertFalse(Path(member['target']).exists())
            self.assertEqual(t.projection.k._fact(Path(member['source']), 1), t.projection.facts[i])

    def test_owned_pending_SQLrollback_plus5stagedrollback_clear(self):
        t = self.original()
        self.assert_originals(t)
        ack = t.clear()
        self.assertTrue(ack['rollback_verified'])
        self.assertTrue(ack['reader_before_verified'])
        self.assertEqual(ack['restored_count'], 5)
        self.assertFalse(ack['publication_acceptance'])
        self.assertFalse(t.marker.exists())
        self.assertFalse((t.writer.root / m.SUCCESSOR).exists())
        self.assertEqual(self.s.sql.logical(), self.s.c.before)
        self.assertFalse(self.s.c.conn.in_transaction)

    def test_real_committed_SQLreverse_plus5retained_restore_clear(self):
        t = self.reversed()
        self.assert_originals(t)
        self.assertEqual(self.s.sql.logical(), self.s.c.before)
        self.assertEqual(t.clear()['outcome'], 'cleared')
        self.assertFalse(t.marker.exists())
        self.assertFalse((t.writer.root / m.SUCCESSOR).exists())

    def test_pending_status_preserves_hold(self):
        t = self.original()
        self.assertEqual(t.status()['outcome'], 'retained-pending')
        self.assertTrue(t.marker.exists())
        self.assertFalse(t.directory.exists())

    def test_no_replay_after_clear(self):
        t = self.original()
        t.clear()
        with self.assertRaises(m.Held):
            t.clear()

    def test_partial_five_restoration_refuses(self):
        t = self.original()
        t.projection.phases[4] = 'linked'
        with self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_unknown_SQL_pending_cannot_claim_original(self):
        t = self.original()
        self.s.sql.phase = 'writing'
        with self.assertRaises(ValueError):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_changed_reader_before_table_refuses(self):
        t = self.original()
        self.s.c.conn.execute("UPDATE BOOK SET NAME='foreign' WHERE ID='wrong-0'")
        self.s.c.conn.commit()
        with self.assertRaises(ValueError):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_reversed_reader_late_tasksmode_refuses(self):
        t = self.reversed()
        self.s.reader.tasks_database.chmod(416)
        with self.assertRaises(ValueError):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_restored_original_changed_bytes_refuses(self):
        t = self.original()
        Path(t.projection.members[0]['source']).write_bytes(b'foreign')
        with self.assertRaises(ValueError):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_foreign_target_not_overwritten_or_removed(self):
        t = self.original()
        target = Path(t.projection.members[0]['target'])
        target.write_bytes(b'foreign')
        with self.assertRaises(ValueError):
            t.clear()
        self.assertEqual(target.read_bytes(), b'foreign')
        self.assertTrue(t.marker.exists())

    def test_wrong_original_reader_binding_refuses(self):
        t = self.original()
        self.r.reader = object()
        with self.assertRaises(ValueError):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_last_reader_callback_catalogalias_holds_before_old_unlink(self):
        t = self.original()
        real = t.commit.close_original_rollback
        fired = []

        def late(r):
            result = real(r)
            if not fired:
                os.symlink(t.projection.members[0]['source'], self.shadow)
                fired.append(True)
            return result
        with patch.object(t.commit, 'close_original_rollback', side_effect=late), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue(t.marker.exists())

    def test_last_complete_direct_helper_alias_no_false_ACK(self):
        t = self.original()
        real = m.direct
        fired = []

        def late(path, expected):
            out = real(path, expected)
            if not fired and Path(path) == t.directory / 'cleared.json' and (t.phase == 'complete'):
                os.symlink(t.projection.members[0]['source'], self.shadow)
                fired.append(True)
            return out
        with patch.object(m, 'direct', side_effect=late), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())

    def test_successor_durable_when_old_unlink_loses_ACK(self):
        t = self.original()
        real = os.unlink
        fired = []

        def uncertain(path, *a, **kw):
            out = real(path, *a, **kw)
            if path == m.NAME and kw.get('dir_fd') is not None:
                fired.append(True)
                raise OSError('lost ACK')
            return out
        with patch.object(m.os, 'unlink', side_effect=uncertain), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())
        self.assertTrue((t.directory / 'clear-ready.json').exists())
        with self.assertRaises(m.Held):
            t.status()

    def test_marker_samebytes_newinode_refuses(self):
        t = self.original()
        raw = t.marker.read_bytes()
        t.marker.unlink()
        t.marker.write_bytes(raw)
        t.marker.chmod(384)
        with self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_public_original_and_reversed_factories_refuse_fakes(self):
        with self.assertRaises(m.Held):
            m.from_original(self.r, self.r.reader)
        with self.assertRaises(m.Held):
            m.from_reversed(self.r, object())

    def test_last_original_binding_callback_absent_reader_companion_holds(self):
        t = self.original()
        real = t.commit.original_rollback_binding
        fired = []

        def late(r):
            out = real(r)
            if not fired:
                Path(str(self.s.sql.db) + '-wal').write_bytes(b'foreign')
                fired.append(True)
            return out
        with patch.object(t.commit, 'original_rollback_binding', side_effect=late), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue(t.marker.exists())

    def test_actual_process_death_after_rollback_marker_unlink_keeps_successor(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = Path(tmp) / 'report.json'
            program = "\nimport importlib.util,json,os,sys\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location('fixture','__PORTABLE_COHORT__/test_publication_negative_batch_rollback_terminal.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)\nc=f.Controls();c.setUp();t=c.original()\nPath(sys.argv[1]).write_text(json.dumps(dict(roots=[str(c.f.c.root),str(c.s.c.c.root)],writer=str(t.writer.root),terminal=str(t.directory))))\nreal=os.unlink\ndef crash(name,*args,**kw):\n result=real(name,*args,**kw)\n if name==f.m.NAME:os._exit(71)\n return result\nos.unlink=crash;t.clear();os._exit(99)\n".replace('__PORTABLE_COHORT__', str(_PORTABLE_ROOT))
            out = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(report)], timeout=30)
            self.assertEqual(out.returncode, 71)
            info = json.loads(report.read_text())
            roots = list(map(Path, info['roots']))
            for root, prefix in zip(roots, ('negative-batch-prepare-fixture-', 'reader-admission-fixture-')):
                self.assertEqual(root.parent, Path(tempfile.gettempdir()))
                self.assertTrue(root.name.startswith(prefix))
            try:
                self.assertFalse((Path(info['writer']) / m.NAME).exists())
                self.assertTrue((Path(info['writer']) / m.SUCCESSOR).is_file())
                self.assertTrue((Path(info['terminal']) / 'clear-ready.json').exists())
                self.assertFalse((Path(info['terminal']) / 'cleared.json').exists())
            finally:
                for root in roots:
                    shutil.rmtree(root)

    def test_genuine_ReaderV4_beforeSQL_terminal_binding_with_all_absences(self):
        from types import SimpleNamespace
        rf = load('genuine_reader_phase', str(_PORTABLE_ROOT / 'fixtures/test_publication_reader_phase_v4.py'))
        case = rf.PhaseTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        reader = case.phase

        class Reservation:
            pass
        reservation = Reservation()
        reservation.reader = reader
        reservation.batch = SimpleNamespace(preparations=reader.preparations)
        reservation.projection = SimpleNamespace(phases=['source'] * 5)
        module = SimpleNamespace(__file__='/app/mylar3/mylar/publication_negative_batch_transition.py', NegativeBatchReservation=Reservation)
        with patch.object(rf.m.importlib, 'import_module', return_value=module):
            binding = reader.original_rollback_binding(reservation)
            files, nodes = reader.close_original_rollback(reservation)
        self.assertEqual(binding['phase'], 'before')
        self.assertIsNone(binding['sql_phase'])
        for base, pairs in ((reader.root, reader.pairs), (reader.restore, reader.custody)):
            for name, pair in pairs.items():
                for suffix in ('-wal', '-shm', '-journal'):
                    if suffix not in pair:
                        self.assertIsNone(files[Path(str(base / name) + suffix)])
if __name__ == '__main__':
    unittest.main()

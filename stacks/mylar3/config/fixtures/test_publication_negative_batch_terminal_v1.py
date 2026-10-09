"""Real five-file/marker mechanics with explicit fake SDK and commit reader.

No actual installed Controller, logical reader SQL or operational acceptance.
"""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import copy
import hashlib
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
f = load('transition_fixtures', str(_PORTABLE_ROOT / 'fixtures/test_publication_negative_batch_transition_v4.py'))
m = load('terminal_fixture', str(_PORTABLE_ROOT / 'fixtures/publication_negative_batch_terminal_v1.py'))

class Tests(unittest.TestCase):

    def setUp(self):
        self.c = f.Tests()
        self.c.setUp()
        self.addCleanup(self.c.doCleanups)
        self.shadow = self.c.c.root / 'shadow.cbz'
        for prep in self.c.c.preps:
            prep.binding['complete_catalog_absence']['passive_claim_files'][str(self.shadow)] = None
        self.r = self.c.make()
        self.r.stage_all()
        self.c.c.reader.revalidate_committed = lambda f: None
        self.r.retire_all()
        self.receipt = self.c.c.root / 'committed.json'
        self.receipt.write_bytes(b'{"phase":"committed"}')
        self.receipt.chmod(384)
        r = self.r
        receipt = self.receipt

        class Commit:
            reservation = r
            reader = r.reader

            @property
            def binding(obj):
                return copy.deepcopy(obj.bound)

            def close_committed(obj, reservation):
                m.check(reservation is r, 'exact-fixture-reservation')
                m.direct(receipt, obj.bound['receipt']['signature9'])
                m.check(hashlib.sha256(receipt.read_bytes()).hexdigest() == obj.bound['receipt']['sha256'], 'fixture-commit-receipt')
                return ({receipt: obj.bound['receipt']['signature9']}, {}, ())
        self.commit = Commit()
        self.commit.bound = dict(phase='committed', reservation_id=id(r), preparation_ids=list(map(id, r.batch.preparations)), receipt=dict(path=str(receipt), signature9=m.nine(os.lstat(receipt)), sha256=hashlib.sha256(receipt.read_bytes()).hexdigest()))

    def make(self):
        return m.TerminalClearance(m._KEY, self.r, self.commit)

    def test_pending_status_does_not_clear(self):
        t = self.make()
        self.assertEqual(t.status()['outcome'], 'retained-pending')
        self.assertTrue(t.marker.exists())
        self.assertFalse(t.directory.exists())

    def test_exact_marker_cleared_durable_completion_before_successor_removal(self):
        t = self.make()
        ack = t.clear()
        self.assertEqual(ack['outcome'], 'cleared')
        self.assertFalse(ack['publication_acceptance'])
        self.assertFalse(t.marker.exists())
        self.assertFalse((t.writer.root / m.SUCCESSOR).exists())
        self.assertEqual(set(os.listdir(t.directory)), {'clear-ready.json', 'cleared.json'})
        self.assertTrue(all((not Path(v['source']).exists() and Path(v['target']).stat().st_nlink == 1 for v in t.projection.members)))
        self.assertEqual(t.status(), ack)

    def test_no_repeat_clear_or_recreate_marker(self):
        t = self.make()
        t.clear()
        with self.assertRaises(m.Held):
            t.clear()
        self.assertFalse(t.marker.exists())

    def test_partial_not_five_retired_holds(self):
        self.r.projection.phases[0] = 'linked'
        with self.assertRaises(Exception):
            self.make()
        self.assertTrue(self.r.batch.marker.exists())

    def test_foreign_commit_reservation_holds(self):
        self.commit.reservation = object()
        with self.assertRaises(m.Held):
            self.make()

    def test_changed_original_preparation_identity_holds(self):
        t = self.make()
        self.r.batch.preparations = tuple([object(), *self.r.batch.preparations[1:]])
        with self.assertRaises(m.Held):
            t.clear()

    def test_closed_Writer_cannot_clear(self):
        t = self.make()
        self.r.batch.writer.local[1].depth = 0
        with self.assertRaises(m.Held):
            t.clear()

    def test_marker_samebytes_replacement_holds(self):
        t = self.make()
        raw = t.marker.read_bytes()
        t.marker.unlink()
        t.marker.write_bytes(raw)
        t.marker.chmod(384)
        with self.assertRaises(m.Held):
            t.clear()

    def test_marker_modified_holds_before_unlink(self):
        t = self.make()
        t.marker.write_bytes(b'foreign')
        with self.assertRaises(m.Held):
            t.clear()
        self.assertEqual(t.marker.read_bytes(), b'foreign')

    def test_retained_custody_changed_holds(self):
        t = self.make()
        Path(t.projection.members[0]['target']).write_bytes(b'foreign')
        with self.assertRaises(Exception):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_foreign_private_receipt_directory_never_overwritten(self):
        t = self.make()
        t.directory.mkdir(mode=448)
        (t.directory / 'foreign').write_bytes(b'keep')
        with self.assertRaises(FileExistsError):
            t.clear()
        self.assertEqual((t.directory / 'foreign').read_bytes(), b'keep')
        self.assertTrue(t.marker.exists())

    def test_last_committed_callback_shadow_claim_holds_before_unlink(self):
        shadow = self.shadow
        t = self.make()
        real = self.commit.close_committed
        fired = []

        def changed(r):
            vectors = real(r)
            if not fired:
                os.symlink(t.projection.members[0]['target'], shadow)
                fired.append(True)
            return vectors
        with patch.object(self.commit, 'close_committed', side_effect=changed), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue(t.marker.exists())

    def test_last_committed_callback_native_sidecar_holds(self):
        t = self.make()
        real = self.commit.close_committed

        def changed(r):
            v = real(r)
            Path(str(t.batch.controller.native_database) + '-wal').write_bytes(b'foreign')
            return v
        with patch.object(self.commit, 'close_committed', side_effect=changed), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_last_marker_read_cannot_hide_foreign_claim(self):
        t = self.make()
        real = m.read_exact
        fired = []

        def changed(p, *a):
            raw = real(p, *a)
            if Path(p) == t.marker and (not fired):
                (t.writer.root / 'foreign').write_bytes(b'foreign')
                fired.append(True)
            return raw
        with patch.object(m, 'read_exact', side_effect=changed), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue(t.marker.exists())

    def test_uncertain_unlink_restores_presence_hold_no_replay(self):
        t = self.make()
        real = os.unlink
        fired = []

        def lost(name, *a, **kw):
            result = real(name, *a, **kw)
            if name == m.NAME and (not fired):
                fired.append(True)
                raise OSError('lost unlink ACK')
            return result
        with patch.object(os, 'unlink', side_effect=lost), self.assertRaisesRegex(m.Held, 'uncertain'):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())
        self.assertTrue((t.directory / 'clear-ready.json').exists())
        with self.assertRaises(m.Held):
            t.status()
        with self.assertRaises(m.Held):
            t.clear()

    def test_crash_after_marker_unlink_has_durable_successor(self):
        t = self.make()
        real = os.unlink

        class Crash(BaseException):
            pass
        observed = []

        def crash(name, *a, **kw):
            result = real(name, *a, **kw)
            if name == m.NAME:
                observed.append(((t.writer.root / m.SUCCESSOR).exists(), (t.directory / 'clear-ready.json').exists()))
                raise Crash()
            return result
        with patch.object(os, 'unlink', side_effect=crash), self.assertRaises(m.Held):
            t.clear()
        self.assertEqual(observed, [(True, True)])

    def test_real_process_death_after_pending_unlink_stays_fenced(self):
        with tempfile.TemporaryDirectory() as report_directory:
            report = Path(report_directory) / 'report.json'
            program = "\nimport importlib.util,json,os,sys\nfrom pathlib import Path\nspec=importlib.util.spec_from_file_location('fixture','__PORTABLE_COHORT__/fixtures/test_publication_negative_batch_terminal_v1.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)\nc=f.Tests();c.setUp();t=c.make()\nPath(sys.argv[1]).write_text(json.dumps(dict(root=str(c.c.c.root),writer=str(t.writer.root),terminal=str(t.directory))))\nreal=os.unlink\ndef crash(name,*args,**kw):\n result=real(name,*args,**kw)\n if name==f.m.NAME:os._exit(71)\n return result\nos.unlink=crash;t.clear();os._exit(99)\n".replace('__PORTABLE_COHORT__', str(_PORTABLE_ROOT))
            result = subprocess.run([sys.executable, '-I', '-B', '-c', program, str(report)], timeout=30)
            self.assertEqual(result.returncode, 71)
            info = json.loads(report.read_text())
            root = Path(info['root'])
            self.assertEqual(root.parent, Path(tempfile.gettempdir()))
            self.assertTrue(root.name.startswith('negative-batch-prepare-fixture-'))
            try:
                writer = Path(info['writer'])
                terminal = Path(info['terminal'])
                self.assertFalse((writer / m.NAME).exists())
                self.assertTrue((writer / m.SUCCESSOR).is_file())
                self.assertTrue((terminal / 'clear-ready.json').is_file())
                self.assertFalse((terminal / 'cleared.json').exists())
            finally:
                shutil.rmtree(root)

    def test_late_completion_receipt_readback_claim_holds_successor(self):
        t = self.make()
        real = os.read
        fired = []

        def late(fd, *args):
            raw = real(fd, *args)
            if not fired and Path(os.readlink('/proc/self/fd/' + str(fd))).name == 'cleared.json':
                os.symlink(t.projection.members[0]['target'], self.shadow)
                fired.append(True)
            return raw
        with patch.object(os, 'read', side_effect=late), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(fired)
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())

    def test_successor_removed_only_after_completion_receipt(self):
        t = self.make()
        real = os.unlink
        observed = []

        def observed_unlink(name, *a, **kw):
            if name == m.SUCCESSOR:
                observed.append((t.directory / 'cleared.json').is_file())
            return real(name, *a, **kw)
        with patch.object(os, 'unlink', side_effect=observed_unlink):
            t.clear()
        self.assertEqual(observed, [True])

    def test_uncertain_final_unlink_restores_successor(self):
        t = self.make()
        real = os.unlink

        def lost(name, *a, **kw):
            result = real(name, *a, **kw)
            if name == m.SUCCESSOR:
                raise OSError('lost final ACK')
            return result
        with patch.object(os, 'unlink', side_effect=lost), self.assertRaises(m.Held):
            t.clear()
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())
        self.assertTrue((t.directory / 'cleared.json').exists())

    def test_unknown_marker_replacement_not_overwritten(self):
        t = self.make()
        real = self.commit.close_committed

        def changed(r):
            v = real(r)
            if t.phase == 'cleared':
                t.marker.write_bytes(b'foreign replacement')
            return v
        with patch.object(self.commit, 'close_committed', side_effect=changed), self.assertRaises(m.Held):
            t.clear()
        self.assertEqual(t.marker.read_bytes(), b'foreign replacement')
        self.assertTrue((t.writer.root / m.SUCCESSOR).exists())

    def test_projection_pointer_substitution_holds(self):
        t = self.make()
        t.projection = copy.copy(t.projection)
        with self.assertRaises(m.Held):
            t.clear()
        self.assertTrue(t.marker.exists())

    def test_public_factory_missing_installed_types_holds(self):
        with self.assertRaises(m.Held):
            m.from_retired(self.r, self.commit)
if __name__ == '__main__':
    unittest.main()

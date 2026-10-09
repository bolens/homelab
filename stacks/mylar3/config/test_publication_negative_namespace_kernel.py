"""Real local hardlink/SQLite-free fixtures, no live media or production authority."""
from pathlib import Path
_PORTABLE_ROOT = next((p for p in Path(__file__).resolve().parents if (p / '.portable-cohort').is_file()))
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
P = Path(str(_PORTABLE_ROOT / 'publication_negative_namespace_kernel.py'))
s = importlib.util.spec_from_file_location('kernel', P)
m = importlib.util.module_from_spec(s)
s.loader.exec_module(m)

class Controls(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='comic-hardlink-fixture-', dir='/tmp')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.root.chmod(448)
        for name in ('library', 'private', 'journal'):
            (self.root / name).mkdir(mode=448)
        (self.root / 'lease.lock').write_bytes(b'owned fixture lock')
        self.source = self.root / 'library/source.bin'
        self.target = self.root / 'private/retained.bin'
        self.source.write_bytes(b'owned tiny fixture')
        os.setxattr(self.source, 'user.fixture', b'preserve')
        self.original = m._fact(self.source, 1)

    def adapter(self):
        return m.LocalFixtureAdapter(self.root)

    def test_default_live_off(self):
        r = subprocess.run([sys.executable, str(P)], capture_output=True, check=True)
        self.assertFalse(json.loads(r.stdout)['executable'])
        for token in (None, True, {'reader_absent': True, 'native_grant': True}):
            with self.assertRaises(m.Held):
                m.retire_native(token)

    def test_actual_link_retention_and_rollback_attributes(self):
        with self.adapter() as k:
            k.prepare()
            a = k.apply()
            self.assertTrue(a['fixture_transition_verified'])
            self.assertFalse(a['native_grant'])
            self.assertFalse(self.source.exists())
            retained = m._fact(self.target, 1)
            self.assertTrue(m._preserved(retained, self.original, 1))
            b = k.rollback()
            self.assertTrue(b['fixture_rollback_verified'])
            self.assertFalse(self.target.exists())
            self.assertTrue(m._preserved(m._fact(self.source, 1), self.original, 1))

    def test_explicit_journal_two_alias_witness(self):
        with self.adapter() as k:
            k.prepare()
            k.apply()
            rows = k._rows()
            pair = rows[2][0]['pair']
            self.assertEqual(pair['signature9'][8], 2)
            self.assertEqual(rows[-1][0]['retained']['signature9'][8], 1)
            self.assertEqual(rows[1][0]['phase'], 'link-intent')
            self.assertEqual(rows[3][0]['phase'], 'unlink-intent')

    def test_atomic_link_eexist_never_overwrites_foreign_target(self):
        with self.adapter() as k:
            k.prepare()
            self.target.write_bytes(b'foreign')
            with self.assertRaises(FileExistsError):
                k._link(self.source, self.target, self.original)
            self.assertEqual(self.target.read_bytes(), b'foreign')
            self.assertEqual(m._fact(self.source, 1), self.original)

    def test_foreign_source_refuses_rollback_no_cleanup(self):
        with self.adapter() as k:
            k.prepare()
            k.apply()
            self.source.write_bytes(b'foreign')
            with self.assertRaises(m.Held):
                k.rollback()
            self.assertEqual(self.source.read_bytes(), b'foreign')
            self.assertTrue(self.target.exists())

    def test_lost_link_ack_retains_two_links_and_no_replay(self):
        with self.adapter() as k:
            k.prepare()
            real = k._link

            def lost(a, b, known):
                real(a, b, known)
                raise TimeoutError('unknown ack')
            with patch.object(k, '_link', lost), self.assertRaises(TimeoutError):
                k.apply()
            self.assertEqual(os.lstat(self.source).st_nlink, 2)
            self.assertEqual(os.lstat(self.target).st_nlink, 2)
            view = k.inspect_pending()
            self.assertTrue(view['held'])
            self.assertFalse(view['automatic_replay'])
            self.assertEqual(view['phase'], 'link-intent')
            with self.assertRaises(m.Held):
                k.apply()

    def test_lost_unlink_ack_preserves_retained_and_no_replay(self):
        with self.adapter() as k:
            k.prepare()
            real = k._unlink

            def lost(p, f):
                real(p, f)
                raise TimeoutError('unknown ack')
            with patch.object(k, '_unlink', lost), self.assertRaises(TimeoutError):
                k.apply()
            self.assertFalse(self.source.exists())
            self.assertEqual(os.lstat(self.target).st_nlink, 1)
            self.assertEqual(k.inspect_pending()['phase'], 'unlink-intent')
            with self.assertRaises(m.Held):
                k.apply()

    def test_expired_lease_refuses_transition(self):
        scope = self.adapter()
        k = scope.kernel
        k.prepare()
        scope.close()
        with self.assertRaises(m.Held):
            k.apply()
        self.assertTrue(self.source.exists())
        self.assertFalse(self.target.exists())

    def test_foreign_third_hardlink_refused(self):
        with self.adapter() as k:
            k.prepare()
            os.link(self.source, self.root / 'foreign.bin')
            with self.assertRaises(m.Held):
                k.apply()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())

    def test_content_and_xattr_drift_refused(self):
        with self.adapter() as k:
            k.prepare()
            os.setxattr(self.source, 'user.fixture', b'foreign')
            with self.assertRaises(m.Held):
                k.apply()
            self.assertTrue(self.source.exists())

    def test_known_link_ctime_drift_before_unlink_refused(self):
        with self.adapter() as k:
            k.prepare()
            real = k._append

            def late(phase, **kw):
                value = real(phase, **kw)
                if phase == 'linked':
                    os.chmod(self.source, os.stat(self.source).st_mode & 511)
                return value
            with patch.object(k, '_append', late), self.assertRaisesRegex(m.Held, 'known-custody-incarnation'):
                k.apply()
            self.assertEqual(os.lstat(self.source).st_nlink, 2)
            self.assertEqual(os.lstat(self.target).st_nlink, 2)

    def test_parent_rebuild_before_transition_held(self):
        with self.adapter() as k:
            k.prepare()
            parent = self.source.parent
            old = self.root / 'kept'
            parent.rename(old)
            parent.mkdir(mode=448)
            (old / self.source.name).rename(self.source)
            with self.assertRaisesRegex(m.Held, 'parent-drift'):
                k.apply()

    def test_coowned_names_are_preserved(self):
        other = self.source.parent / 'other.bin'
        other.write_bytes(b'other')
        before = m._fact(other, 1)
        with self.adapter() as k:
            k.prepare()
            k.apply()
            k.rollback()
        self.assertEqual(m._fact(other, 1), before)

    def test_journal_foreign_entry_held(self):
        with self.adapter() as k:
            k.prepare()
            (self.root / 'journal/foreign.json').write_bytes(b'foreign')
            with self.assertRaises(m.Held):
                k.apply()

    def test_lost_rollback_link_ack_retains_pair_no_replay(self):
        with self.adapter() as k:
            k.prepare()
            k.apply()
            real = k._link

            def lost(a, b, known):
                real(a, b, known)
                raise TimeoutError('lost rollback link ack')
            with patch.object(k, '_link', lost), self.assertRaises(TimeoutError):
                k.rollback()
            self.assertEqual(os.lstat(self.source).st_nlink, 2)
            self.assertEqual(os.lstat(self.target).st_nlink, 2)
            self.assertEqual(k.inspect_pending()['phase'], 'rollback-link-intent')
            with self.assertRaises(m.Held):
                k.rollback()

    def test_lost_rollback_unlink_ack_preserves_original_no_replay(self):
        with self.adapter() as k:
            k.prepare()
            k.apply()
            real = k._unlink

            def lost(p, known):
                real(p, known)
                raise TimeoutError('lost rollback unlink ack')
            with patch.object(k, '_unlink', lost), self.assertRaises(TimeoutError):
                k.rollback()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())
            self.assertEqual(os.lstat(self.source).st_nlink, 1)
            self.assertEqual(k.inspect_pending()['phase'], 'rollback-unlink-intent')
            with self.assertRaises(m.Held):
                k.rollback()

    def test_durable_parent_binding_refuses_adoption_on_reopen(self):
        with self.adapter() as k:
            k.prepare()
            k._append('link-intent', pending=True)
        parent = self.source.parent
        old = self.root / 'saved'
        parent.rename(old)
        parent.mkdir(mode=448)
        (old / self.source.name).rename(self.source)
        old.rmdir()
        with self.adapter() as k:
            with self.assertRaisesRegex(m.Held, 'durable-fenced-namespace'):
                k.inspect_pending()

    def test_reopened_completed_json_cannot_authorize_rollback(self):
        with self.adapter() as k:
            k.prepare()
            k.apply()
        with self.adapter() as k:
            self.assertTrue(k.inspect_pending()['held'])
            with self.assertRaisesRegex(m.Held, 'fresh-owning-capability-required'):
                k.rollback()
            self.assertTrue(self.target.exists())
            self.assertFalse(self.source.exists())

    def test_rewritten_journal_never_rebinds_owned_original(self):
        with self.adapter() as k:
            k.prepare()
            path = self.root / 'journal/00.json'
            packet = json.loads(path.read_bytes())
            packet['original']['sha256'] = '0' * 64
            path.write_bytes(m._encode(packet))
            with self.assertRaisesRegex(m.Held, 'owned-receipt-custody'):
                k.apply()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())

    def test_crash_before_link_no_auto_replay(self):
        with self.adapter() as k:
            k.prepare()
            k._append('link-intent', pending=True)
        with self.adapter() as k:
            view = k.inspect_pending()
            self.assertEqual(view['phase'], 'link-intent')
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())
            with self.assertRaises(m.Held):
                k.apply()

    def test_final_retained_journal_read_new_child_holds(self):
        with self.adapter() as k:
            k.prepare()
            real = m._fact
            fired = []

            def late(p, *args, **kw):
                value = real(p, *args, **kw)
                if Path(p) == self.root / 'journal/04.json' and (not fired):
                    fired.append(True)
                    (self.root / 'journal/foreign.txt').write_bytes(b'foreign')
                return value
            with patch.object(m, '_fact', side_effect=late), self.assertRaisesRegex(m.Held, 'journal-census-incarnation'):
                k.apply()
            self.assertTrue(fired)
            self.assertTrue(self.target.exists())
            self.assertFalse(self.source.exists())

    def test_post_rows_custody_callback_new_journal_child_holds(self):
        with self.adapter() as k:
            k.prepare()
            real = m._namespace
            fired = []

            def late(p):
                value = real(p)
                if p == self.target.parent and self.target.exists() and (not self.source.exists()) and (not fired):
                    fired.append(True)
                    (self.root / 'journal/foreign.txt').write_bytes(b'foreign')
                return value
            with patch.object(m, '_namespace', side_effect=late), self.assertRaisesRegex(m.Held, 'terminal-directory9'):
                k.apply()
            self.assertTrue(fired)
            self.assertTrue(self.target.exists())

    def test_private_journal_mode_drift_refuses(self):
        with self.adapter() as k:
            k.prepare()
            (self.root / 'journal/00.json').chmod(416)
            with self.assertRaisesRegex(m.Held, 'private-journal-leaf'):
                k.apply()
            self.assertTrue(self.source.exists())
            self.assertFalse(self.target.exists())
if __name__ == '__main__':
    unittest.main()

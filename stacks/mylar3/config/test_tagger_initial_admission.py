"""Disposable native/legacy callers; CLI/catalog fixtures, real Writer and files.

Capacity replies project finite filesystem free-space only, never admission success.
"""
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import test_tagger_native as fixtures
import tagger_staging as standalone
from tagger_adapter import fingerprint
from tagger_archive import identity


class NativeAdmission(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.NativeTest('runTest')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture
        self.stage = sys.modules['mylar.tagger_staging']

    def invoke(self):
        # Actual native operation scope and legacy automatic caller; no publication grant.
        with self.f.writers.operation():
            return self.f.native.run(str(self.f.root), filename=str(self.f.source), issueid='123')

    def directories(self):
        root = self.f.root/'modern-tagger-v2'
        return root/'staging', root/'staging-receipts'

    def test_native_success_and_owned_cleanup_still_work(self):
        self.f.test_automatic_stage_survives_until_native_placement_and_is_cleaned_after()

    def test_actual_native_low_space_refuses_before_folder_or_receipt(self):
        with patch.object(self.stage.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(1, 1, 0)):
            self.assertIsInstance(self.invoke(), self.f.handoff.Failure)
        self.assertEqual([list(p.iterdir()) for p in self.directories()], [[], []])
        self.assertEqual(self.f.source.read_bytes(), self.f.before)

    def test_actual_legacy_retained_same_generation_does_not_copy_again(self):
        with patch.object(self.stage.Staging, 'ready', side_effect=OSError('fixture late ready failure')):
            self.assertIsInstance(self.invoke(), self.f.handoff.Failure)
        folder, receipts = self.directories()
        files = list(folder.glob('*/*'))
        self.assertEqual(len(files), 1)
        original = (files[0].read_bytes(), files[0].stat(), [p.read_bytes() for p in receipts.iterdir()])
        for _ in range(3):
            self.assertIsInstance(self.invoke(), self.f.handoff.Failure)
            self.assertEqual(list(folder.glob('*/*')), files)
            self.assertEqual(files[0].read_bytes(), original[0])
            self.assertEqual(files[0].stat(), original[1])
            self.assertEqual([p.read_bytes() for p in receipts.iterdir()], original[2])
        self.assertEqual(self.f.source.read_bytes(), self.f.before)
        self.assertFalse(self.f.writers.owner().fenced(tagger=True))

    def test_lookup_failure_makes_no_archive_copy(self):
        self.f.lookup_mock.return_value = self.f.lookup.LookupResult('timed_out')
        self.assertIsInstance(self.invoke(), self.f.handoff.Failure)
        self.assertEqual([list(p.iterdir()) for p in self.directories()], [[], []])

    def test_source_swap_after_receipt_before_copy_copies_no_payload(self):
        saved = self.stage.Staging.save
        seen = []
        def save(owner, record):
            saved(owner, record)
            if record['state'] == 'copying':
                self.f.source.write_bytes(b'changed source generation')
        opened = self.stage.Staging.recover
        def recover(owner):
            seen.extend(p.stat().st_size for p in owner.root.glob('*/*'))
            return opened(owner)
        with patch.object(self.stage.Staging, 'save', save), patch.object(self.stage.Staging, 'recover', recover):
            self.assertIsInstance(self.invoke(), self.f.handoff.Failure)
        self.assertIn(0, seen)
        self.assertFalse(any(n > 0 for n in seen))

    def test_native_uses_existing_scalar_settings_without_cache_root_dependency(self):
        self.f.mylar.CONFIG.DDL_CACHE_MAX_GIB = 2
        self.f.mylar.CONFIG.DDL_CACHE_MIN_FREE_GIB = 3
        admitted = self.stage.Staging.admit_copy
        limits = []
        def admit(owner, *args):
            limits.append(owner.copy_limits)
            return admitted(owner, *args)
        with patch.object(self.stage.Staging, 'admit_copy', admit):
            self.assertIs(type(self.invoke()), str)
        self.assertEqual(limits, [(2 * 1024**3, 3 * 1024**3)])


class DirectAdmission(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name in ('stages', 'receipts'):
            (self.root/name).mkdir(mode=0o700)
        self.source = self.root/'source.cbz'; self.source.write_bytes(b'x'*4096)

    def owner(self, maximum=8192, reserve=1024):
        return standalone.Staging(self.root/'stages', self.root/'receipts', copy_limits=(maximum, reserve))

    def allocate(self, owner, token):
        return owner.allocate(token*32, self.source, fingerprint(self.source), identity(self.source.stat()))

    def test_single_copy_byte_limit_precedes_folder_birth(self):
        with self.assertRaisesRegex(ValueError, 'copy limit'):
            self.allocate(self.owner(maximum=4095), 'a')
        self.assertEqual(list((self.root/'stages').iterdir()), [])
        self.assertEqual(list((self.root/'receipts').iterdir()), [])

    def test_exact_free_floor_and_repeated_generation_refusal(self):
        owner = self.owner(); required = 4096 + 8192 + 1024
        with patch.object(standalone.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(required, 0, required)):
            target = self.allocate(owner, 'a'); shutil.copyfile(self.source, target)
        before = target.read_bytes()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'Unresolved automatic'):
                self.allocate(owner, 'b')
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(len(list((self.root/'receipts').iterdir())), 1)

    def test_same_path_new_generation_is_not_silently_reused_or_deleted(self):
        owner = self.owner(); old = self.allocate(owner, 'a'); shutil.copyfile(self.source, old)
        self.source.write_bytes(b'new generation')
        new = self.allocate(owner, 'b')
        self.assertNotEqual(old, new)
        self.assertEqual(old.read_bytes(), b'x'*4096)
        self.assertFalse(new.exists())

    def test_invalid_limits_refuse_without_new_state(self):
        for limits in ((), (True, 1), (1, 0), (1, -1)):
            with self.assertRaises(ValueError):
                standalone.Staging(self.root/'stages', self.root/'receipts', copy_limits=limits)


if __name__ == '__main__':
    unittest.main()

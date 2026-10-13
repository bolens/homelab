"""Real private cache files, original directory races and allocation contention."""
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import cache_admission as guard


class Controls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.cache = self.root / 'cache'; self.cache.mkdir()
        cfg = SimpleNamespace(CACHE_DIR=str(self.cache), DDL_LOCATION=str(self.cache), DDL_CACHE_MAX_GIB=20, DDL_CACHE_MIN_FREE_GIB=5)
        self.mylar = SimpleNamespace(CONFIG=cfg, DATA_DIR=str(self.root))
        p = patch.dict(sys.modules, {'mylar': self.mylar}); p.start(); self.addCleanup(p.stop)

    def test_finite_settings_reject_bool_zero_negative_and_fraction(self):
        for value in (True, 0, -1, 4097, '1.5', None):
            with self.assertRaises(ValueError): guard.setting(value)
        self.assertEqual(guard.setting('20'), 20)
        with self.assertRaises(ValueError): guard.validate_update({'DDL_CACHE_MAX_GIB': 20, 'ddl_cache_max_gib': 21})

    def test_overlapping_roots_do_not_double_count_retained_and_temporary(self):
        (self.cache / '.mylar-unpack-x').mkdir(); p = self.cache / '.mylar-unpack-x/member'; p.write_bytes(b'retained')
        self.mylar.CONFIG.DDL_LOCATION = str(p.parent)
        _, roots, _, _ = guard.configured(); self.assertEqual(roots, (self.cache,))
        self.assertGreaterEqual(guard.usage(roots), p.stat().st_blocks * 512)

    def test_overbudget_rejects_growth_but_allows_original_only_recovery(self):
        with (self.cache / 'retained').open('wb') as f: f.truncate(21 * guard.GIB)
        with self.assertRaises(guard.Held):
            with guard.Allocation(self.cache, 1): pass
        with guard.Allocation(self.cache, 0) as lease: lease.before_write(0)
        self.assertEqual((self.cache / 'retained').stat().st_size, 21 * guard.GIB)

    def test_two_chunks_preserve_exact_free_reserve_without_double_count(self):
        available = [5 * guard.GIB + 8192]
        def free(_): return SimpleNamespace(f_bavail=available[0], f_frsize=1)
        with patch.object(guard.os, 'fstatvfs', free), guard.Allocation(self.cache, 8192) as lease:
            lease.before_write(4096); available[0] -= 4096
            lease.before_write(4096); available[0] -= 4096
        self.assertEqual(available[0], 5 * guard.GIB)

    def test_foreign_free_space_loss_refuses_before_next_write(self):
        with patch.object(guard.os, 'fstatvfs', return_value=SimpleNamespace(f_bavail=6 * guard.GIB, f_frsize=1)):
            with guard.Allocation(self.cache, 8192) as lease:
                lease.before_write(4096)
                with patch.object(guard.os, 'fstatvfs', return_value=SimpleNamespace(f_bavail=5 * guard.GIB, f_frsize=1)), self.assertRaises(guard.Held):
                    lease.before_write(4096)

    def test_actual_thread_reservation_cannot_be_double_spent(self):
        with guard.Allocation(self.cache, 0):
            with self.assertRaises(guard.Held):
                with guard.Allocation(self.cache, 0): pass

    def test_actual_independent_process_flock_refuses_second_reservation(self):
        script = "import sys;from pathlib import Path;from types import SimpleNamespace;sys.path.insert(0,sys.argv[1]);import cache_admission as g;sys.modules['mylar']=SimpleNamespace(CONFIG=SimpleNamespace(CACHE_DIR=sys.argv[2],DDL_LOCATION=sys.argv[2]),DATA_DIR=str(Path(sys.argv[2]).parent));g.Allocation(sys.argv[2],0).__enter__()"
        with guard.Allocation(self.cache, 0):
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script, str(Path(guard.__file__).parent), str(self.cache)], capture_output=True)
        self.assertNotEqual(result.returncode, 0); self.assertIn(b'already reserved', result.stderr)

    def test_later_census_entry_cannot_change_a_previously_counted_file(self):
        first = self.cache / 'a'; first.write_bytes(b'original')
        last = self.cache / 'z'; last.write_bytes(b'last')
        actual = guard.os.stat; fired = []
        def changed(path, *args, **kwargs):
            result = actual(path, *args, **kwargs)
            if path == 'z' and not fired:
                fired.append(True)
                with first.open('wb') as stream: stream.truncate(21 * guard.GIB)
            return result
        with patch.object(guard.os, 'stat', changed), self.assertRaises(guard.Held):
            guard.usage((self.cache,))
        self.assertEqual(fired, [True]); self.assertEqual(first.stat().st_size, 21 * guard.GIB)

    def test_directory_switched_to_symlink_after_stat_is_not_followed(self):
        child = self.cache / 'nested'; child.mkdir(); (child / 'original').write_bytes(b'bytes')
        foreign = self.root / 'foreign'; foreign.mkdir(); (foreign / 'large').write_bytes(b'foreign')
        actual = guard.os.stat; fired = []
        def replaced(path, *args, **kwargs):
            result = actual(path, *args, **kwargs)
            if path == 'nested' and kwargs.get('follow_symlinks') is False and not fired:
                child.rename(self.cache / 'retained-original'); child.symlink_to(foreign, target_is_directory=True); fired.append(True)
            return result
        with patch.object(guard.os, 'stat', replaced), self.assertRaises((guard.Held, OSError)):
            guard.usage((self.cache,))
        self.assertTrue(fired); self.assertEqual((foreign / 'large').read_bytes(), b'foreign')

    def test_lock_replacement_does_not_create_independent_successful_lease(self):
        with self.assertRaises(guard.Held):
            with guard.Allocation(self.cache, 0) as lease:
                p = self.root / 'cache-admission-v1.lock'; p.rename(self.root / 'retained-lock'); p.write_bytes(b''); p.chmod(0o600)
                lease.before_write(1)

if __name__ == '__main__': unittest.main()

"""Disposable effective CONFIG + genuine Writer startup; no installed/live grant."""
import importlib
import types
import unittest
from unittest.mock import patch
import test_publication_startup as fixture


class PolicyTests(unittest.TestCase):
    setUp = fixture.ExistingAdmissionTests.setUp
    authority = fixture.ExistingAdmissionTests.authority
    activate = fixture.ExistingAdmissionTests.activate

    def configure(self):
        self.cache = self.root/'cache'; self.cache.mkdir(mode=0o700)
        self.mylar.CONFIG=types.SimpleNamespace(CACHE_DIR=str(self.cache),DDL_LOCATION=str(self.cache),DDL_CACHE_MAX_GIB=7,DDL_CACHE_MIN_FREE_GIB=2)
        self.config=self.root/'config.ini';self.config.write_text('[DDL]\nddl_cache_max_gib=7\nddl_cache_min_free_gib=2\n');self.config.chmod(0o600)
        self.policy=importlib.import_module('mylar.cache_admission')
        self.lock=self.root/'cache-admission-v1.lock'

    def test_normal_admitted_startup_initializes_first_pack_lock(self):
        self.configure();self.authority()
        self.assertFalse(self.lock.exists());self.assertEqual(self.activate()['state'],'ready')
        self.assertTrue(self.lock.is_file());self.assertEqual(self.lock.stat().st_mode & 0o777,0o600)
        with self.native.operation():
            packet=self.policy.policy_snapshot()
        self.assertEqual(packet['maximum'],7*self.policy.GIB);self.assertEqual(packet['reserve'],2*self.policy.GIB)
        before=self.policy.identity(self.lock.stat())
        self.assertEqual(self.activate()['state'],'ready');self.assertEqual(self.policy.identity(self.lock.stat()),before)

    def test_readonly_snapshot_never_initializes_missing_lock(self):
        self.configure();self.authority();self.activate();self.lock.unlink()
        with self.native.operation(),self.assertRaises(FileNotFoundError):self.policy.policy_snapshot()
        self.assertFalse(self.lock.exists())

    def test_snapshot_requires_genuine_owning_writer(self):
        self.configure();self.authority();self.activate()
        with self.assertRaises(self.policy.Held):self.policy.policy_snapshot()

    def test_stale_config_callback_refuses_without_adopting_replacement(self):
        self.configure();self.authority();self.activate();actual=self.policy.configured;calls=[]
        def changed():
            value=actual();calls.append(True)
            if len(calls)==2:self.config.write_text('changed original')
            return value
        with self.native.operation(),patch.object(self.policy,'configured',changed),self.assertRaises(self.policy.Held):self.policy.policy_snapshot()
        self.assertEqual(self.config.read_text(),'changed original')

    def test_initialization_does_not_replace_foreign_lock(self):
        self.configure();self.lock.symlink_to(self.config);raw=self.config.read_bytes()
        with self.assertRaises(OSError):self.policy.initialize_shared_lock()
        self.assertTrue(self.lock.is_symlink());self.assertEqual(self.config.read_bytes(),raw)

    def test_initialization_closes_original_after_fd_close_callback(self):
        self.configure();real=self.policy.os.close;fired=[]
        def changed(fd):
            value=real(fd)
            if self.lock.exists() and not fired:
                fired.append(True);self.lock.chmod(0o640)
            return value
        with patch.object(self.policy.os,'close',changed),self.assertRaises(self.policy.Held):self.policy.initialize_shared_lock()
        self.assertEqual(fired,[True]);self.assertEqual(self.lock.stat().st_mode & 0o777,0o640)

    def test_health_policy_failure_is_readonly_none(self):
        self.configure();health=importlib.import_module('mylar.worker_health')
        self.assertIsNone(health._cache_policy());self.assertFalse(self.lock.exists())

    def test_config_file_bytes_do_not_override_effective_CONFIG(self):
        self.configure();self.config.write_text('[DDL]\nddl_cache_max_gib=99\n');self.authority();self.activate()
        with self.native.operation():packet=self.policy.policy_snapshot()
        self.assertEqual(packet['maximum'],7*self.policy.GIB)
        self.assertEqual(packet['config']['path'],str(self.config))
        self.assertEqual(packet['data']['identity5'][:2],[self.root.stat().st_dev,self.root.stat().st_ino])

    def test_actual_admitted_0644_config_is_preserved(self):
        self.configure();self.config.chmod(0o644);self.authority();self.activate()
        before=self.policy.identity(self.config.stat());raw=self.config.read_bytes()
        with self.native.operation():packet=self.policy.policy_snapshot()
        self.assertEqual(packet['config']['signature9'],list(before))
        self.assertEqual(self.policy.identity(self.config.stat()),before);self.assertEqual(self.config.read_bytes(),raw)

    def test_writable_config_is_not_policy(self):
        self.configure();self.config.chmod(0o622);self.authority();self.activate()
        with self.native.operation(),self.assertRaises(self.policy.Held):self.policy.policy_snapshot()
        self.assertEqual(self.config.stat().st_mode & 0o777,0o622)

    def test_untrusted_config_owner_projection_refuses(self):
        # Attribute-only negative; no chown/remount/runtime acceptance claim.
        self.configure();self.authority();self.activate();actual=self.policy.os.fstat
        from pathlib import Path
        def observed(fd):
            z=actual(fd)
            if Path('/proc/self/fd/'+str(fd)).readlink()==self.config:
                values={name:getattr(z,name) for name in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink')}
                values['st_uid']=123456789;return types.SimpleNamespace(**values)
            return z
        with self.native.operation(),patch.object(self.policy.os,'fstat',observed),self.assertRaises(self.policy.Held):self.policy.policy_snapshot()

    def test_effective_nested_ddl_is_bound_separately_from_aggregate_root(self):
        self.configure();ddl=self.cache/'ddl';ddl.mkdir(mode=0o700);self.mylar.CONFIG.DDL_LOCATION=str(ddl)
        self.authority();self.activate()
        with self.native.operation():packet=self.policy.policy_snapshot()
        self.assertEqual(len(packet['roots']),1);self.assertEqual(packet['roots'][0]['path'],str(self.cache))
        self.assertEqual(packet['ddl'],dict(path=str(ddl),identity5=list(self.policy.directory_identity(ddl.stat()))))


if __name__=='__main__':unittest.main()

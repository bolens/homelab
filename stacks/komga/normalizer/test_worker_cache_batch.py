"""Genuine NativeBatch/Writer/scope integration; remote replies are fixture inputs."""
import hashlib
from types import SimpleNamespace
import unittest
import cache_reservation as core
from maintenance import Maintenance
from publication_guard import scope, remote_unlocked, Unavailable
from test_publication_guard import AuthorityFixture
from worker_cache import Policy, publish


class CacheBatchTests(AuthorityFixture, unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.cache=self.config/'cache';self.cache.mkdir(mode=0o700)
        self.ini=self.config/'config.ini';self.ini.write_text('[DDL]\nddl_cache_max_gib=1\n');self.ini.chmod(0o600)
        lock=self.config/'cache-admission-v1.lock';lock.touch(mode=0o600)
        self.worker=SimpleNamespace(config=dict(writer_state=str(self.writer.root),mylar=dict(config_dir=str(self.config)),publication_roots=[dict(native=str(self.native_root),worker=str(self.library))]),reader=SimpleNamespace(books=lambda:{}))
        self.m=object.__new__(Maintenance);self.m.worker=self.worker;self.m.last_run=0
        self.m.settings=dict(pack_import=True,mylar_ddl_cache='/native/cache',ddl_cache=str(self.cache))
        self.packet=dict(version=1,kind='effective-ddl-cache-policy-v1',data=dict(path='/native',identity5=list(core.directory_identity(self.config.stat()))),roots=[dict(path='/native/cache',identity5=list(core.directory_identity(self.cache.stat())))],ddl=dict(path='/native/cache',identity5=list(core.directory_identity(self.cache.stat()))),lock=dict(path='/native/cache-admission-v1.lock',signature9=list(core.identity(lock.stat()))),config=dict(path='/native/config.ini',signature9=list(core.identity(self.ini.stat())),sha256=hashlib.sha256(self.ini.read_bytes()).hexdigest()),maximum=core.GIB,reserve=1)
        self.calls=[]
        def api(command,**kwargs):
            remote_unlocked(self.worker);self.calls.append(command)
            return {'cache_policy':self.packet} if command=='getHealth' else {}
        self.m.mylar=api

    def test_prefetched_policy_is_consumed_only_under_actual_shared_writer(self):
        batch=self.m.prepare()
        self.assertEqual(self.calls,['getHealth','workflowCommands','packWork'])
        with self.assertRaises(Unavailable):Policy(self.m)
        source=self.root/'final.cbz';source.write_bytes(b'finalized output')
        with self.writer.hold(),scope(self.worker,self.writer,native_batch=batch):
            policy=Policy(self.m)
            with self.assertRaises(Unavailable):self.m.mylar('getHealth')
            target=publish(policy,source,self.cache/'.mylar-pack-fixture',self.cache/'.mylar-pack-fixture/final.cbz')
            self.assertEqual(target.read_bytes(),source.read_bytes())
            # Reservation is released before the owning caller can import/handoff.
            with policy.allocation(self.cache,0):pass
        remote_unlocked(self.worker)
        self.assertEqual(len(self.calls),3)

    def test_prefetched_original_config_drift_refuses_after_writer_acquisition(self):
        batch=self.m.prepare();self.ini.write_text('changed after prefetch')
        with self.writer.hold(),scope(self.worker,self.writer,native_batch=batch),self.assertRaises(core.Held):Policy(self.m)
        self.assertEqual(list(self.cache.iterdir()),[])

    def test_no_nativebatch_or_unavailable_policy_cannot_stage(self):
        with self.writer.hold(),scope(self.worker,self.writer),self.assertRaises(Unavailable):Policy(self.m)
        self.packet=None;batch=self.m.prepare()
        with self.writer.hold(),scope(self.worker,self.writer,native_batch=batch),self.assertRaises(core.Held):Policy(self.m)
        self.assertEqual(list(self.cache.iterdir()),[])


if __name__=='__main__':unittest.main()

"""Real Writer/NativeBatch with explicit path-only bind model, not live mounts."""
from contextlib import contextmanager
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import cache_reservation as core
import worker_cache as cache
import test_worker_cache_batch as fixtures
from publication_guard import scope


class AliasTests(unittest.TestCase):
    def fixture(self):
        f=fixtures.CacheBatchTests('run');f.setUp();self.addCleanup(f.doCleanups);return f

    @contextmanager
    def alias(self, spelling, target):
        # Translate only this disposable alias path to genuine original FDs and
        # stat_results. No device/inode/permission result is fabricated.
        original_open=core.open_directory;original_stat=os.lstat
        def translated(path):
            p=Path(path)
            return target[0]/p.relative_to(spelling) if p.is_relative_to(spelling) else p
        def opened(path):return original_open(translated(path))
        def stated(path,*args,**kwargs):
            if isinstance(path,(str,Path)) and Path(path).is_absolute():path=translated(path)
            return original_stat(path,*args,**kwargs)
        with patch.object(core,'open_directory',opened),patch.object(os,'lstat',stated):yield

    def nested(self,f):
        nested=f.cache/'ddl';nested.mkdir(mode=0o700);alias=f.root/'ddl-alias'
        f.packet['ddl']=dict(path='/native/cache/ddl',identity5=list(core.directory_identity(nested.stat())))
        f.m.settings.update(mylar_ddl_cache='/native/cache/ddl',ddl_cache=str(alias))
        return nested,alias

    def test_nested_rw_alias_uses_one_aggregate_root_and_exact_destination(self):
        f=self.fixture();nested,alias=self.nested(f);batch=f.m.prepare();target=[nested]
        with self.alias(alias,target),f.writer.hold(),scope(f.worker,f.writer,native_batch=batch):
            p=cache.Policy(f.m);self.assertEqual(p.roots,(f.cache,));self.assertEqual(p.ddl,alias)
            with p.allocation(alias,0) as reserved:self.assertEqual(reserved.used,core.usage((f.cache,)))
            source=f.root/'source.cbz';source.write_bytes(b'exact bytes')
            cache.publish(p,source,alias/'.mylar-pack',alias/'.mylar-pack/source.cbz')
            self.assertEqual((nested/'.mylar-pack/source.cbz').read_bytes(),source.read_bytes())
            with self.assertRaises(core.Held):
                with p.allocation(f.cache,1):pass
        self.assertEqual(len(list(f.cache.rglob('source.cbz'))),1)

    def test_changed_alias_original_refuses(self):
        f=self.fixture();nested,alias=self.nested(f);other=f.root/'other';other.mkdir();batch=f.m.prepare();target=[nested]
        with self.alias(alias,target),f.writer.hold(),scope(f.worker,f.writer,native_batch=batch):
            p=cache.Policy(f.m);target[0]=other
            with self.assertRaises(core.Held):p.check()
        self.assertEqual(list(other.iterdir()),[])

    def test_unrelated_alias_and_misjoined_root_refuse(self):
        for changed_root in (False,True):
            f=self.fixture();nested,alias=self.nested(f);other=f.root/'other';other.mkdir();batch=None
            if changed_root:f.packet['roots'][0]['identity5']=list(core.directory_identity(other.stat()))
            batch=f.m.prepare()
            with self.alias(alias,[nested if changed_root else other]),f.writer.hold(),scope(f.worker,f.writer,native_batch=batch),self.assertRaises(core.Held):cache.Policy(f.m)

    def test_disjoint_roots_count_retained_bytes_and_only_ddl_can_grow(self):
        f=self.fixture();other=f.config/'other';other.mkdir(mode=0o700)
        f.packet['roots'].append(dict(path='/native/other',identity5=list(core.directory_identity(other.stat()))));batch=f.m.prepare()
        with f.writer.hold(),scope(f.worker,f.writer,native_batch=batch):
            p=cache.Policy(f.m);self.assertEqual(set(p.roots),{f.cache,other})
            source=f.root/'final.cbz';source.write_bytes(b'new')
            cache.publish(p,source,f.cache/'.mylar-pack',f.cache/'.mylar-pack/final.cbz')
            with self.assertRaises(core.Held):
                with p.allocation(other,1):pass
            with (other/'retained').open('wb') as stream:stream.truncate(2*core.GIB)
            with p.allocation(f.cache,0) as reserved:self.assertEqual(reserved.used,core.usage((f.cache,other)))
            with self.assertRaises(core.Held):
                with p.allocation(f.cache,1):pass

    def test_changed_effective_ddl_and_symlink_refuse(self):
        f=self.fixture();f.packet['ddl']['path']='/native/other';batch=f.m.prepare()
        with f.writer.hold(),scope(f.worker,f.writer,native_batch=batch),self.assertRaises(core.Held):cache.Policy(f.m)
        f=self.fixture();nested,alias=self.nested(f);alias.symlink_to(nested,target_is_directory=True);batch=f.m.prepare()
        with f.writer.hold(),scope(f.worker,f.writer,native_batch=batch),self.assertRaises((OSError,core.Held)):cache.Policy(f.m)


if __name__=='__main__':unittest.main()

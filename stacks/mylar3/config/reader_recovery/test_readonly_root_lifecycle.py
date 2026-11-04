"""Pure staging/cleanup helpers; synthetic local filesystem, no NFS grant."""
from pathlib import Path
from contextlib import contextmanager
import sys
sys.path.insert(0, str(Path(__file__).parent))
import hashlib
import os
import tempfile
import types
import unittest
from unittest.mock import patch
import comic_negative_nfs_active_lifecycle as m


@contextmanager
def stale_retained_census():
    """Model a retained description's pre-mutation view; fresh opens see reality."""
    real_open,real_listdir=os.open,os.listdir
    retained={};fresh=[]
    def open_directory(path,flags,*args,**kwargs):
        fd=real_open(path,flags,*args,**kwargs)
        retained.pop(fd,None)
        if flags&os.O_DIRECTORY:
            if str(path)=='.' and 'dir_fd' in kwargs:fresh.append(fd)
            else:retained[fd]=real_listdir(path)
        return fd
    def names(path):
        return list(retained[path]) if isinstance(path,int) and path in retained else real_listdir(path)
    with patch.object(os,'open',side_effect=open_directory),patch.object(os,'listdir',side_effect=names):
        yield fresh


class LifecycleVectors(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.live, self.fixed, self.staging = [self.base / n for n in ('live', 'fixed', 'staging')]
        for p in (self.live, self.fixed, self.staging):
            p.mkdir(mode=0o700)
        self.roots = [self.live, self.fixed]
        self.files = ((str(self.fixed), tuple(m.stamp(self.fixed))),)
        self.nodes = ((str(self.live), tuple(m.stamp(self.live)[i] for i in (0, 1, 5, 6, 7))),)
        self.parent = self.staging / ('.comic-nfs-private-' + 'a' * 32)
        self.plan = dict(path=str(self.parent), grandparent_signature=m.stamp(self.staging),
                         expected_device=self.staging.stat().st_dev, mount_identity=dict(fstype='nfs4'))

    def prepare(self, observe=None):
        return m._prepare_parent(self.plan, self.roots, observe or (lambda _: self.plan['mount_identity']),
                                 self.files, self.nodes)

    def fixture(self):
        self.parent.mkdir(mode=0o700)
        child = self.parent / ('.comic-nfs-probe-' + 'b' * 32); child.mkdir(mode=0o700)
        for name in ('source', 'target'):
            (child / name).mkdir(mode=0o700)
        names = {'source/source.bin', 'source/collision.bin', 'target/foreign.bin',
                 'stage-intent.json', 'collision-intent.json', 'retire-intent.json',
                 'restore-intent.json', 'unstage-intent.json', 'result.json'}
        facts = {}
        for name in names:
            p = child / name; p.write_bytes(b'synthetic original\n'); p.chmod(0o600)
            facts[name] = dict(signature=m.stamp(p), sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        parent = dict(path=str(self.parent), signature=m.stamp(self.parent),
                      grandparent_identity=m.stamp(self.staging)[:2],
                      grandparent_node5=[m.stamp(self.staging)[i] for i in (0, 1, 5, 6, 7)])
        return parent, dict(path=str(child), signature=m.stamp(child)), facts, {n: m.stamp(child / n) for n in ('source', 'target')}

    def cleanup(self, fixture, callback):
        return m._cleanup_hardlink_owned(*fixture, self.roots, types.SimpleNamespace(pulse=callback), self.files, self.nodes)

    def test_configured_prepare_accepts_live_churn_without_rebasing_node(self):
        def observe(_):
            (self.live / 'journal').touch(); return self.plan['mount_identity']
        result = self.prepare(observe)
        self.assertEqual(result['path'], str(self.parent)); self.assertEqual(os.listdir(self.parent), [])

    def test_standalone_prepare_retains_full_metadata_guards(self):
        def observe(_):
            (self.live / 'journal').touch(); return self.plan['mount_identity']
        with self.assertRaises(m.Held):
            m.prepare_parent(self.plan, self.roots, observe)
        self.assertFalse(self.parent.exists())

    def test_missing_duplicate_or_foreign_root_vector_refuses(self):
        for files, nodes in (((), self.nodes), (self.files, self.nodes + self.nodes),
                             (self.files + self.files, self.nodes),
                             (self.files, ((str(self.staging), self.nodes[0][1]),))):
            with self.subTest(files=len(files), nodes=len(nodes)), self.assertRaises(m.Held):
                m._protected_vectors(self.roots, files, nodes)

    def test_node_mode_and_regular_file_vectors_refuse(self):
        os.chmod(self.live, 0o500)
        with self.assertRaises(m.Held):
            m._protected_vectors(self.roots, self.files, self.nodes)
        malformed = list(self.files[0][1]); malformed[5] = 0o100600
        with self.assertRaises(m.Held):
            m._protected_vectors(self.roots, ((str(self.fixed), tuple(malformed)),), self.nodes)

    def test_complete_roots_still_guard_overlap(self):
        self.plan['path'] = str(self.live / self.parent.name)
        with self.assertRaisesRegex(m.Held, 'protected-overlap'):
            self.prepare()
        self.assertEqual(os.listdir(self.live), [])

    def test_node_only_root_still_guards_physical_alias(self):
        original = m.stamp
        def stamp(path):
            return original(self.live) if Path(path) == self.base else original(path)
        with patch.object(m, 'stamp', stamp), self.assertRaisesRegex(m.Held, 'physical-protected-alias'):
            self.prepare()
        self.assertFalse(self.parent.exists())

    def test_cleanup_closes_node_after_every_pulse_and_keeps_other_roots(self):
        fixture = self.fixture(); calls = []
        def churn():
            calls.append(1); (self.live / ('journal-' + str(len(calls)))).touch()
        result = self.cleanup(fixture, churn)
        self.assertTrue(result['owned_fixture_absence_verified']); self.assertFalse(self.parent.exists())
        self.assertGreater(len(calls), 9); self.assertEqual(os.listdir(self.fixed), [])

    def test_hardlink_cleanup_refreshes_retained_directory_views(self):
        fixture=self.fixture()
        with stale_retained_census() as opened:
            result=self.cleanup(fixture,lambda:None)
        self.assertTrue(result['owned_fixture_absence_verified'])
        self.assertFalse(self.parent.exists());self.assertGreaterEqual(len(opened),4)

    def test_legacy_cleanup_refreshes_retained_directory_views(self):
        self.parent.mkdir(mode=0o700)
        child=self.parent/('.comic-nfs-probe-'+'b'*32);child.mkdir(mode=0o700);facts={}
        for name in ('source.bin','collision-source.bin','collision-destination.bin'):
            path=child/name;path.write_bytes(b'synthetic original');path.chmod(0o600)
            facts[name]=dict(signature=m.stamp(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        parent=dict(path=str(self.parent),signature=m.stamp(self.parent),grandparent_identity=m.stamp(self.staging)[:2])
        with stale_retained_census() as opened:
            result=m.cleanup_owned(parent,dict(path=str(child),signature=m.stamp(child)),facts,self.roots,types.SimpleNamespace(pulse=lambda:None),stopped_child_proof=True)
        self.assertTrue(result['owned_fixture_absence_verified'])
        self.assertFalse(self.parent.exists());self.assertGreater(len(opened),4)

    def test_fresh_census_closes_owned_descriptor_after_initial_fstat_failure(self):
        held=os.open(self.staging,os.O_RDONLY|os.O_DIRECTORY);opened=[];fired=[]
        expected=tuple(m.stamp(self.staging)[i]for i in(0,1,5,6,7));real_open,real_stat=os.open,os.fstat
        def new(path,*args,**kwargs):
            fd=real_open(path,*args,**kwargs)
            if str(path)=='.':opened.append(fd)
            return fd
        def fail(fd):
            if fd in opened and not fired:fired.append(True);raise OSError('synthetic fstat failure')
            return real_stat(fd)
        try:
            with patch.object(os,'open',side_effect=new),patch.object(os,'fstat',side_effect=fail):
                with self.assertRaisesRegex(OSError,'synthetic fstat failure'):m.fresh_names(held,expected)
            self.assertEqual(len(opened),1)
            with self.assertRaises(OSError):os.fstat(opened[0])
            os.fstat(held)
        finally:os.close(held)

    def test_fresh_census_never_closes_reused_foreign_descriptor(self):
        held=os.open(self.staging,os.O_RDONLY|os.O_DIRECTORY);opened=[];foreign=[]
        expected=tuple(m.stamp(self.staging)[i]for i in(0,1,5,6,7));real_open,real_stat=os.open,os.fstat
        def new(path,*args,**kwargs):
            fd=real_open(path,*args,**kwargs)
            if str(path)=='.':opened.append(fd)
            return fd
        def replace(fd):
            if fd in opened and not foreign:
                os.close(fd);other=real_open(self.fixed,os.O_RDONLY|os.O_DIRECTORY);foreign.append(other)
                self.assertEqual(other,fd);raise OSError('synthetic descriptor replacement')
            return real_stat(fd)
        try:
            with patch.object(os,'open',side_effect=new),patch.object(os,'fstat',side_effect=replace):
                with self.assertRaisesRegex(OSError,'synthetic descriptor replacement'):m.fresh_names(held,expected)
            os.fstat(foreign[0])
        finally:
            for fd in foreign:os.close(fd)
            os.close(held)

    def test_fresh_census_never_adopts_returned_foreign_identity(self):
        held=os.open(self.staging,os.O_RDONLY|os.O_DIRECTORY);opened=[];foreign=[]
        expected=tuple(m.stamp(self.staging)[i]for i in(0,1,5,6,7));real_open,real_stat=os.open,os.fstat
        def new(path,*args,**kwargs):
            fd=real_open(path,*args,**kwargs)
            if str(path)=='.':opened.append(fd)
            return fd
        def replace(fd):
            if fd in opened and not foreign:
                os.close(fd);other=real_open(self.fixed,os.O_RDONLY|os.O_DIRECTORY);foreign.append(other)
                self.assertEqual(other,fd)
            return real_stat(fd)
        try:
            with patch.object(os,'open',side_effect=new),patch.object(os,'fstat',side_effect=replace):
                with self.assertRaisesRegex(m.Held,'census-open-directory'):m.fresh_names(held,expected)
            os.fstat(foreign[0])
        finally:
            for fd in foreign:os.close(fd)
            os.close(held)

    def test_cleanup_fixed_root_churn_refuses_before_unlink(self):
        fixture = self.fixture()
        def change():
            (self.fixed / 'unexpected').touch()
        with self.assertRaises(m.Held):
            self.cleanup(fixture, change)
        self.assertTrue((Path(fixture[1]['path']) / 'result.json').exists())

    def test_cleanup_file_mutation_refuses_before_unlink(self):
        fixture = self.fixture(); leaf = Path(fixture[1]['path']) / 'result.json'
        with self.assertRaises(m.Held):
            self.cleanup(fixture, lambda: leaf.write_bytes(b'changed'))
        self.assertEqual(len(fixture[2]), len([p for p in Path(fixture[1]['path']).rglob('*') if p.is_file()]))

    def test_cleanup_node_mode_drift_refuses_before_unlink(self):
        fixture = self.fixture()
        with self.assertRaises(m.Held):
            self.cleanup(fixture, lambda: os.chmod(self.live, 0o500))
        self.assertTrue((Path(fixture[1]['path']) / 'result.json').exists())


if __name__ == '__main__':
    unittest.main()

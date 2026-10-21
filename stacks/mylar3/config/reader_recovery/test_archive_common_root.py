"""Actual private directory custody; no Docker, NFS or Parent admission claims."""
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('common_root_parent', HERE / 'comic_reader_lifecycle_parent.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.root = self.base / 'common'
        self.root.mkdir(mode=0o700)
        self.library = self.root / 'library'
        self.retention = self.root / 'retention'
        for path in (self.library, self.retention):
            path.mkdir(mode=0o700)
        self.assertEqual((os.geteuid(), os.getegid()), (1000, 1000), 'Run this owning fixture as UID/GID1000')
        self.geometry = dict(version=1, kind='private-common-root-nfs',
                             **{name: dict(path=str(path), signature9=p.nine(path.lstat())) for name, path in
                                (('common_root', self.root), ('library', self.library), ('retention', self.retention))})
        self.mounts = [dict(host=str(self.root), child=str(self.root), write=True)]

    def admit(self, geometry=None, mounts=None, others=()):
        row = p.admit_common_root(geometry or self.geometry, self.mounts if mounts is None else mounts,
                                 str(self.library), str(self.retention), list(others))
        self.addCleanup(p.close_common_root, row)
        return row

    def test_exact_root9_and_original_three_directory_descriptors_survive_descendant_writes(self):
        row = self.admit()
        for directory in (self.library, self.retention):
            (directory / 'owned').write_bytes(b'private')
        p.check_common_root(row)
        self.assertEqual(p.nine(os.fstat(row[0])), self.geometry['common_root']['signature9'])
        self.assertEqual([os.fstat(fd).st_ino for fd in row[2]], [x.stat().st_ino for x in (self.library, self.retention)])

    def test_root_timestamp_drift_refuses_with_unchanged_namespace(self):
        row = self.admit()
        z = self.root.stat()
        os.utime(self.root, ns=(z.st_atime_ns, z.st_mtime_ns + 1))
        with self.assertRaisesRegex(p.Held, 'archive-common-original-root-FD9'):
            p.check_common_root(row)

    def test_extra_entry_refuses(self):
        (self.root / 'foreign').mkdir()
        value = copy.deepcopy(self.geometry)
        value['common_root']['signature9'] = p.nine(self.root.stat())
        with self.assertRaisesRegex(p.Held, 'archive-common-exact-namespace'):
            self.admit(value)

    def test_nested_readonly_or_writable_shadow_refuses(self):
        for write in (True, False):
            with self.subTest(write=write), self.assertRaisesRegex(p.Held, 'archive-common-no-nested-or-shadow-bind'):
                self.admit(mounts=[*self.mounts, dict(host=str(self.library), child=str(self.library), write=write)])

    def test_aliased_child_and_writable_ancestor_refuse(self):
        for mounts in ([dict(host=str(self.root), child='/different-common-root', write=True)],
                       [*self.mounts, dict(host=str(self.base), child='/other', write=True)]):
            with self.subTest(mounts=mounts), self.assertRaises(p.Held):
                self.admit(mounts=mounts)

    def test_other_role_overlap_and_symlink_refuse(self):
        with self.assertRaisesRegex(p.Held, 'archive-common-other-scope-overlap'):
            self.admit(others=[str(self.library / 'native-data')])
        self.library.rename(self.base / 'displaced-library')
        self.library.symlink_to(self.base / 'displaced-library', target_is_directory=True)
        with self.assertRaises(p.Held):
            self.admit()

    def test_swapped_child_refuses_without_rebaseline(self):
        row = self.admit()
        original = os.fstat(row[2][0]).st_ino
        self.library.rename(self.base / 'retained-original-library')
        self.library.mkdir(mode=0o700)
        self.assertEqual(os.fstat(row[2][0]).st_ino, original)
        with self.assertRaises(p.Held):
            p.check_common_root(row)

    def searchable(self):
        if self.root.name=='common':
            root=self.base/('archive-publication-'+'a'*64);self.root.rename(root);self.root=root
            (root/'library').rename(root/'L');(root/'retention').rename(root/'R')
            self.library=root/'L';self.retention=root/'R'
            self.geometry.update(**{name:dict(path=str(path),signature9=p.nine(path.lstat()))for name,path in(('common_root',root),('library',self.library),('retention',self.retention))})
            self.mounts=[dict(host=str(root),child=str(root),write=True)]
        self.root.chmod(0o711)
        value=copy.deepcopy(self.geometry)
        value.update(version=2,kind='searchable-common-root-nfs')
        value['common_root']['signature9']=p.nine(self.root.lstat())
        return value

    def test_searchable_variant_keeps_private_leaves_and_full_custody(self):
        value=self.searchable();row=self.admit(value)
        p.check_common_root(row)
        self.assertEqual(value['common_root']['signature9'][5]&0o777,0o711)
        self.assertEqual([os.fstat(fd).st_mode&0o777 for fd in row[2]],[0o700,0o700])
        self.root.chmod(0o700)
        with self.assertRaises(p.Held):p.check_common_root(row)

    def test_searchable_variant_rejects_other_modes_and_leaf_access(self):
        self.searchable()
        for role,path in [('common_root',self.root),('library',self.library),('retention',self.retention)]:
            for mode in (0o755,0o777,0o710,0o702):
                with self.subTest(role=role,mode=mode):
                    value=self.searchable();path.chmod(mode);value[role]['signature9']=p.nine(path.lstat())
                    with self.assertRaises(p.Held):self.admit(value)
                    path.chmod(0o700)

    def test_legacy_geometry_does_not_accept_searchable_root(self):
        value=self.searchable();value.update(version=1,kind='private-common-root-nfs')
        with self.assertRaises(p.Held):self.admit(value)

    def test_searchable_variant_retains_extra_shadow_and_foreign_owner_refusals(self):
        self.root.chmod(0o711);wrong=copy.deepcopy(self.geometry);wrong.update(version=2,kind='searchable-common-root-nfs');wrong['common_root']['signature9']=p.nine(self.root.lstat())
        with self.assertRaisesRegex(p.Held,'archive-common-disposable-names'):self.admit(wrong)
        value=self.searchable()
        with self.assertRaises(p.Held):self.admit(value,mounts=[*self.mounts,dict(host=str(self.library),child=str(self.library),write=False)])
        foreign=copy.deepcopy(value);foreign['common_root']['signature9'][6]=1001
        with self.assertRaises(p.Held):self.admit(foreign)
        (self.root/'foreign').mkdir();value['common_root']['signature9']=p.nine(self.root.lstat())
        with self.assertRaises(p.Held):self.admit(value)


if __name__ == '__main__':
    unittest.main()

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


if __name__ == '__main__':
    unittest.main()

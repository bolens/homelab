import sys
from pathlib import Path as _SourcePath
sys.path.insert(0, str(_SourcePath(__file__).parent))
"""Mountinfo mechanism controls; no Docker, privilege or factual authority."""
import unittest

import comic_nfs_parent_session as p


class Mounts(unittest.TestCase):
    def setUp(self):
        self.rows=[
            '1 99 0:1 / / ro - overlay overlay rw',
            '2 1 0:2 /library /protected ro - nfs4 server:/export rw',
            '3 1 0:3 /private/tree /work rw - btrfs /dev/disk rw',
            '4 1 0:2 /retention /retention rw - nfs4 server:/export rw',
            '5 1 0:4 / /proc rw - proc proc rw',
        ]

    def observe(self):
        return p.readonly_mount_observation(('\n'.join(self.rows)+'\n').encode(),
                                            ['/protected'],['/work','/retention'])

    def test_disjoint_realized_readonly_binding_returns_facts_only(self):
        result=self.observe()
        self.assertEqual(set(result['protected']),{'/protected'})
        self.assertFalse(result['mutation_authority'])
        self.assertFalse(result['publication_authority'])

    def test_writable_protected_binding_refuses(self):
        self.rows[1]=self.rows[1].replace('/protected ro','/protected rw')
        with self.assertRaisesRegex(p.Held,'protected-submount'):self.observe()

    def test_writable_nested_other_filesystem_refuses(self):
        self.rows.append('6 2 0:5 / /protected/nested rw - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'protected-submount'):self.observe()

    def test_readonly_nested_other_filesystem_accepts(self):
        self.rows.append('6 2 0:5 / /protected/nested ro - tmpfs tmpfs rw')
        self.observe()

    def test_writable_alias_of_readonly_nested_other_filesystem_refuses(self):
        self.rows.extend(['6 2 0:5 / /protected/nested ro - tmpfs tmpfs rw',
                          '7 1 0:5 / /alias rw - tmpfs tmpfs rw'])
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_writable_descendant_alias_of_readonly_nested_nfs_on_other_superblock_refuses(self):
        self.rows.extend(['6 2 0:6 /nested /protected/nested ro - nfs4 other:/export rw',
                          '7 1 0:7 /nested/sub /alias rw - nfs4 other:/export rw'])
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_readonly_protected_row_hidden_by_writable_ancestor_refuses(self):
        self.rows[1]=self.rows[1].replace('/protected ro','/ancestor/protected ro')
        self.rows.append('6 1 0:9 / /ancestor rw - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'hidden-mount'):
            p.readonly_mount_observation(('\n'.join(self.rows)+'\n').encode(),
                                         ['/ancestor/protected'],['/work','/retention'])

    def test_visible_protected_mount_under_readonly_ancestor_accepts(self):
        self.rows[1]=self.rows[1].replace('2 1','2 6').replace('/protected ro','/ancestor/protected ro')
        self.rows.append('6 1 0:9 / /ancestor ro - tmpfs tmpfs rw')
        p.readonly_mount_observation(('\n'.join(self.rows)+'\n').encode(),
                                    ['/ancestor/protected'],['/work','/retention'])

    def test_shared_ancestor_above_protected_mount_refuses(self):
        self.rows[1]=self.rows[1].replace('2 1','2 6').replace('/protected ro','/ancestor/protected ro')
        self.rows.append('6 1 0:9 / /ancestor ro shared:7 - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'protected-submount'):
            p.readonly_mount_observation(('\n'.join(self.rows)+'\n').encode(),
                                         ['/ancestor/protected'],['/work','/retention'])

    def test_writable_alias_of_same_physical_root_refuses(self):
        self.rows.append('6 1 0:2 /library /alias rw - nfs4 server:/export rw')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_writable_alias_of_physical_descendant_refuses(self):
        self.rows.append('6 1 0:2 /library/sub /alias rw - nfs4 server:/export rw')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_writable_alias_of_physical_ancestor_refuses(self):
        self.rows.append('6 1 0:2 / /alias rw - nfs4 server:/export rw')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_same_nfs_export_on_another_superblock_is_not_assumed_disjoint(self):
        self.rows.append('6 1 0:9 /library/sub /alias rw - nfs4 server:/export rw')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_different_tmpfs_instances_are_not_physical_aliases(self):
        self.rows[1]='2 1 0:8 / /protected ro - tmpfs tmpfs rw'
        self.rows.append('6 1 0:9 / /unrelated rw - tmpfs tmpfs rw')
        self.observe()

    def test_readonly_alias_does_not_create_writing_authority(self):
        self.rows.append('6 1 0:2 /library /alias ro - nfs4 server:/export rw')
        self.observe()

    def test_shared_protected_mount_refuses(self):
        self.rows[1]=self.rows[1].replace('ro -','ro shared:41 -')
        with self.assertRaisesRegex(p.Held,'protected-submount'):self.observe()

    def test_slave_protected_mount_refuses(self):
        self.rows[1]=self.rows[1].replace('ro -','ro master:41 -')
        with self.assertRaisesRegex(p.Held,'protected-submount'):self.observe()

    def test_shared_descendant_refuses(self):
        self.rows.append('6 2 0:5 / /protected/nested ro shared:2 - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'protected-submount'):self.observe()

    def test_protected_root_must_be_an_actual_mountpoint(self):
        self.rows[1]=self.rows[1].replace('/protected ro','/protected/other ro')
        with self.assertRaisesRegex(p.Held,'exact-mount'):self.observe()

    def test_stacked_protected_mount_refuses(self):
        self.rows.append('6 1 0:9 / /protected ro - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'exact-mount'):self.observe()

    def test_duplicate_kernel_mount_id_refuses(self):
        self.rows.append('2 1 0:9 / /other ro - tmpfs tmpfs rw')
        with self.assertRaisesRegex(p.Held,'duplicate-id'):self.observe()

    def test_writable_root_filesystem_refuses(self):
        self.rows[0]=self.rows[0].replace('/ ro','/ rw')
        with self.assertRaisesRegex(p.Held,'root-filesystem'):self.observe()

    def test_missing_owned_writable_mount_refuses(self):
        self.rows.pop(2)
        with self.assertRaisesRegex(p.Held,'exact-mount'):self.observe()

    def test_readonly_owned_writable_mount_refuses(self):
        self.rows[2]=self.rows[2].replace('/work rw','/work ro')
        with self.assertRaisesRegex(p.Held,'owned-writable'):self.observe()

    def test_escaped_mount_paths_are_decoded_before_alias_comparison(self):
        self.rows[1]=self.rows[1].replace('/library','/library\\040space')
        self.rows.append('6 1 0:2 /library\\040space/sub /alias rw - nfs4 server:/export rw')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_unknown_mountinfo_escape_refuses(self):
        self.rows[1]=self.rows[1].replace('/library','/library\\777')
        with self.assertRaisesRegex(p.Held,'mountinfo-escape'):self.observe()

    def test_ambiguous_readwrite_options_refuse(self):
        self.rows[1]=self.rows[1].replace('/protected ro','/protected ro,rw')
        with self.assertRaisesRegex(p.Held,'mountinfo-options'):self.observe()

    def test_lexically_overlapping_writable_scope_refuses(self):
        with self.assertRaisesRegex(p.Held,'scope-disjoint'):
            p.readonly_mount_observation(b'not consumed',['/protected'],['/protected/work','/retention'])

    def test_saved_observation_is_plain_data_not_parent_capability(self):
        result=self.observe()
        self.assertIs(type(result),dict)
        self.assertFalse(result['mutation_authority'])


if __name__=='__main__':unittest.main()

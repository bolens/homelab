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
            '2 1 0:2 / /protected ro - nfs4 server:/export/library rw,addr=192.0.2.1',
            '3 1 0:3 /private/tree /work rw - btrfs /dev/disk rw',
            '4 1 0:2 / /retention rw - nfs4 server:/export/retention rw,addr=192.0.2.1',
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
        self.rows.extend(['6 2 0:6 / /protected/nested ro - nfs4 other:/export/nested rw,addr=192.0.2.1',
                          '7 1 0:7 / /alias rw - nfs4 other:/export/nested/sub rw,addr=192.0.2.1'])
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
        self.rows.append('6 1 0:2 / /alias rw - nfs4 server:/export/library rw,addr=192.0.2.1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_writable_alias_of_physical_descendant_refuses(self):
        self.rows.append('6 1 0:2 / /alias rw - nfs4 server:/export/library/sub rw,addr=192.0.2.1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_writable_alias_of_physical_ancestor_refuses(self):
        self.rows.append('6 1 0:2 / /alias rw - nfs4 server:/export rw,addr=192.0.2.1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_same_nfs_export_on_another_superblock_is_not_assumed_disjoint(self):
        self.rows.append('6 1 0:9 / /alias rw - nfs4 server:/export/library/sub rw,addr=192.0.2.1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_nfs_sibling_name_prefix_is_not_ancestry(self):
        self.rows.append('6 1 0:2 / /alias rw - nfs4 alias:/export/library-extra rw,addr=192.0.2.1')
        self.observe()

    def test_same_address_different_dns_spelling_still_detects_alias(self):
        self.rows.append('6 1 0:9 / /alias rw - nfs4 alias:/export/library/sub rw,addr=192.0.2.1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_same_device_different_address_still_detects_alias(self):
        self.rows.append('6 1 0:2 / /alias rw - nfs4 alias:/export/library/sub rw,addr=192.0.2.9')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_distinct_unproven_server_identity_refuses(self):
        self.rows[3]=self.rows[3].replace('0:2','0:9').replace('addr=192.0.2.1','addr=192.0.2.9')
        with self.assertRaisesRegex(p.Held,'unproved-nfs-device'):self.observe()

    def test_nfs_protocol_namespaces_are_not_assumed_equivalent(self):
        self.rows[3]=self.rows[3].replace('nfs4','nfs')
        with self.assertRaisesRegex(p.Held,'nfs-protocol'):self.observe()

    def test_nfs_non_nfs_device_collision_refuses(self):
        self.rows[3]='4 1 0:2 / /retention rw - tmpfs tmpfs rw'
        with self.assertRaisesRegex(p.Held,'filesystem-identity'):self.observe()

    def test_non_kernel_nfs_root_refuses(self):
        self.rows[1]=self.rows[1].replace('0:2 / ', '0:2 /library ')
        with self.assertRaisesRegex(p.Held,'nfs-root'):self.observe()

    def test_same_address_different_port_on_other_device_refuses(self):
        self.rows[3]=self.rows[3].replace('0:2','0:9')+',port=2050'
        with self.assertRaisesRegex(p.Held,'unproved-nfs-device'):self.observe()

    def test_ambiguous_nfs_source_refuses(self):
        for source in ('server:relative','server:/export/../library','server:/export//library',
                       '[not-an-address]:/export/library','server,other:/export/library'):
            with self.subTest(source=source):
                old=self.rows[1];self.rows[1]=old.replace('server:/export/library',source)
                try:
                    with self.assertRaises(p.Held):self.observe()
                finally:self.rows[1]=old

    def test_ipv6_source_spelling_preserves_same_device_alias_checks(self):
        self.rows=[r.replace('server:', '[2001:db8::1]:').replace('addr=192.0.2.1','addr=2001:db8::1')
                   for r in self.rows]
        self.observe()
        self.rows.append('6 1 0:2 / /alias rw - nfs4 [2001:0db8:0:0:0:0:0:1]:/export/library/sub rw,addr=2001:0db8:0:0:0:0:0:1')
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_same_local_device_disjoint_paths_accept(self):
        self.rows[1]='2 1 0:3 /private/library /protected ro - btrfs /dev/disk rw'
        self.observe()

    def test_same_local_device_ancestor_alias_refuses(self):
        self.rows[1]='2 1 0:3 /private /protected ro - btrfs /dev/disk rw'
        with self.assertRaisesRegex(p.Held,'physical-alias'):self.observe()

    def test_different_tmpfs_instances_are_not_physical_aliases(self):
        self.rows[1]='2 1 0:8 / /protected ro - tmpfs tmpfs rw'
        self.rows.append('6 1 0:9 / /unrelated rw - tmpfs tmpfs rw')
        self.observe()

    def test_readonly_alias_does_not_create_writing_authority(self):
        self.rows.append('6 1 0:2 / /alias ro - nfs4 server:/export/library rw,addr=192.0.2.1')
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
        self.rows.append('6 1 0:2 / /alias rw - nfs4 server:/export/library\\040space/sub rw,addr=192.0.2.1')
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

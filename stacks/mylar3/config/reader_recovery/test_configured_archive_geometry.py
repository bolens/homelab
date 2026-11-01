"""Production geometry must use existing configured authority, never fixture names."""
import copy
import stat
from pathlib import Path
import tempfile
import unittest
import sys
sys.path.insert(0,str(Path(__file__).parent))
import comic_reader_lifecycle_parent as p


def geometry():
    def directory(inode, uid, gid, mode):
        return [7, inode, 4096, 11, 12, stat.S_IFDIR | mode, uid, gid, 2]
    root = '/configured/media'
    common = directory(1, 99, 100, 0o777)
    library = directory(2, 1000, 100, 0o777)
    retention = directory(3, 1000, 1000, 0o700)
    def identity(value):return [value[i] for i in (0, 1, 5, 6, 7)]
    return dict(version=3, kind='configured-common-root-nfs',
                common_root=dict(path=root, signature9=common),
                library=dict(path=root + '/comics', signature9=library),
                retention=dict(path=root + '/.private-repair', signature9=retention),
                source_mount=dict(host=root, child='/data', write=True),
                namespace={'comics': identity(library), '.private-repair': identity(retention),
                           'manga': identity(directory(4, 1000, 100, 0o777)),
                           'books': identity(directory(5, 1000, 100, 0o777))})


class ConfiguredGeometry(unittest.TestCase):
    def setUp(self):
        self.value = geometry()
        self.mounts = [dict(self.value['source_mount'])]
        self.native = dict(Mounts=[dict(Type='bind', Source='/configured/media', Destination='/data', RW=True)])

    def admit(self, value=None, mounts=None, native=None):
        return p.configured_common_root(value or self.value,
                                        self.mounts if mounts is None else mounts,
                                        self.native if native is None else native,
                                        '/configured/media/comics', '/configured/media/.private-repair')

    def test_existing_export_permissions_and_complete_namespace(self):
        before = copy.deepcopy(self.value)
        self.admit()
        self.assertEqual(self.value, before)

    def test_root_is_exact_existing_native_mount_not_a_new_ancestor(self):
        self.native['Mounts'][0]['Source'] += '/narrower'
        with self.assertRaises(p.Held):self.admit()

    def test_readonly_native_mount_cannot_grant_writes(self):
        self.native['Mounts'][0]['RW'] = False
        with self.assertRaises(p.Held):self.admit()

    def test_unconfigured_child_spelling_refuses(self):
        self.value['source_mount']['child'] = '/other'
        self.mounts = [dict(self.value['source_mount'])]
        with self.assertRaises(p.Held):self.admit()

    def test_nested_writable_or_readonly_alias_refuses(self):
        for write in (False, True):
            with self.subTest(write=write), self.assertRaises(p.Held):
                self.admit(mounts=self.mounts + [dict(host='/configured/media/comics', child='/alias', write=write)])

    def test_shadow_child_mount_refuses(self):
        with self.assertRaises(p.Held):
            self.admit(mounts=self.mounts + [dict(host='/unrelated', child='/data/comics', write=False)])

    def test_retention_stays_private_without_changing_library_modes(self):
        self.value['retention']['signature9'][5] = stat.S_IFDIR | 0o777
        with self.assertRaises(p.Held):self.admit()

    def test_namespace_cannot_omit_selected_children(self):
        del self.value['namespace']['comics']
        with self.assertRaises(p.Held):self.admit()

    def test_namespace_paths_are_one_component(self):
        self.value['namespace']['../outside'] = self.value['namespace']['books']
        with self.assertRaises(p.Held):self.admit()

    def test_namespace_selected_identity_must_match_original(self):
        self.value['namespace']['comics'][1] += 1
        with self.assertRaises(p.Held):self.admit()

    def test_source_mount_cannot_be_duplicated(self):
        with self.assertRaises(p.Held):self.admit(mounts=self.mounts * 2)

    def test_different_filesystem_children_refuse(self):
        self.value['library']['signature9'][0] += 1
        with self.assertRaises(p.Held):self.admit()

    def test_legacy_geometry_cannot_borrow_configured_authority(self):
        self.value['version'] = 2
        self.value['kind'] = 'searchable-common-root-nfs'
        with self.assertRaises(p.Held):self.admit()


class ConfiguredFilesystem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'existing-export'; self.root.mkdir(mode=0o777)
        self.library = self.root / 'comics'; self.library.mkdir(mode=0o777)
        self.retention = self.root / '.private-repair'; self.retention.mkdir(mode=0o700)
        self.other = self.root / 'manga'; self.other.mkdir(mode=0o775)
        self.value = dict(version=3, kind='configured-common-root-nfs',
            **{name: dict(path=str(path), signature9=p.nine(path.lstat())) for name, path in
               (('common_root', self.root), ('library', self.library), ('retention', self.retention))},
            source_mount=dict(host=str(self.root), child='/data', write=True),
            namespace={path.name: p.five(path.lstat()) for path in self.root.iterdir()})
        self.mounts = [self.value['source_mount']]
        self.native = dict(Mounts=[dict(Type='bind', Source=str(self.root), Destination='/data', RW=True)])

    def admit(self):
        row = p.admit_common_root(self.value, self.mounts, str(self.library), str(self.retention), [],
                                  native_profile=self.native)
        self.addCleanup(p.close_common_root, row); return row

    def test_original_modes_and_siblings_survive_owned_descendant_changes(self):
        row = self.admit()
        for path in (self.library, self.retention):(path / 'owned').write_bytes(b'owned')
        p.check_common_root(row)
        self.assertEqual(p.five(self.other.lstat()), self.value['namespace']['manga'])
        self.assertEqual(p.nine(self.root.lstat()), self.value['common_root']['signature9'])

    def test_sibling_identity_drift_refuses_even_with_unchanged_root9(self):
        row = self.admit(); self.other.chmod(0o700)
        with self.assertRaises(p.Held):p.check_common_root(row)

    def test_namespace_cannot_refresh_after_admission(self):
        row = self.admit(); (self.root / 'unrelated').mkdir()
        with self.assertRaises(p.Held):p.check_common_root(row)

    def test_source_symlink_cannot_borrow_original_directory(self):
        moved = self.library.with_name('moved'); self.library.rename(moved)
        self.library.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(p.Held):self.admit()

    def test_unbound_profile_cannot_admit_production_geometry(self):
        with self.assertRaises(p.Held):
            p.admit_common_root(self.value, self.mounts, str(self.library), str(self.retention), [])


class ConfiguredOwnerReads(unittest.TestCase):
    """Real files with the existing credential double; no Root/NFS proof."""
    def setUp(self):
        import test_archive_common_root as legacy
        legacy.OwnerReadTests.setUp(self)
        self.parent=legacy.p; self.actor.release(); self.parent._OWNER_READS=None
        self.root.chmod(0o777);(self.root/'L').chmod(0o777);(self.root/'manga').mkdir(mode=0o775)
        self.geometry=dict(version=3,kind='configured-common-root-nfs',
            **{role:dict(path=str(path),signature9=self.parent.nine(path.lstat())) for role,path in
               (('common_root',self.root),('library',self.root/'L'),('retention',self.root/'R'))},
            source_mount=dict(host=str(self.root),child='/data',write=True),
            namespace={path.name:self.parent.five(path.lstat()) for path in self.root.iterdir()})
        self.actor=self.parent.bind_owner_reads(self.geometry);self.addCleanup(self.actor.release)

    def test_configured_actor_preserves_original_group_modes_and_root_identity(self):
        self.actor.check()
        self.assertEqual(self.uid,0)
        self.assertEqual(self.actor.geometry,self.geometry)
        self.assertEqual(self.actor.stat(str(self.root/'L')).st_mode & 0o777,0o777)

    def test_actor_cannot_adopt_replaced_sibling(self):
        (self.root/'manga').chmod(0o700)
        with self.assertRaises(self.parent.Held):self.actor.check()
        self.assertEqual(self.uid,0)

    def test_actor_cannot_adopt_mutated_namespace_fact(self):
        self.actor.geometry['namespace']['manga'][1]+=1
        with self.assertRaises(self.parent.Held):self.actor.check()
        self.assertEqual(self.uid,0)

    def test_configured_probe_binding_uses_original_retention_without_fixture_names(self):
        from unittest.mock import patch
        q=self.parent
        native=dict(Mounts=[dict(Type='bind',Source=str(self.root),Destination='/data',RW=True)])
        row=q.admit_common_root(self.geometry,[self.geometry['source_mount']],str(self.root/'L'),str(self.root/'R'),[],native_profile=native)
        self.addCleanup(q.close_common_root,row)
        owner=q.LifecycleParent.__new__(q.LifecycleParent)
        owner.plan=dict(version=13,kind='reviewed-archive-one-lifecycle-protocol',publication_geometry=self.geometry)
        owner.mapping=q.Paths([self.geometry['source_mount']]);owner.mapping.owner=owner
        q._ARCHIVE_COMMON_ROOTS[owner]=row;self.addCleanup(q._ARCHIVE_COMMON_ROOTS.pop,owner,None)
        fixture=self.root/'R'/('.comic-nfs-private-'+'b'*32)/('.comic-nfs-probe-'+'c'*32)
        with patch.object(q.LifecycleParent,'left',lambda self:None),patch.object(q.Paths,'nfs_roots',lambda unused:(str(self.root),)):
            result=owner.mapping.nfs_probe_binding(str(fixture))
        self.assertEqual(result['host_root'],str(self.root/'R'))
        self.assertEqual(result['child_root'],str(self.root/'R'))


class ConfiguredNFSMapping(unittest.TestCase):
    """Original production role shapes with synthetic inspection transport."""
    def setUp(self):
        import test_plan13_disposable_mapping as legacy
        self.case=legacy.Mapping('runTest');self.case.setUp();self.addCleanup(self.case.doCleanups)
        self.active=legacy.m;f=self.case
        f.common.rename(f.base/'existing-media');f.common=f.base/'existing-media'
        (f.common/'L').rename(f.common/'comics');(f.common/'R').rename(f.common/'.repair')
        f.library=f.common/'comics';f.retention=f.common/'.repair';(f.common/'manga').mkdir()
        f.common.chmod(0o777);f.library.chmod(0o777)
        f.geometry=dict(version=3,kind='configured-common-root-nfs',
            **{role:dict(path=str(path),signature9=self.active.stamp(path)) for role,path in
               (('common_root',f.common),('library',f.library),('retention',f.retention))},
            source_mount=dict(host=str(f.common),child='/data',write=True),
            namespace={path.name:p.five(path.lstat()) for path in f.common.iterdir()})
        for row in f.rows:row['Name']='/configured-'+row['Name'].rsplit('-',1)[-1]
        f.rows[0]['Mounts']=[dict(Type='volume',Driver='local',Source=str(f.state/'native'),Destination='/config',RW=True),
                             dict(Type='bind',Source=str(f.common),Destination='/data',RW=True)]
        f.rows[2]['Mounts']=[dict(Type='bind',Source=str(f.common/name),Destination='/data/'+name,RW=False) for name in ('comics','manga')]
        f.plan.update(publication_geometry=f.geometry,native=dict(data='/config',roots=['/data/comics']),
                      mounts=[f.geometry['source_mount'],dict(host=str(f.operation),child='/_operation',write=True)])
        f.seal()

    def mapping(self):return self.case.mapping([self.case.library,self.case.common/'manga'])

    def test_original_production_roles_map_without_disposable_names(self):
        value=self.mapping()
        self.assertEqual(self.active.selected_library_root(value,self.case.roles),self.case.library)
        self.assertEqual({row['destination'] for row in value['media_mounts']},{'/data/comics','/data/manga'})

    def test_readonly_native_cannot_grant_production_write_geometry(self):
        self.case.rows[0]['Mounts'][1]['RW']=False;self.case.seal()
        with self.assertRaises(self.active.Held):self.mapping()

    def test_foreign_action_cannot_borrow_configured_geometry(self):
        self.case.plan['action']='negative-five';self.case.seal()
        with self.assertRaises(self.active.Held):self.mapping()

    def test_wrong_original_native_bind_does_not_match_geometry(self):
        self.case.rows[0]['Mounts'][1]['Destination']='/elsewhere';self.case.seal()
        with self.assertRaises(self.active.Held):self.mapping()


class ReaderBackupMounts(unittest.TestCase):
    """Actual mapping/volume checks with read-only transport responses only."""
    def setUp(self):
        import types
        from test_nfs_current_roles import row
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.config=self.root/'reader';self.config.mkdir(mode=0o700)
        self.runtime=row(3,'reader','running')
        self.runtime['Mounts']=[dict(Type='volume',Driver='local',Name='reader_config',Source=str(self.config),Destination='/config',RW=True)]
        self.volume=dict(Name='reader_config',Driver='local',Scope='local',Mountpoint=str(self.config),Options=None)
        self.calls=[];self.emitted=[]
        def run(args,seconds):self.calls.append(args);return p.encode([copy.deepcopy(self.volume)])
        self.mounts=[dict(host=str(self.config),child=str(self.config),write=False)]
        self.owner=types.SimpleNamespace(continuous=lambda:dict(reader=copy.deepcopy(self.runtime)),plan={'mounts':self.mounts},mapping=p.Paths(self.mounts),engine=types.SimpleNamespace(run=run),left=lambda:30,emit=lambda name,value:self.emitted.append((name,value)))
    def call(self,projected=False):return p.LifecycleParent.reader_backup_preflight(self.owner,projected=projected)
    def test_default_volume_identity_checked_without_changing_runtime(self):
        before=copy.deepcopy(self.runtime);self.call();self.assertEqual(self.runtime,before)
        self.assertEqual(self.calls,[['volume','inspect','reader_config']]);self.assertEqual(len(self.emitted),1)
    def test_bind_identity_needs_no_volume_inspection(self):
        self.runtime['Mounts'][0]['Type']='bind';self.call();self.assertFalse(self.calls)
    def test_ordinary_nonidentity_volume_refuses_before_stop(self):
        self.mounts[0]['child']='/reader-config';self.owner.mapping=p.Paths(self.mounts)
        with self.assertRaisesRegex(p.Held,'backup-host-path-not-mounted-canonically'):self.call()
        self.assertFalse(self.calls)
    def test_configured_readonly_volume_projection_is_explicit(self):
        self.mounts[0]['child']='/reader-config';self.owner.mapping=p.Paths(self.mounts)
        self.call(projected=True);self.assertEqual(self.calls,[['volume','inspect','reader_config']])
    def test_driver_backends_that_detach_at_stop_are_refused(self):
        for options in ({'type':'nfs','device':'example.invalid:/export'},{'type':'none','o':'bind','device':'/other'}):
            self.volume['Options']=options
            with self.subTest(options=options),self.assertRaisesRegex(p.Held,'reader-backup-volume-backing'):self.call()
        self.assertFalse(self.emitted)
    def test_volume_identity_and_scope_cannot_be_substituted(self):
        for key,value in (('Name','foreign'),('Driver','foreign'),('Scope','global'),('Mountpoint','/foreign')):
            before=copy.deepcopy(self.volume);self.volume[key]=value
            with self.subTest(key=key),self.assertRaisesRegex(p.Held,'reader-backup-volume-backing'):self.call()
            self.volume=before
        self.assertFalse(self.emitted)
    def test_ordinary_bind_and_volume_helper_shadows_refuse_before_inspection(self):
        for kind in ('bind','volume'):
            self.runtime['Mounts'][0]['Type']=kind
            for suffix in ('subdir','database.sqlite'):
                shadow=dict(host='/other',child=str(self.config/suffix),write=False)
                self.owner.plan['mounts']=[self.mounts[0],shadow];self.owner.mapping=p.Paths(self.owner.plan['mounts'])
                with self.subTest(kind=kind,suffix=suffix),self.assertRaisesRegex(p.Held,'reader-backup-projection-shadow'):self.call()
        self.assertFalse(self.calls)

    def test_configured_helper_host_and_child_shadows_refuse_before_inspection(self):
        self.mounts[0]['child']='/reader-config'
        for shadow in (dict(host='/other',child='/reader-config/subdir',write=False),dict(host='/other',child='/reader-config/database.sqlite',write=False),dict(host=str(self.config/'subdir'),child='/other',write=False)):
            self.owner.plan['mounts']=[self.mounts[0],shadow];self.owner.mapping=p.Paths(self.owner.plan['mounts'])
            with self.subTest(shadow=shadow),self.assertRaisesRegex(p.Held,'reader-backup-projection-shadow'):self.call(projected=True)
        self.assertFalse(self.calls)


if __name__ == '__main__':unittest.main()

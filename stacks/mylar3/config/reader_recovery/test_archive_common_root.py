"""Actual private directory custody; no Docker, NFS or Parent admission claims."""
import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).parent
import sys
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import publication_native_configured_scope as owning_scope_parser
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


class ProbeRetentionBinding(unittest.TestCase):
    """Actual common-root FD custody; Parent left() explicitly projected."""
    setUp=Tests.setUp
    admit=Tests.admit
    searchable=Tests.searchable
    def mapping(self,searchable=True):
        from unittest.mock import patch
        value=self.searchable() if searchable else self.geometry;row=self.admit(value)
        owner=p.LifecycleParent.__new__(p.LifecycleParent)
        owner.plan=dict(version=13,kind='reviewed-archive-one-lifecycle-protocol',publication_geometry=value)
        mapping=p.Paths(self.mounts);owner.mapping=mapping;mapping.owner=owner
        p._ARCHIVE_COMMON_ROOTS[owner]=row
        self.addCleanup(p._ARCHIVE_COMMON_ROOTS.pop,owner,None)
        self.patch=patch.object(p.LifecycleParent,'left',lambda self:None);self.patch.start();self.addCleanup(self.patch.stop)
        self.root_patch=patch.object(p.Paths,'nfs_roots',lambda self:(str(value['common_root']['path']),));self.root_patch.start();self.addCleanup(self.root_patch.stop)
        self.fixture=self.retention/('.comic-nfs-private-'+'b'*32)/('.comic-nfs-probe-'+'c'*32)
        return mapping,row
    def test_original_retention_descriptor_uses_birth_identity5(self):
        mapping,row=self.mapping();before=mapping.nfs_probe_binding(str(self.fixture))
        (self.retention/'unrelated').write_bytes(b'original')
        self.assertEqual(mapping.nfs_probe_binding(str(self.fixture)),before)
        self.assertEqual(before,dict(host_root=str(self.retention),child_root=str(self.retention),root5=[self.geometry['retention']['signature9'][i] for i in (0,1,5,6,7)]))
    def test_retention_binding_observes_one_original_root_set(self):
        mapping,row=self.mapping();original=mapping.nfs_roots;calls=[]
        def roots():
            calls.append(True)
            return original()
        mapping.nfs_roots=roots
        mapping.nfs_probe_binding(str(self.fixture))
        self.assertEqual(len(calls),1)
    def test_retention_swap_during_root_observation_refuses(self):
        mapping,row=self.mapping();original=mapping.nfs_roots
        def changed():
            roots=original()
            self.retention.rename(self.root/'retained');self.retention.mkdir(mode=0o700)
            return roots
        mapping.nfs_roots=changed
        with self.assertRaises(p.Held):mapping.nfs_probe_binding(str(self.fixture))
    def test_missing_registry_and_foreign_geometry_refuse(self):
        mapping,row=self.mapping();owner=mapping.owner;p._ARCHIVE_COMMON_ROOTS.pop(owner)
        with self.assertRaises(p.Held):mapping.nfs_probe_binding(str(self.fixture))
        p._ARCHIVE_COMMON_ROOTS[owner]=row;owner.plan['publication_geometry']=dict(row[1],kind='foreign')
        with self.assertRaises(p.Held):mapping.nfs_probe_binding(str(self.fixture))
    def test_foreign_fixture_ancestor_or_names_refuse(self):
        mapping,row=self.mapping()
        for root in (self.library/self.fixture.name,self.fixture.parent,self.fixture.parent/'foreign',self.retention/'.comic-nfs-private-alias'/self.fixture.name):
            with self.subTest(root=root),self.assertRaises(p.Held):mapping.nfs_probe_binding(str(root))
    def test_retention_fd_swap_refuses(self):
        mapping,row=self.mapping();self.retention.rename(self.root/'retained');self.retention.mkdir(mode=0o700)
        with self.assertRaises(p.Held):mapping.nfs_probe_binding(str(self.fixture))
    def test_legacy_plan13_geometry_keeps_direct_fixture_binding(self):
        mapping,row=self.mapping(searchable=False)
        self.assertIsNone(mapping.nfs_probe_binding(str(self.fixture)))
    def test_legacy_mapping_does_not_gain_retention_bind(self):
        mapping,row=self.mapping();mapping.owner.plan['version']=12
        self.assertIsNone(mapping.nfs_probe_binding(str(self.fixture)))




class OwnerReadTests(unittest.TestCase):
    """Disposable real I/O; explicit credential double, not actual Root/NFS proof."""
    def setUp(self):
        from unittest import mock
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / ('archive-publication-' + 'b' * 64)
        self.root.mkdir(mode=0o711); self.root.chmod(0o711); (self.root / 'L').mkdir(mode=0o700); (self.root / 'R').mkdir(mode=0o700)
        self.geometry = dict(version=2, kind='searchable-common-root-nfs', **{role: dict(path=str(path), signature9=p.nine(path.lstat()))
            for role, path in (('common_root', self.root), ('library', self.root/'L'), ('retention', self.root/'R'))})
        self.uid = 0; self.events = []
        def switch(real, effective, saved):
            self.events.append(effective); self.uid = effective
        for name, value in (('getresuid', lambda: (0, self.uid, 0)), ('getresgid', lambda: (0, 0, 0)),
                            ('getgroups', lambda: [0]), ('geteuid', lambda: self.uid), ('setresuid', switch)):
            patch = mock.patch.object(p.os, name, side_effect=value); patch.start(); self.addCleanup(patch.stop)
        p._OWNER_READ_FAILED = False; self.addCleanup(setattr, p, '_OWNER_READ_FAILED', False)
        p._OWNER_READS = None; self.addCleanup(setattr, p, '_OWNER_READS', None)
        self.actor = p.bind_owner_reads(self.geometry); self.addCleanup(self.actor.release)

    def common_row(self):
        return p.admit_common_root(self.geometry,[dict(host=str(self.root),child=str(self.root),write=True)],
                                   str(self.root/'L'),str(self.root/'R'),[])

    def test_registered_common_root_uses_one_complete_geometry_check(self):
        row=self.common_row();before=len(self.events)
        p.check_common_root(row)
        self.assertEqual(len(self.events)-before,6)
        self.assertEqual(self.uid,0)

    def test_common_root_original_actor_registration_and_geometry_required(self):
        row=self.common_row();actor=row.actor
        try:
            row.actor=object()
            with self.assertRaises(p.Held):p.check_common_root(row)
        finally:row.actor=actor
        actor.common_roots.remove(row)
        try:
            with self.assertRaises(p.Held):p.check_common_root(row)
        finally:actor.common_roots.append(row)
        original=row[1]['kind'];row[1]['kind']='foreign'
        try:
            with self.assertRaises(p.Held):p.check_common_root(row)
        finally:row[1]['kind']=original

    def test_common_root_reused_child_descriptor_refuses(self):
        row=self.common_row();target=row[2][0];foreign=self.root.parent/'foreign';foreign.mkdir()
        other=os.open(foreign,os.O_RDONLY|os.O_DIRECTORY)
        try:
            os.dup2(other,target)
            with self.assertRaises(p.Held):p.check_common_root(row)
        finally:
            original=os.open(self.root/'L',os.O_RDONLY|os.O_DIRECTORY)
            try:os.dup2(original,target)
            finally:os.close(original);os.close(other)

    def test_common_root_checker_replacement_refuses_without_calling_it(self):
        from unittest import mock
        row=self.common_row()
        with mock.patch.object(p.GeometryOwnerReads,'check',side_effect=AssertionError('foreign checker')) as foreign:
            with self.assertRaises(p.Held):p.check_common_root(row)
            foreign.assert_not_called()

    def test_common_root_private_ancestor_keeps_owner_principal_fallback(self):
        from unittest import mock
        row=self.common_row();original=p.os.lstat;before=len(self.events)
        def private(path,*args,**kwargs):
            if self.uid==0 and str(path)==str(self.root):raise PermissionError('private ancestor projection')
            return original(path,*args,**kwargs)
        with mock.patch.object(p.os,'lstat',side_effect=private):p.check_common_root(row)
        self.assertEqual(len(self.events)-before,102)

    def after_geometry_check(self,mutation,restore=lambda:None):
        """Explicit late-callback projection; not genuine installed authority."""
        from unittest import mock
        self.actor.release();p._OWNER_READS=None;original=p.GeometryOwnerReads.check;armed=[False];row=None
        def checked(actor):
            original(actor)
            if armed[0]:
                armed[0]=False;mutation(row,actor)
        with mock.patch.object(p.GeometryOwnerReads,'check',checked):
            actor=self.actor=p.bind_owner_reads(self.geometry);roots=actor.common_roots
            try:
                row=self.common_row();armed[0]=True
                with self.assertRaises((p.Held,FileNotFoundError)):p.check_common_root(row)
            finally:
                armed[0]=False;restore();actor.common_roots=roots
                actor.release();p._OWNER_READS=None

    def test_common_root_late_ancestor_replacement_refuses_with_original_FDs(self):
        parent=self.root.parent;retained=parent.with_name(parent.name+'-retained')
        def mutation(row,actor):
            parent.rename(retained);parent.mkdir(mode=0o700)
        def restore():
            if retained.exists():parent.rmdir();retained.rename(parent)
        self.after_geometry_check(mutation,restore)

    def test_common_root_late_row_ledger_replacement_refuses(self):
        self.after_geometry_check(lambda row,actor:setattr(actor,'common_roots',list(actor.common_roots)))

    def test_common_root_changed_namespace_refuses(self):
        row=self.common_row();(self.root/'foreign').mkdir()
        with self.assertRaises(p.Held):p.check_common_root(row)

    def test_common_root_foreign_ancestor_ledger_never_reaches_Root_stat(self):
        from unittest import mock
        row=self.common_row();foreign=self.root.parent/'foreign';foreign.write_bytes(b'outside owned geometry')
        path=str(foreign);fact=p.five(foreign.lstat());seen=[];original=p.os.lstat
        self.actor.nodes[path]=row[3][path]=fact
        def observed(value,*args,**kwargs):
            seen.append(str(value));return original(value,*args,**kwargs)
        try:
            with mock.patch.object(p.os,'lstat',side_effect=observed),self.assertRaises(p.Held):p.check_common_root(row)
            self.assertNotIn(path,seen)
        finally:self.actor.nodes.pop(path);row[3].pop(path)

    def test_run_operation_release_then_late_finalizer_cannot_close_reused_fd(self):
        from unittest import mock
        import weakref
        owners=[];finalizers=[];rows=[];actor=self.actor
        class Owner:
            def __init__(inner,*args,**kwargs):
                inner.owner_reads=actor;row=self.common_row();rows.append(row);owners.append(inner)
                finalizers.append(weakref.finalize(inner,p.close_common_root,row))
            def execute(inner):return {'fixture_only':True}
        with mock.patch.object(p,'LifecycleParent',Owner):
            self.assertEqual(p.run_operation(None,None,engine=object()),{'fixture_only':True})
        self.assertIsNone(p._OWNER_READS);self.assertFalse(actor.handles)
        row=rows[0]
        for fd in (row[0],*row[2]):
            with self.assertRaises(OSError):os.fstat(fd)
        unrelated=self.root.parent/'unrelated';unrelated.write_bytes(b'unrelated-owned-fixture')
        fd=os.open(unrelated,os.O_RDONLY|os.O_NOFOLLOW);target=row[0]
        try:
            if fd!=target:os.dup2(fd,target)
            original=p.five(os.fstat(target));finalizers[0]()
            self.assertEqual(p.five(os.fstat(target)),original)
            self.assertEqual(os.pread(target,64,0),b'unrelated-owned-fixture')
        finally:
            for handle in {fd,target}:
                try:os.close(handle)
                except OSError:pass # Unit cleanup after original RED may already be closed.
        self.assertFalse(finalizers[0].alive)

    def test_constructor_refusal_preserves_primary_and_late_finalizer_is_safe(self):
        from unittest import mock
        import weakref
        primary=ValueError('original-constructor-refusal');owners=[];finalizers=[];rows=[];actor=self.actor
        class Owner:
            def __init__(inner,*args,**kwargs):
                inner.owner_reads=actor;row=self.common_row();rows.append(row);owners.append(inner)
                finalizers.append(weakref.finalize(inner,p.close_common_root,row));raise primary
        with mock.patch.object(p,'LifecycleParent',Owner),self.assertRaises(ValueError)as caught:
            p.run_operation(None,None,engine=object())
        self.assertIs(caught.exception,primary);self.assertFalse(actor.handles);self.assertIsNone(p._OWNER_READS)
        finalizers[0]()
        for fd in (rows[0][0],*rows[0][2]):
            with self.assertRaises(OSError):os.fstat(fd)

    def test_operation_primary_survives_cleanup_failure_and_all_fds_are_attempted(self):
        from unittest import mock
        import weakref
        primary=ValueError('original-execute-refusal');owners=[];finalizers=[];rows=[];actor=self.actor
        class Owner:
            def __init__(inner,*args,**kwargs):
                inner.owner_reads=actor;row=self.common_row();rows.append(row);owners.append(inner)
                finalizers.append(weakref.finalize(inner,p.close_common_root,row))
            def execute(inner):patcher.start();raise primary
        real=type(actor).close_directory;attempted=[]
        def close(owner,fd):
            self.assertIs(owner,actor);attempted.append(fd);real(owner,fd)
            if rows and fd==rows[0][0]:raise OSError('injected-close-failure-after-close')
        patcher=mock.patch.object(type(actor),'close_directory',close);self.addCleanup(patcher.stop)
        with mock.patch.object(p,'LifecycleParent',Owner),self.assertRaises(ValueError)as caught:
            p.run_operation(None,None,engine=object())
        patcher.stop()
        self.assertIs(caught.exception,primary);self.assertFalse(actor.handles)
        self.assertEqual(len(attempted),6);self.assertEqual(len(set(attempted)),6)
        finalizers[0]()
        self.assertEqual(len(attempted),6)

    def test_common_admission_refusal_deregisters_all_opened_fds(self):
        from unittest import mock
        before=set(self.actor.handles);primary=ValueError('original-admission-refusal')
        with mock.patch.object(p,'check_common_root',side_effect=primary),self.assertRaises(ValueError)as caught:self.common_row()
        self.assertIs(caught.exception,primary);self.assertEqual(set(self.actor.handles),before)
        self.actor.check();p.release_owner_reads(self.actor);self.assertFalse(self.actor.handles)

    def test_original_archive_bytes_hash_and_namespace_after_explicit_owner_read(self):
        import hashlib
        path = self.root/'L'/'target.cbz'; path.write_bytes(b'original-disposable')
        ref = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=p.nine(path.lstat()))
        self.assertEqual(p.read(ref, private=False), b'original-disposable')
        self.assertEqual(p.nfs_names(self.root/'L'), ('target.cbz',))
        self.assertEqual(self.uid, 0)
        self.assertEqual(self.events[-1], 0)

    def test_comma_file_metadata_and_original_vector_use_filesystem_spelling(self):
        path = self.root/'L'/'Series, Issue.cbz'; path.write_bytes(b'original')
        fact = p.nine(path.lstat())
        self.assertEqual(p.nine(p.nfs_lstat(path)), fact)
        self.assertEqual(p.nine(self.actor._run('stats', (str(path),))[0]), fact)
        self.actor.control_vector(((str(path), tuple(fact)),), ())
        self.assertEqual(self.uid, 0)

    def test_comma_directory_namespace_descriptor_and_canonical_checks(self):
        path = self.root/'L'/'Series, Annual'; path.mkdir(mode=0o700)
        (path/'Issue, One.cbz').write_bytes(b'original')
        self.assertEqual(p.nfs_names(path), ('Issue, One.cbz',))
        self.assertTrue(p.nfs_canonical(path))
        fd = p.nfs_directory(path)
        self.assertEqual(p.nfs_names(fd), ('Issue, One.cbz',))
        self.actor.close_directory(fd)
        self.actor.check()
        self.assertEqual(self.uid, 0)

    def test_comma_path_symlink_and_foreign_scope_still_refuse(self):
        path = self.root/'L'/'Series, Link'; path.symlink_to('/etc')
        with self.assertRaises(p.Held):self.actor.stat(path)
        with self.assertRaises((p.Held, OSError)):self.actor.stat(path/'passwd')
        with self.assertRaises(p.Held):self.actor.stat(self.root.parent/'Foreign, File')
        self.assertEqual(self.uid, 0)

    def test_comma_ancestor_replacement_and_validator_rebinding_refuse(self):
        from unittest import mock
        path = self.root/'L'/'Series, Annual'; path.mkdir(mode=0o700)
        fd = self.actor.directory(path)
        path.rename(path.with_name('retained-original')); path.mkdir(mode=0o700)
        with self.assertRaises(p.Held):self.actor.check()
        self.actor.close_directory(fd)
        with mock.patch.object(p, 'filesystem_absolute', side_effect=AssertionError('foreign validator')) as foreign:
            with self.assertRaises(p.Held):self.actor.stat(self.root/'L')
            foreign.assert_not_called()
        self.assertEqual(self.uid, 0)

    def test_comma_filesystem_admission_keeps_transport_and_mutation_spelling(self):
        value = str(self.root/'L'/'Series, Issue.cbz')
        self.assertEqual(p.filesystem_absolute(value), Path(value))
        with self.assertRaises(p.Held):p.absolute(value)
        for invalid in ('relative', '/a/../b', '/a//b', '/a/./b', '/a\n/b', '/a\r/b', '/a\\b', '/a\x00b'):
            with self.subTest(path=repr(invalid)), self.assertRaises(p.Held):p.filesystem_absolute(invalid)

    def test_missing_leaf_and_late_replacement_refuse_without_credential_loss(self):
        with self.assertRaises(FileNotFoundError):self.actor.stat(self.root/'L'/'missing')
        self.assertEqual(self.uid, 0)
        (self.root/'L').rename(self.root/'old'); (self.root/'L').mkdir(mode=0o700)
        with self.assertRaises(p.Held):self.actor.check()
        self.assertEqual(self.uid, 0)

    def test_symlink_escape_foreign_scope_and_write_operation_refuse(self):
        (self.root/'L'/'link').symlink_to('/etc/passwd')
        with self.assertRaises(p.Held):self.actor.stat(self.root/'L'/'link')
        for operation, path in (('file', '/etc/passwd'), ('write', str(self.root/'L'/'file'))):
            with self.assertRaises(p.Held):self.actor._run(operation, path)
        self.assertEqual(self.uid, 0)

    def test_wrong_hash_and_full9_refuse(self):
        path = self.root/'L'/'original'; path.write_bytes(b'original')
        ref = dict(path=str(path), sha256='0'*64, signature9=p.nine(path.lstat()))
        with self.assertRaises(p.Held):self.actor.read(ref)
        self.assertEqual(self.uid, 0)

    def test_extra_thread_trace_and_profile_refuse_before_switch(self):
        from unittest import mock
        for name, value, owner in (('active_count', 2, p.threading), ('gettrace', object(), p.sys), ('getprofile', object(), p.sys)):
            before = len(self.events)
            with mock.patch.object(owner, name, return_value=value), self.assertRaises(p.Held):self.actor.stat(self.root/'L')
            self.assertEqual(len(self.events), before)

    def test_no_scope_replacement_and_no_legacy_implicit_switch(self):
        with self.assertRaises(p.Held):p.bind_owner_reads(self.geometry)
        before = len(self.events)
        self.assertIsNone(p.bind_owner_reads(dict(version=1)))
        self.assertEqual(len(self.events), before)

    def test_restore_failure_poison_prevents_engine_guard_and_preserves_primary(self):
        from unittest import mock
        def fail_restore(real, effective, saved):
            if effective == 0:raise RuntimeError('disposable restoration failure')
            self.uid = effective
        enabled = p.gc.isenabled(); mask = p.signal.pthread_sigmask(p.signal.SIG_BLOCK, set())
        try:
            with mock.patch.object(p.os, 'setresuid', side_effect=fail_restore):
                with self.assertRaises(FileNotFoundError):self.actor.stat(self.root/'L'/'missing')
            self.assertTrue(self.actor.poisoned)
            with self.assertRaises(p.Held):p.owner_root_guard()
        finally:
            self.uid = 0
            p.signal.pthread_sigmask(p.signal.SIG_SETMASK, mask)
            if enabled:p.gc.enable()

    def test_gc_and_signals_only_restored_after_root_identity(self):
        from unittest import mock
        enable = p.gc.enable; restore = p.signal.pthread_sigmask
        def enable_checked():
            self.assertEqual(self.uid, 0); return enable()
        def mask_checked(how, values):
            if how == p.signal.SIG_SETMASK:self.assertEqual(self.uid, 0)
            return restore(how, values)
        with mock.patch.object(p.gc, 'enable', side_effect=enable_checked), mock.patch.object(p.signal, 'pthread_sigmask', side_effect=mask_checked):
            self.actor.stat(self.root/'L')

    def test_original_child_timestamps_may_change_but_each_read_full9_remains_strict(self):
        import hashlib
        path=self.root/'L'/'owned';path.write_bytes(b'original')
        ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=p.nine(path.lstat()))
        self.actor.check()  # Existing Parent deliberately retains L/R identity5.
        p.final({str(path):tuple(ref['signature9'])},{},())
        z=path.stat();os.utime(path,ns=(z.st_atime_ns,z.st_mtime_ns+1))
        with self.assertRaises(p.Held):p.read(ref,private=False)
        self.actor.check()

    def test_absence_distinguishes_permission_refusal_and_late_creation(self):
        from unittest import mock
        path=self.root/'R'/'absent'
        self.assertTrue(p.nfs_absent(path));p.final({}, {}, (str(path),))
        original_stat=p.os.stat
        def refused(name,*args,**kwargs):
            if name=='absent':raise PermissionError(13,'fixture only')
            return original_stat(name,*args,**kwargs)
        with mock.patch.object(p.os,'stat',side_effect=refused):
            with self.assertRaises(PermissionError):p.nfs_absent(path)
        path.mkdir(mode=0o700)
        with self.assertRaises(p.Held):p.final({}, {}, (str(path),))

    def test_scope_mutation_and_instance_method_shadowing_refuse(self):
        with self.assertRaises(AttributeError):self.actor.stat=lambda path:None
        old=self.actor.geometry['library']['path'];self.actor.geometry['library']['path']='/etc'
        with self.assertRaises(p.Held):p.owner_root_guard()
        self.actor.geometry['library']['path']=old

    def test_original_source_drift_refuses_before_switch(self):
        original=self.actor.source['signature9'];before=len(self.events)
        self.actor.source['signature9']=[*original[:3],original[3]+1,*original[4:]]
        with self.assertRaises(p.Held):self.actor.stat(self.root/'L')
        self.assertEqual(len(self.events),before);self.actor.source['signature9']=original

    def test_no_scope_root_read_refusal_is_not_retried_or_adopted(self):
        from unittest import mock
        path=self.root/'L'/'absent';p._OWNER_READS=None;before=len(self.events)
        try:
            with mock.patch.object(p.os,'lstat',side_effect=PermissionError(13,'fixture only')):
                with self.assertRaises(PermissionError):p.nfs_absent(path)
            self.assertEqual(len(self.events),before)
        finally:p._OWNER_READS=self.actor

    def test_closed_reused_descriptor_is_not_closed_as_owned(self):
        fd=self.actor.directory(self.root/'L');os.close(fd)
        foreign=os.open('/dev/null',os.O_RDONLY)
        try:
            if foreign!=fd:os.dup2(foreign,fd)
            with self.assertRaises(p.Held):self.actor.close_directory(fd)
            self.assertTrue(os.fstat(fd))
        finally:
            os.close(foreign)
            if foreign!=fd:os.close(fd)

    def test_constructor_primary_survives_release_secondary_failure(self):
        from unittest import mock
        geometry=copy.deepcopy(self.geometry);geometry['library']['signature9'][1]+=1
        original=p.GeometryOwnerReads.release
        def failed_release(actor):
            original(actor);raise RuntimeError('disposable secondary')
        with mock.patch.object(p.GeometryOwnerReads,'release',failed_release):
            with self.assertRaisesRegex(p.Held,'owner-read-original-directory5'):p.GeometryOwnerReads(geometry)
        self.assertEqual(self.uid,0)

    def test_owned_inode_is_closed_on_mode_refusal(self):
        fd=self.actor.directory(self.root/'L');os.chmod(self.root/'L',0o500)
        try:
            with self.assertRaisesRegex(p.Held,'owner-read-release-owned-FD5'):self.actor.close_directory(fd)
            with self.assertRaises(OSError):os.fstat(fd)
            self.assertNotIn(fd,self.actor.handles)
        finally:os.chmod(self.root/'L',0o700)

    def test_actual_composer_originals_close_owner_file_and_detect_late_change(self):
        import hashlib
        import genuine_plan13_producer as composer
        actor=composer.p.bind_owner_reads(self.geometry)
        try:
            path=self.root/'L'/'original.cbz';path.write_bytes(b'owning-original')
            ref=dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),signature9=composer.p.nine(path.lstat()))
            originals=composer.Originals();self.assertEqual(originals.read(ref,private=False),b'owning-original');originals.close()
            path.write_bytes(b'late-change')
            with self.assertRaises(composer.p.Held):originals.close()
        finally:composer.p.release_owner_reads(actor)

    def test_actual_current_roles_closes_fresh9_without_adopting_postcapture_drift(self):
        import time
        import genuine_current_roles as capture
        actor=capture.p.bind_owner_reads(self.geometry)
        owner=object.__new__(capture.Capture)
        try:
            owner.plan=dict(geometry=self.geometry);owner.originals=capture.composer.Originals()
            path=self.root/'L'/'new';path.write_bytes(b'bootstrap-added')
            owner.geometry_originals=copy.deepcopy(self.geometry)
            for role in ('common_root','library','retention'):
                owner.geometry_originals[role]['signature9']=owner._identity(self.geometry[role])
            owner.geometry=capture.p.admit_common_root(owner.geometry_originals,[dict(host=str(self.root),child=str(self.root),write=True)],str(self.root/'L'),str(self.root/'R'),[])
            for name in ('profiles','epochs','network_profile','native_process','sdk','sources'):setattr(owner,name,{})
            owner.end=time.monotonic()+30;owner.output_close=lambda:None
            owner.tape=capture.p.encode(dict(plan=owner.plan,profiles={},epochs={},network={},native_process={},sdk={},geometry=owner.geometry_originals,sources={}))
            owner.close();(self.root/'L'/'later').write_bytes(b'after-capture')
            actor.check()
            with self.assertRaisesRegex(capture.p.Held,'capture-current-directory-full9'):owner.close()
        finally:
            if getattr(owner,'geometry',None) is not None:capture.p.close_common_root(owner.geometry)
            capture.p.release_owner_reads(actor)

    def test_assembly_rejects_scope_from_different_parent_module_before_writes(self):
        import genuine_active_inputs as assembly
        output=self.root/'R'/'never-created'
        with self.assertRaisesRegex(assembly.p.Held,'active-owning-read-scope'):
            assembly.Assembly(None,output,owner_reads=self.actor)
        self.assertFalse(output.exists())

    def test_signal_gap_thread_is_refused_before_effective_uid_change(self):
        from unittest import mock
        original_mask=p.signal.pthread_sigmask;masked=[False];before=len(self.events)
        def mask(how,values):
            value=original_mask(how,values)
            if how==p.signal.SIG_BLOCK:masked[0]=True
            return value
        with mock.patch.object(p.signal,'pthread_sigmask',side_effect=mask),mock.patch.object(p.threading,'active_count',side_effect=lambda:2 if masked[0] else 1):
            with self.assertRaisesRegex(p.Held,'masked-single-untraced-thread'):self.actor.stat(self.root/'L')
        self.assertNotIn(1000,self.events[before:]);self.assertEqual(self.uid,0)

    def test_restoration_poison_survives_release_and_blocks_engine(self):
        from unittest import mock
        def restore_failure(real,effective,saved):
            if effective==0:raise RuntimeError('disposable restore failure')
            self.uid=effective
        enabled=p.gc.isenabled();mask=p.signal.pthread_sigmask(p.signal.SIG_BLOCK,set())
        try:
            with mock.patch.object(p.os,'setresuid',side_effect=restore_failure):
                with self.assertRaises(RuntimeError):self.actor.stat(self.root/'L')
        finally:
            self.uid=0;p.signal.pthread_sigmask(p.signal.SIG_SETMASK,mask)
            if enabled:p.gc.enable()
        p.release_owner_reads(self.actor)
        self.assertIsNone(p._OWNER_READS)
        with mock.patch.object(p.subprocess,'run') as spawn:
            with self.assertRaisesRegex(p.Held,'process-poison'):p.ScopedDocker().canary(['findmnt'])
            spawn.assert_not_called()
        with self.assertRaisesRegex(p.Held,'process-poison'):p.bind_owner_reads(self.geometry)

    def test_current_roles_constructor_postbind_refusal_releases_actor_and_fds(self):
        from unittest import mock
        import genuine_current_roles as capture
        import test_genuine_current_roles as fixture_source
        self.assertIs(capture.scope_parser, owning_scope_parser)
        self.assertEqual(Path(owning_scope_parser.__file__).absolute(), HERE.parent/'publication_native_configured_scope.py')
        with mock.patch.object(p.os,'geteuid',return_value=1000):
            fixture=fixture_source.Fixture(self)
            actor=capture.p.GeometryOwnerReads(self.geometry);held=tuple(actor.handles)
            def bind(geometry):capture.p._OWNER_READS=actor;return actor
            with mock.patch.object(p.os,'geteuid',return_value=1000),mock.patch.object(capture.p,'bind_owner_reads',side_effect=bind),mock.patch.object(capture.Capture,'_config',side_effect=ValueError('disposable original refusal')):
                with self.assertRaisesRegex(ValueError,'disposable original refusal'):fixture.owner()
            self.assertIsNone(capture.p._OWNER_READS);self.assertFalse(actor.handles)
            for fd in held:
                with self.assertRaises(OSError):os.fstat(fd)

    def test_composer_constructor_postbind_refusal_releases_actor_and_fds(self):
        from unittest import mock
        import genuine_plan13_producer as composer
        import test_genuine_plan13_producer as fixture_source
        with tempfile.TemporaryDirectory() as directory,mock.patch.object(p.os,'geteuid',return_value=1000):
            fixture=fixture_source.Fixture(Path(directory));actor=composer.p.GeometryOwnerReads(self.geometry);held=tuple(actor.handles)
            def bind(geometry):composer.p._OWNER_READS=actor;return actor
            with mock.patch.object(p.os,'geteuid',return_value=1000),mock.patch.object(composer.p,'bind_owner_reads',side_effect=bind),mock.patch.object(composer,'compose',side_effect=ValueError('disposable original refusal')):
                with self.assertRaisesRegex(ValueError,'disposable original refusal'):composer.Producer(fixture.put(fixture.doc),Path(directory)/'proposal-output')
            self.assertIsNone(composer.p._OWNER_READS);self.assertFalse(actor.handles)
            for fd in held:
                with self.assertRaises(OSError):os.fstat(fd)

    def test_tree_remote_input_ancestors_use_bound_owner_and_restore_root(self):
        from unittest import mock
        projection,tree,_,_=self.control_tree();path=self.root/'L'/'remote-source.json'
        path.write_bytes(b'{"remote":true}');path.chmod(0o600)
        ref=dict(path=str(path),sha256=p.hashlib.sha256(path.read_bytes()).hexdigest(),signature9=p.nine(path.lstat()))
        tree.reserve_nfs_control(ref,public=True);original=p.os.lstat;denied=[]
        def guarded(value,*args,**kwargs):
            target=Path(value) if isinstance(value,(str,Path))else None
            if self.uid==0 and target is not None and (target==self.root or self.root in target.parents):
                denied.append(str(target));raise PermissionError('Root cannot traverse this synthetic export')
            return original(value,*args,**kwargs)
        with mock.patch.object(p.os,'lstat',side_effect=guarded),mock.patch.object(p.os,'geteuid',return_value=os.getuid()):
            result=tree.project(ref);tree.check()
        self.assertEqual(Path(result['path']).read_bytes(),b'{"remote":true}')
        self.assertEqual(self.uid,0);self.assertEqual(denied,[])

    def test_archive_source_group_uses_owner_for_every_remote_ancestor(self):
        from unittest import mock
        projection,tree,_,_=self.control_tree();refs={}
        names=('comic_archive_backup_action.py','comic_archive_repair_action.py','comic_archive_evidence_adapter.py',
               'comic_archive_proof_producer.py','comic_reader_backup.py','comic_reader_backup_primitives.py',
               'comic_reader_schema.py','publication_native_configured_scope.py','comic_native_process_probe.py')
        for name in names:
            path=self.root/'L'/name;path.write_bytes(name.encode());path.chmod(0o600)
            refs[name]=dict(path=str(path),sha256=p.hashlib.sha256(path.read_bytes()).hexdigest(),signature9=p.nine(path.lstat()))
            tree.reserve_nfs_control(refs[name],public=True)
        original=p.os.lstat;denied=[]
        def guarded(value,*args,**kwargs):
            target=Path(value) if isinstance(value,(str,Path))else None
            if self.uid==0 and target is not None and (target==self.root or self.root in target.parents):
                denied.append(str(target));raise PermissionError('Root cannot traverse this synthetic export')
            return original(value,*args,**kwargs)
        with mock.patch.object(p.os,'lstat',side_effect=guarded),mock.patch.object(p.os,'geteuid',return_value=os.getuid()):
            result=tree.archive_sources(refs);tree.check()
        self.assertEqual(set(result),set(names));self.assertEqual(denied,[]);self.assertEqual(self.uid,0)
        for name,ref in result.items():self.assertEqual(Path(ref['path']).read_bytes(),name.encode())

    def test_remote_input_ancestor_drift_still_refuses_before_pair_commit(self):
        from unittest import mock
        projection,tree,_,_=self.control_tree();path=self.root/'L'/'remote-source.json'
        path.write_bytes(b'{"remote":true}');path.chmod(0o600)
        ref=dict(path=str(path),sha256=p.hashlib.sha256(path.read_bytes()).hexdigest(),signature9=p.nine(path.lstat()))
        tree.reserve_nfs_control(ref,public=True);original=p.os.stat;changed=[];pairs=tree.pairs
        def drift(value,*args,**kwargs):
            result=original(value,*args,**kwargs)
            if self.uid==1000 and str(value)==path.name and not changed:
                changed.append(True);path.parent.chmod(0o750)
            return result
        try:
            with mock.patch.object(p.os,'stat',side_effect=drift),mock.patch.object(p.os,'geteuid',return_value=os.getuid()),self.assertRaises((p.Held,projection.Held)):
                tree.project(ref)
            self.assertTrue(changed);self.assertEqual(tree.pairs,pairs);self.assertEqual(self.uid,0)
            self.assertEqual(path.read_bytes(),b'{"remote":true}')
        finally:path.parent.chmod(0o700)

    def test_stats_siblings_keep_one_initial_and_each_fresh_walk(self):
        from unittest import mock
        paths=tuple(str(self.root/'L'/str(i))for i in range(4))
        for path in paths:Path(path).write_bytes(b'original')
        original=p.os.open;roots=[];opened=[]
        def observed(path,*args,**kwargs):
            fd=original(path,*args,**kwargs)
            if self.uid==1000:opened.append(fd)
            if self.uid==1000 and path=='/':roots.append(fd)
            return fd
        with mock.patch.object(p.os,'open',side_effect=observed):values=self.actor._run('stats',paths)
        self.assertEqual([p.nine(v)for v in values],[p.nine(Path(path).lstat())for path in paths])
        self.assertEqual(len(roots),len(paths)+1);self.assertEqual(self.uid,0)
        for fd in set(opened):
            with self.assertRaises(OSError):os.fstat(fd)

    def test_stats_parent_change_and_next_call_open_new_chains(self):
        from unittest import mock
        paths=tuple(str(self.root/name/leaf)for name,leaf in (('L','a'),('L','b'),('R','c'),('L','d')))
        for path in paths:Path(path).write_bytes(b'original')
        original=p.os.open;roots=[]
        def observed(path,*args,**kwargs):
            fd=original(path,*args,**kwargs)
            if self.uid==1000 and path=='/':roots.append(fd)
            return fd
        with mock.patch.object(p.os,'open',side_effect=observed):
            values=self.actor._run('stats',paths);first=len(roots);self.actor._run('stats',paths[:2])
        self.assertEqual(first,7);self.assertEqual(len(roots)-first,3)
        self.assertEqual([p.nine(v)for v in values],[p.nine(Path(path).lstat())for path in paths]);self.assertEqual(self.uid,0)

    def test_stats_sibling_parent_replacement_refuses_before_next_sample(self):
        from unittest import mock
        folder=self.root/'L'/'siblings';folder.mkdir(mode=0o700)
        paths=tuple(str(folder/name)for name in ('first','second','third'))
        for path in paths:Path(path).write_bytes(b'original')
        original=p.os.stat;seen=[];saved=folder.with_name('saved')
        def changed(name,*args,**kwargs):
            value=original(name,*args,**kwargs)
            if name in ('first','second','third'):seen.append(name)
            if name=='second':folder.rename(saved);folder.mkdir(mode=0o700)
            return value
        try:
            with mock.patch.object(p.os,'stat',side_effect=changed),self.assertRaises(p.Held):self.actor._run('stats',paths)
            self.assertEqual(seen,['first','second']);self.assertEqual(self.uid,0)
        finally:
            if saved.exists():folder.rmdir();saved.rename(folder)

    def test_stats_sibling_symlink_substitution_refuses(self):
        from unittest import mock
        folder=self.root/'L'/'siblings';folder.mkdir(mode=0o700)
        for name in ('first','second'):(folder/name).write_bytes(b'original')
        original=p.os.stat;saved=folder.with_name('saved')
        def changed(name,*args,**kwargs):
            value=original(name,*args,**kwargs)
            if name=='second':folder.rename(saved);folder.symlink_to(saved,target_is_directory=True)
            return value
        try:
            with mock.patch.object(p.os,'stat',side_effect=changed),self.assertRaises(OSError):self.actor._run('stats',tuple(str(folder/name)for name in ('first','second')))
            self.assertEqual(self.uid,0)
        finally:
            if saved.exists():folder.unlink();saved.rename(folder)

    def test_stats_missing_leaf_keeps_primary_through_close_failure(self):
        from unittest import mock
        path=self.root/'L'/'present';path.write_bytes(b'original')
        original_open=p.os.open;original_close=p.os.close;opened=[];failed=[]
        def opened_fd(*args,**kwargs):
            fd=original_open(*args,**kwargs)
            if self.uid==1000:opened.append(fd)
            return fd
        def close(fd):
            original_close(fd)
            if self.uid==1000 and opened and fd==opened[0] and not failed:failed.append(fd);raise RuntimeError('synthetic close after dispatch')
        with mock.patch.object(p.os,'open',side_effect=opened_fd),mock.patch.object(p.os,'close',side_effect=close),self.assertRaises(FileNotFoundError):
            self.actor._run('stats',(str(path),str(path.with_name('missing'))))
        self.assertTrue(failed);self.assertEqual(self.uid,0)
        for fd in set(opened):
            with self.assertRaises(OSError):os.fstat(fd)

    def test_stats_root_and_single_stat_keep_original_samples(self):
        paths=('/',str(Path(str(self.root)).parents[-2]))
        values=self.actor._run('stats',paths,ancestor=True)
        self.assertEqual([p.five(v)for v in values],[p.five(Path(path).lstat())for path in paths])
        self.assertEqual(p.five(self.actor._run('stat',str(self.root))),p.five(self.root.lstat()));self.assertEqual(self.uid,0)

    def test_stats_parent_change_close_failure_never_opens_next_chain(self):
        from unittest import mock
        paths=(str(self.root/'L'/'left'),str(self.root/'R'/'right'))
        for path in paths:Path(path).write_bytes(b'original')
        original_open=p.os.open;original_close=p.os.close;original_stat=p.os.stat
        chain=[];opened=[];sampled=[];failed=[];roots=[]
        def opened_fd(path,*args,**kwargs):
            fd=original_open(path,*args,**kwargs)
            if self.uid==1000:
                opened.append(fd)
                if path=='L' and not chain:chain.append(fd)
                if path=='/':roots.append(fd)
            return fd
        def close(fd):
            original_close(fd)
            if self.uid==1000 and chain and fd==chain[0] and not failed:
                failed.append(fd);raise RuntimeError('synthetic parent-change close')
        def sample(name,*args,**kwargs):
            if name in ('left','right'):sampled.append(name)
            return original_stat(name,*args,**kwargs)
        with mock.patch.object(p.os,'open',side_effect=opened_fd),mock.patch.object(p.os,'close',side_effect=close),mock.patch.object(p.os,'stat',side_effect=sample),self.assertRaisesRegex(RuntimeError,'synthetic parent-change close'):
            self.actor._run('stats',paths)
        self.assertEqual(sampled,['left']);self.assertEqual(len(roots),2);self.assertEqual(self.uid,0)
        for fd in set(opened):
            with self.assertRaises(OSError):os.fstat(fd)

    def control_tree(self):
        import hashlib
        from unittest import mock
        import comic_child_control_projection as projection
        exec('def _tree_control_read(ref, private=True):\n return read(ref, private=False)\n',p.__dict__)
        local=self.root.parent/'local-control.json';local.write_bytes(b'{"original":true}');local.chmod(0o600)
        ref=dict(path=str(local),sha256=hashlib.sha256(local.read_bytes()).hexdigest(),signature9=p.nine(local.lstat()))
        operation=self.root.parent/'operation';operation.mkdir(mode=0o700)
        # The credential double retains real UID1000 file births; do not forge
        # ownership metadata or claim this is actual Root/NFS execution.
        with mock.patch.object(p.os,'geteuid',return_value=os.getuid()):
            tree=projection.Tree(self.root.parent/'child','/_operation',operation,p._tree_control_read,
                                 uid=os.getuid(),gid=os.getgid(),owner_reads=self.actor)
            tree.scope(str(self.root/'R'),'retention_root');tree.project(ref)
        return projection,tree,local,ref

    def test_control_vector_mixed_paths_and_fresh_invocations(self):
        local=self.root.parent/'local';local.write_bytes(b'original')
        remote=self.root/'L'/'remote';remote.write_bytes(b'original')
        files=tuple((str(path),tuple(p.nine(path.lstat())))for path in (local,remote))
        nodes=((str(self.root/'R'),tuple(p.five((self.root/'R').lstat()))),)
        self.actor.control_vector(files+files,nodes+nodes);self.assertEqual(self.uid,0)
        remote.write_bytes(b'changed')
        with self.assertRaises(p.Held):self.actor.control_vector(files,nodes)

    def test_final_batches_remote_files_without_per_file_owner_checks(self):
        files = {}
        for index in range(64):
            path = self.root/'L'/str(index);path.write_bytes(b'original')
            files[str(path)] = tuple(p.nine(path.lstat()))
        before = len(self.events)
        p.final(files, {}, ())
        self.assertLess(len(self.events)-before, 100)
        self.assertEqual(self.uid, 0)

    def test_final_batch_remains_fresh_on_every_call(self):
        path=self.root/'L'/'original';path.write_bytes(b'original')
        files={str(path):tuple(p.nine(path.lstat()))}
        p.final(files, {}, ());path.write_bytes(b'changed')
        with self.assertRaises(p.Held):p.final(files, {}, ())

    def test_final_local_files_keep_scalar_full9(self):
        path=self.root.parent/'local';path.write_bytes(b'original')
        files={str(path):tuple(p.nine(path.lstat()))};path.write_bytes(b'changed')
        with self.assertRaisesRegex(p.Held,'file-final'):p.final(files, {}, ())

    def test_final_directory9_is_not_reduced_to_directory5(self):
        path=self.root/'L';files={str(path):tuple(p.nine(path.lstat()))}
        before=path.stat();os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1))
        with self.assertRaisesRegex(p.Held,'file-final'):p.final(files, {}, ())

    def test_final_batch_keeps_absence_checks(self):
        path=self.root/'L'/'absent';p.final({}, {}, (str(path),));path.write_bytes(b'foreign')
        with self.assertRaisesRegex(p.Held,'absence-final'):p.final({}, {}, (str(path),))

    def test_remote_vector_over_bound_keeps_scalar_fallback(self):
        path=self.root/'L'/'sample';path.write_bytes(b'original');fact=tuple(p.nine(path.lstat()))
        rows=tuple((str(self.root/'L'/str(i)),fact)for i in range(513))
        self.assertEqual(p.remote_control_vector(rows,()),(frozenset(),frozenset()))

    def test_final_rejects_substituted_batch_helper_before_dispatch(self):
        from unittest import mock
        path=self.root/'L'/'sample';path.write_bytes(b'original');files={str(path):tuple(p.nine(path.lstat()))}
        with mock.patch.object(p,'remote_control_vector',side_effect=AssertionError('must not dispatch')):
            with self.assertRaises(p.Held):p.final(files,{},())

    def test_remote_vector_rejects_substituted_contains_before_dispatch(self):
        from unittest import mock
        path=self.root/'L'/'sample';path.write_bytes(b'original');rows=((str(path),tuple(p.nine(path.lstat()))),)
        with mock.patch.object(type(self.actor),'contains',side_effect=AssertionError('must not dispatch')):
            with self.assertRaises(p.Held):p.remote_control_vector(rows,())

    def test_final_rejects_late_caller_fact_change(self):
        from unittest import mock
        remote=self.root/'L'/'remote';remote.write_bytes(b'original')
        local=self.root.parent/'local';local.write_bytes(b'local')
        files={str(remote):tuple(p.nine(remote.lstat())),str(local):tuple(p.nine(local.lstat()))}
        real=p.os.lstat;changed=[]
        def sample(path,*args,**kwargs):
            result=real(path,*args,**kwargs)
            if str(path)==str(local) and not changed:
                value=files[str(remote)];files[str(remote)]=(*value[:2],value[2]+1,*value[3:]);changed.append(True)
            return result
        with mock.patch.object(p.os,'lstat',side_effect=sample),self.assertRaisesRegex(p.Held,'final-original-primitive-vectors'):
            p.final(files,{},())
        self.assertTrue(changed)

    def test_final_recloses_remote_file_after_local_callback(self):
        from unittest import mock
        remote=self.root/'L'/'remote';remote.write_bytes(b'original')
        local=self.root.parent/'local';local.write_bytes(b'local')
        files={str(remote):tuple(p.nine(remote.lstat())),str(local):tuple(p.nine(local.lstat()))}
        real=p.os.lstat;changed=[]
        def sample(path,*args,**kwargs):
            result=real(path,*args,**kwargs)
            if str(path)==str(local) and not changed:remote.write_bytes(b'changed');changed.append(True)
            return result
        with mock.patch.object(p.os,'lstat',side_effect=sample),self.assertRaises(p.Held):p.final(files,{},())
        self.assertTrue(changed)

    def test_final_rejects_foreign_late_row_without_iteration(self):
        from unittest import mock
        path=self.root.parent/'local';path.write_bytes(b'local')
        files={str(path):tuple(p.nine(path.lstat()))};real=p.os.lstat;called=[]
        class Foreign:
            def __iter__(self):called.append(True);raise AssertionError('foreign row executed')
        def sample(value,*args,**kwargs):
            result=real(value,*args,**kwargs)
            if str(value)==str(path):files[str(path)]=Foreign()
            return result
        with mock.patch.object(p.os,'lstat',side_effect=sample),self.assertRaisesRegex(p.Held,'final-original-primitive-vectors'):
            p.final(files,{},())
        self.assertFalse(called)

    def test_control_vector_primitive_conflicts_refuse_before_io(self):
        from unittest import mock
        path=str(self.root/'L');node=tuple(p.five((self.root/'L').lstat()));changed=(*node[:1],node[1]+1,*node[2:])
        rows=[([],()),((),((Path(path),node),)),((),((path,(*node[:1],True,*node[2:])),)),
              ((),((path,node),(path,changed))), ((),(('relative',node),)),((),((path,node),)*513)]
        for files,nodes in rows:
            with self.subTest(files=type(files).__name__,rows=len(nodes)),mock.patch.object(p.os,'lstat')as io:
                with self.assertRaises(p.Held):self.actor.control_vector(files,nodes)
                io.assert_not_called()

    def test_control_vector_cross_width_conflict_and_combined_bound(self):
        from unittest import mock
        path=self.root.parent/'file';path.write_bytes(b'original');file=tuple(p.nine(path.lstat()))
        directory=tuple(p.five((self.root/'L').lstat()))
        for files,nodes in [(((str(path),file),),((str(path),directory),)),
                            ((),tuple((str(self.root/'L'/str(i)),directory)for i in range(513))),
                            (tuple((str(self.root.parent/('file-'+str(i))),file)for i in range(300)),
                             tuple((str(self.root/'L'/str(i)),directory)for i in range(300)))]:
            with mock.patch.object(p.os,'lstat')as io:
                with self.assertRaises(p.Held):self.actor.control_vector(files,nodes)
                io.assert_not_called()

    def test_stats_later_path_failure_closes_descriptors_and_restores_root(self):
        first=self.root/'L'/'first';first.write_bytes(b'original')
        before=set(os.listdir('/proc/self/fd'))
        with self.assertRaises(FileNotFoundError):self.actor._run('stats',(str(first),str(self.root/'R'/'missing')))
        self.assertEqual(self.uid,0);self.assertEqual(set(os.listdir('/proc/self/fd')),before)

    def test_stats_scope_and_symlink_escape_refuse(self):
        link=self.root/'L'/'link';link.symlink_to('/etc')
        for paths in [('/etc/passwd',),(str(link/'passwd'),),[str(self.root/'L')],(str(self.root/'L'),)*2]:
            with self.subTest(paths=paths),self.assertRaises((p.Held,OSError)):self.actor._run('stats',paths)
            self.assertEqual(self.uid,0)
        expected=((str(link),tuple(p.five((self.root/'L').lstat()))),)
        with self.assertRaises(p.Held):self.actor.control_vector((),expected)

    def test_stats_later_error_survives_failed_restoration_and_poison(self):
        from unittest import mock
        first=self.root/'L'/'first';first.write_bytes(b'original')
        def switch(real,effective,saved):
            if effective==0:raise RuntimeError('disposable restore refusal')
            self.uid=effective
        enabled=p.gc.isenabled();mask=p.signal.pthread_sigmask(p.signal.SIG_BLOCK,set())
        try:
            with mock.patch.object(p.os,'setresuid',side_effect=switch):
                with self.assertRaises(FileNotFoundError):self.actor._run('stats',(str(first),str(self.root/'R'/'missing')))
            self.assertTrue(self.actor.poisoned)
        finally:
            self.uid=0;p.signal.pthread_sigmask(p.signal.SIG_SETMASK,mask)
            if enabled:p.gc.enable()
        with self.assertRaises(p.Held):p.owner_root_guard()

    def test_stats_late_ancestor_replacement_refuses(self):
        from unittest import mock
        first=self.root/'L'/'first';second=self.root/'L'/'second'
        first.write_bytes(b'first');second.write_bytes(b'second');original=p.os.stat;changed=[False]
        def replace(name,*args,**kwargs):
            if name=='second'and self.uid==1000 and not changed[0]:
                changed[0]=True;(self.root/'L').rename(self.root/'old');(self.root/'L').mkdir(mode=0o700)
            return original(name,*args,**kwargs)
        try:
            with mock.patch.object(p.os,'stat',side_effect=replace),self.assertRaises((p.Held,OSError)):
                self.actor._run('stats',(str(first),str(second)))
            self.assertTrue(changed[0]);self.assertEqual(self.uid,0)
        finally:
            if changed[0]:(self.root/'L').rmdir();(self.root/'old').rename(self.root/'L')

    def test_vector_semantic_dependency_and_defaults_refuse_without_callback(self):
        from unittest import mock
        called=[]
        def fake(*args,**kwargs):called.append(True);return b'forged'
        with mock.patch.object(p,'read',fake),self.assertRaises(p.Held):self.actor.control_vector((),())
        self.assertFalse(called)
        keywords=p._read_original.__kwdefaults__;old=keywords['empty_stderr'];keywords['empty_stderr']=True
        try:
            with self.assertRaises(p.Held):self.actor.control_vector((),())
        finally:keywords['empty_stderr']=old
        keywords=type(self.actor)._run.__kwdefaults__;old=keywords['ancestor'];keywords['ancestor']=True
        try:
            with self.assertRaises(p.Held):self.actor.control_vector((),())
        finally:keywords['ancestor']=old

    def test_vector_original_seal_and_registry_cannot_be_replaced(self):
        original=p._OWNER_READ_SEALS[self.actor];p._OWNER_READ_SEALS[self.actor]=tuple(list(original))
        try:
            with self.assertRaises(p.Held):self.actor.control_vector((),())
        finally:p._OWNER_READ_SEALS[self.actor]=original
        bound=p._OWNER_READS;p._OWNER_READS=object()
        try:
            with self.assertRaises(p.Held):self.actor.control_vector((),())
        finally:p._OWNER_READS=bound

    def test_vector_replaced_trailing_source_callback_is_refused_before_running(self):
        from unittest import mock
        path=self.root.parent/'target';path.write_bytes(b'original');files=((str(path),tuple(p.nine(path.lstat()))),)
        called=[];original=p.os.lstat;patcher=mock.patch.object(p,'read',lambda *a,**k:called.append(True));changed=[False]
        def sample(value,*args,**kwargs):
            result=original(value,*args,**kwargs)
            if str(value)==str(path)and not changed[0]:changed[0]=True;patcher.start()
            return result
        try:
            with mock.patch.object(p.os,'lstat',side_effect=sample),self.assertRaises(p.Held):self.actor.control_vector(files,())
            self.assertTrue(changed[0]);self.assertFalse(called);self.assertEqual(path.read_bytes(),b'original')
        finally:patcher.stop()

    def test_vector_late_source_bytes_refuse_using_private_source_copy(self):
        from unittest import mock
        source=self.root.parent/'parent-copy.py';source.write_bytes(Path(p.__file__).read_bytes());source.chmod(0o600)
        with mock.patch.object(p,'__file__',str(source)):actor=p.GeometryOwnerReads(self.geometry)
        original_actor=p._OWNER_READS;p._OWNER_READS=actor
        path=self.root.parent/'target';path.write_bytes(b'original');files=((str(path),tuple(p.nine(path.lstat()))),)
        original=p.os.lstat;changed=[False]
        def sample(value,*args,**kwargs):
            result=original(value,*args,**kwargs)
            if str(value)==str(path)and not changed[0]:changed[0]=True;source.write_bytes(b'changed private source')
            return result
        try:
            with mock.patch.object(p.os,'lstat',side_effect=sample),self.assertRaises(p.Held):actor.control_vector(files,())
            self.assertTrue(changed[0]);self.assertEqual(self.uid,0)
        finally:actor.release();p._OWNER_READS=original_actor

    def test_tree_vector_independent_passes_and_no_cross_call_cache(self):
        from unittest import mock
        _,tree,local,_=self.control_tree();original=p.os.lstat;calls=[]
        def sample(path,*args,**kwargs):
            if str(path)==str(local):calls.append(True)
            return original(path,*args,**kwargs)
        with mock.patch.object(p.os,'lstat',side_effect=sample):tree.check();tree.check()
        self.assertEqual(len(calls),4)
        local.write_bytes(b'changed')
        with self.assertRaises(p.Held):tree.check()

    def test_tree_replaced_first_close_cannot_bypass_late_fact_mutation(self):
        from unittest import mock
        projection,tree,local,_=self.control_tree();original=projection.os.listdir;changed=[False]
        def names(path):
            result=original(path)
            if str(path)==str(tree.root)and not changed[0]:changed[0]=True;local.write_bytes(b'changed')
            return result
        with mock.patch.object(projection,'close',return_value=None),mock.patch.object(projection.os,'listdir',side_effect=names):
            with self.assertRaises(p.Held):tree.check()
        self.assertTrue(changed[0])

    def test_tree_final_vector_rejects_method_and_code_replacement(self):
        from unittest import mock
        projection,tree,_,_=self.control_tree();original=projection.os.listdir
        for member in ('control_vector','_run','check','assert_root'):
            called=[];patcher=mock.patch.object(type(self.actor),member,lambda *a,**k:called.append(True));changed=[False]
            def names(path):
                result=original(path)
                if str(path)==str(tree.root)and not changed[0]:changed[0]=True;patcher.start()
                return result
            try:
                with mock.patch.object(projection.os,'listdir',side_effect=names),self.assertRaises(projection.Held):tree.check()
                self.assertFalse(called)
            finally:patcher.stop()
        function=type(self.actor).control_vector;code=function.__code__;changed=[False]
        def forged(*args,**kwargs):return None
        def names(path):
            result=original(path)
            if str(path)==str(tree.root)and not changed[0]:changed[0]=True;function.__code__=forged.__code__
            return result
        try:
            with mock.patch.object(projection.os,'listdir',side_effect=names),self.assertRaises(projection.Held):tree.check()
        finally:function.__code__=code

    def test_tree_final_vector_rejects_foreign_actor_seal_and_logical_mutation(self):
        from unittest import mock
        projection,tree,_,_=self.control_tree();original=projection.os.listdir;actor=self.actor;seal=p._OWNER_READ_SEALS[actor]
        for field in ('actor','none','seal','logical','dependency'):
            changed=[False];pairs=tree.pairs
            original_read=p.read
            def names(path):
                result=original(path)
                if str(path)==str(tree.root)and not changed[0]:
                    changed[0]=True
                    if field=='actor':tree.owner_reads=object.__new__(type(actor))
                    elif field=='none':tree.owner_reads=None
                    elif field=='seal':p._OWNER_READ_SEALS[actor]=tuple(list(seal))
                    elif field=='dependency':p.read=lambda *args,**kwargs:self.fail('replaced source callback must not run')
                    else:tree.pairs=()
                return result
            try:
                with mock.patch.object(projection.os,'listdir',side_effect=names),self.assertRaises((p.Held,projection.Held)):tree.check()
            finally:tree.owner_reads=actor;p._OWNER_READ_SEALS[actor]=seal;tree.pairs=pairs;p.read=original_read

    def test_geometry_batch_preserves_distinct_fd_checks(self):
        from unittest import mock
        fd=os.dup(next(iter(self.actor.handles)));self.actor.handles[fd]=next(iter(self.actor.handles.values()))
        original=os.fstat;seen=[];self.events.clear()
        def sample(handle):
            seen.append((handle,self.uid));return original(handle)
        with mock.patch.object(p.os,'fstat',side_effect=sample):self.actor.check()
        self.assertEqual(self.events,[1000,0]*3)
        for handle in self.actor.handles:self.assertEqual(seen.count((handle,0)),2)

    def test_geometry_conflicting_path_refuses_before_io(self):
        from unittest import mock
        fd=next(iter(self.actor.handles));original=self.actor.handles[fd];path,fact=original
        self.actor.handles[fd]=(path,(fact[0],fact[1]+1,*fact[2:]))
        try:
            with mock.patch.object(p.os,'fstat') as sample,mock.patch.object(p.os,'lstat') as path_sample:
                with self.assertRaises(p.Held):self.actor.check()
                sample.assert_not_called();path_sample.assert_not_called()
        finally:self.actor.handles[fd]=original

    def test_geometry_final_fd_pass_rejects_reuse(self):
        from unittest import mock
        target=next(iter(self.actor.handles));saved=os.dup(target)
        foreign=self.root.parent/'foreign';foreign.write_bytes(b'foreign')
        source=os.open(foreign,os.O_RDONLY|os.O_NOFOLLOW);original=p.os.stat;changed=[]
        def sample(path,*args,**kwargs):
            result=original(path,*args,**kwargs)
            if self.uid==1000 and path==Path(tuple(self.actor.nodes)[-2]).name and not changed:changed.append(True);os.dup2(source,target)
            return result
        try:
            with mock.patch.object(p.os,'stat',side_effect=sample),self.assertRaises(p.Held):self.actor.check()
            self.assertTrue(changed);self.assertEqual(os.pread(target,32,0),b'foreign')
        finally:os.dup2(saved,target);os.close(saved);os.close(source)

    def test_geometry_final_ledger_primitives_refuse_without_callbacks(self):
        from unittest import mock
        actor=self.actor;handles=actor.handles;nodes=actor.nodes;original=p.os.stat;calls=[]
        class Foreign:
            def __iter__(self):calls.append('iterate');return iter(next(iter(nodes.values())))
            def __eq__(self,other):calls.append('equal');return True
        for change in ('handle-object','node-iterable','handles-copy','nodes-copy'):
            saved_handles=dict(handles);saved_nodes=dict(nodes);changed=[]
            def sample(path,*args,**kwargs):
                result=original(path,*args,**kwargs)
                if self.uid==1000 and path==Path(tuple(self.actor.nodes)[-2]).name and not changed:
                    changed.append(True)
                    if change=='handle-object':handles[next(iter(handles))]=Foreign()
                    elif change=='node-iterable':nodes[next(iter(nodes))]=Foreign()
                    elif change=='handles-copy':actor.handles=dict(handles)
                    else:actor.nodes=dict(nodes)
                return result
            try:
                with self.subTest(change=change),mock.patch.object(p.os,'stat',side_effect=sample),self.assertRaises(p.Held):actor.check()
                self.assertTrue(changed);self.assertEqual(calls,[])
            finally:
                actor.handles=handles;actor.nodes=nodes;handles.clear();handles.update(saved_handles);nodes.clear();nodes.update(saved_nodes)

    def test_geometry_ancestor_batch_has_exact_scope(self):
        from unittest import mock
        paths=tuple(self.actor.nodes);values=self.actor._run('stats',paths,ancestor=True)
        self.assertEqual([p.five(value) for value in values],list(self.actor.nodes.values()))
        for requested,flag in ((paths,False),((str(self.root.parent/'foreign'),),True),(paths,1)):
            with self.subTest(flag=flag),mock.patch.object(p.os,'setresuid') as switch:
                with self.assertRaises(p.Held):self.actor._run('stats',requested,ancestor=flag)
                switch.assert_not_called()
        original=p.os.lstat;sampled=[]
        def local(path,*args,**kwargs):
            if path==paths[0]:sampled.append(self.uid)
            return original(path,*args,**kwargs)
        with mock.patch.object(p.os,'lstat',side_effect=local):self.actor.control_vector((),((paths[0],tuple(self.actor.nodes[paths[0]])),))
        self.assertEqual(sampled,[0])

    def test_geometry_later_ancestor_error_closes_fds_and_restores_root(self):
        from unittest import mock
        original=p.os.stat;before=set(os.listdir('/proc/self/fd'));error=OSError('later-ancestor');fired=[]
        def sample(path,*args,**kwargs):
            if self.uid==1000 and path==Path(tuple(self.actor.nodes)[-2]).name:fired.append(True);raise error
            return original(path,*args,**kwargs)
        with mock.patch.object(p.os,'stat',side_effect=sample),self.assertRaises(OSError) as held:self.actor.check()
        self.assertIs(held.exception,error);self.assertEqual(self.uid,0);self.assertEqual(fired,[True])
        self.assertEqual(set(os.listdir('/proc/self/fd')),before)

if __name__ == '__main__':
    unittest.main()

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

    def test_original_archive_bytes_hash_and_namespace_after_explicit_owner_read(self):
        import hashlib
        path = self.root/'L'/'target.cbz'; path.write_bytes(b'original-disposable')
        ref = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), signature9=p.nine(path.lstat()))
        self.assertEqual(p.read(ref, private=False), b'original-disposable')
        self.assertEqual(p.nfs_names(self.root/'L'), ('target.cbz',))
        self.assertEqual(self.uid, 0)
        self.assertEqual(self.events[-1], 0)

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

if __name__ == '__main__':
    unittest.main()

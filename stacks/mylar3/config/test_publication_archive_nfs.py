"""Rename/link algorithm controls on real local files/SQL, NOT NFS/Birth proof.

The existing catalog/reader component fixture substitutes installed origins and
StoppedReaderCustody. Only NFS transport/factory admission is substituted here;
all archive bytes, descriptor/link operations, SQLite and phase receipts are real.
The mandatory installed NFS/Parent/Birth scenario remains a separate gate.
"""
from contextlib import closing
import copy
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
import test_publication_archive_adoption as fixture

a = fixture.a
ORIGINAL_NFS_GEOMETRY = a.nfs_child_geometry


class Tests(unittest.TestCase):
    def setUp(self):
        self.case = fixture.Tests('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        case = self.case
        self.common = case.base / 'nfs-geometry-component'
        self.common.mkdir(mode=0o700)
        case.c.library.rename(self.common / 'library')
        case.retention.rename(self.common / 'retention')
        case.c.library = self.common / 'library'
        case.c.library.chmod(0o700)
        case.c.source = case.c.library / 'Series.001.cbz'
        case.c.controller.roots = [case.c.library]
        case.retention = self.common / 'retention'
        case.life.source = case.c.source
        case.c.sql('UPDATE comics SET ComicLocation=?', (str(case.c.library),))
        with closing(sqlite3.connect(case.cfg / 'database.sqlite')) as db:
            db.execute('UPDATE BOOK SET URL=?', (case.c.source.as_uri(),))
            db.commit()
        (case.restore / 'database.sqlite').write_bytes((case.cfg / 'database.sqlite').read_bytes())
        self.reader_before = {name: (case.cfg / name).read_bytes() for name in ('database.sqlite', 'tasks.sqlite')}
        self.source_before = case.c.source.read_bytes()
        self.geometry = dict(version=1, kind='private-common-root-nfs',
                             **{role: dict(path=str(path), signature9=a.o.signature(path)) for role, path in
                                (('common_root', self.common), ('library', case.c.library), ('retention', case.retention))})
        self.facts = dict(protocol='rename-link-v1', mount=dict(fstype='nfs4'), geometry=self.geometry,
                          owner=case.c.owner, operation_id=case.c.operation_id)
        # Explicit component-only admission seam; no installed factory claim.
        gate = patch.object(a, 'nfs_child_geometry', side_effect=self.component_geometry)
        gate.start()
        self.addCleanup(gate.stop)

    def component_geometry(self, facts, source, retention):
        self.assertEqual(a.o.signature(self.common), self.geometry['common_root']['signature9'])
        self.assertEqual(set(os.listdir(self.common)), {'library', 'retention'})
        self.assertEqual(Path(retention), self.case.retention)
        self.assertTrue(Path(source).is_relative_to(self.case.c.library))
        return dict(component_only=True)

    def cap(self):
        case = self.case
        case.prep = case.c.prepare()
        case.reader = case.lease()
        selected = a.NFSRepairPublication(a._KEY, case.life, object(), self.facts)
        with patch.object(a.NFSRepairPublication, 'consume', return_value=copy.deepcopy(self.facts)):
            return a.prepare_existing(case.prep, case.reader, case.retention, publication=selected)

    def assert_preserved(self, cap, *, rollback=False):
        case = self.case
        for name, raw in self.reader_before.items():
            self.assertEqual((case.cfg / name).read_bytes(), raw)
        with closing(sqlite3.connect(case.c.controller.native_database)) as db:
            self.assertEqual(a.snapshot(db, case.prep._deadline), cap._before if rollback else cap._after)
        self.assertEqual((case.prep._operation / 'original.arc').read_bytes(), self.source_before)
        self.assertEqual((case.prep._operation / 'restored-original.arc').read_bytes(), self.source_before)
        self.assertFalse((cap.root / 'install-displaced.arc').exists())
        self.assertFalse((cap.root / 'reverse-displaced.arc').exists())
        self.assertEqual(case.c.source.stat().st_nlink, 1)
        self.assertEqual(cap.stage.stat().st_nlink, 1)

    def test_real_forward_and_explicit_reverse_preserve_full_sql_reader_and_originals(self):
        cap = self.cap()
        before_inode = self.case.c.source.stat().st_ino
        cap.install()
        self.assert_preserved(cap)
        self.assertEqual(set(p.name for p in cap.journal.iterdir()),
                         {'baseline.json', 'install-intent.json', 'installed.json'} | a.nfs_receipt_names())
        self.assertNotEqual(self.case.c.source.read_bytes(), self.source_before)
        self.assertEqual(cap.stage.stat().st_ino, before_inode)
        cap.reverse()
        self.assertEqual(self.case.c.source.read_bytes(), self.source_before)
        self.assertEqual(self.case.c.source.stat().st_ino, before_inode)
        self.assert_preserved(cap, rollback=True)
        cap.complete_reversed()
        cap.close()

    def test_forward_completion_closes_exported_protocol_and_candidate_absences(self):
        cap = self.cap()
        cap.install()
        cap.complete()
        cap.close()
        self.assert_preserved(cap)
        self.assertIn(cap.root / 'install-displaced.arc', cap._absent)
        self.assertIn(cap.root / 'reverse-displaced.arc', cap._absent)
        self.assertIn(self.common, cap._dirs)
        self.assertEqual(cap._publication, self.facts)

    def test_displaced_collision_never_overwritten(self):
        cap = self.cap()
        target = cap.root / 'install-displaced.arc'
        original_link = a.os.link
        fired = []
        def collision(source, destination, **kwargs):
            if destination == target.name and not fired:
                fired.append(True)
                target.write_bytes(b'foreign')
            return original_link(source, destination, **kwargs)
        with patch.object(a.os, 'link', side_effect=collision), self.assertRaises(a.o.Held):
            cap.install()
        self.assertEqual(target.read_bytes(), b'foreign')
        self.assertEqual(self.case.c.source.read_bytes(), self.source_before)
        self.assertEqual(cap._phase, 'uncertain')
        self.assertTrue((cap.preparation._writer.root / a.PENDING).exists())
        with self.assertRaises(a.o.Held):
            cap.install()

    def test_unbound_dictionary_cannot_select_protocol(self):
        case = self.case
        prep = case.c.prepare()
        reader = case.lease()
        with self.assertRaisesRegex(a.o.Held, 'repair-exact-publication-selection'):
            a.prepare_existing(prep, reader, case.retention, publication=self.facts)

    def fault_case(self, reverse, fault):
        child = Tests('runTest')
        child.setUp()
        try:
            cap = child.cap()
            if reverse:
                cap.install()
            database = child.case.c.controller.native_database
            with closing(sqlite3.connect(database)) as db:
                native_before = a.snapshot(db, child.case.prep._deadline)
            with fault(cap), self.assertRaises(a.o.Held):
                (cap.reverse if reverse else cap.install)()
            self.assertEqual(cap._phase, 'uncertain')
            self.assertTrue((cap.preparation._writer.root / a.PENDING).exists())
            for name, raw in child.reader_before.items():
                self.assertEqual((child.case.cfg / name).read_bytes(), raw)
            with closing(sqlite3.connect(database)) as db:
                self.assertEqual(a.snapshot(db, child.case.prep._deadline), native_before)
            self.assertEqual((child.case.prep._operation / 'original.arc').read_bytes(), child.source_before)
            self.assertEqual((child.case.prep._operation / 'restored-original.arc').read_bytes(), child.source_before)
            paths = (cap.source, cap.stage, cap.root / 'install-displaced.arc', cap.root / 'reverse-displaced.arc')
            state = {str(p): (p.read_bytes(), a.o.signature(p)) if p.exists() else None for p in paths}
            observed = cap.uncertain_status()
            self.assertEqual(observed['outcome'], 'held-nfs-transition-uncertain')
            self.assertFalse(observed['automatic_replay'])
            self.assertFalse(observed['reader_resume_authority'])
            self.assertEqual({str(p): (p.read_bytes(), a.o.signature(p)) if p.exists() else None for p in paths}, state)
        finally:
            child.doCleanups()

    def test_every_durable_receipt_boundary_forward_and_reverse_holds_without_replay(self):
        original = a.RepairAdoption._record
        for reverse in (False, True):
            for target in sorted(a.nfs_receipt_names(reverse)):
                def fail(cap, name, value, target=target):
                    result = original(cap, name, value)
                    if name == target:
                        raise OSError('lost durable receipt response')
                    return result
                with self.subTest(reverse=reverse, boundary=target):
                    self.fault_case(reverse, lambda cap: patch.object(a.RepairAdoption, '_record', fail))

    def test_every_syscall_lost_response_forward_and_reverse_retains_custody(self):
        from contextlib import ExitStack, contextmanager
        for reverse in (False, True):
            for boundary in range(1, len(a.NFS_STEPS) + 1):
                @contextmanager
                def fault(cap, target=boundary):
                    count = [0]
                    identities = {(p.stat().st_dev,p.stat().st_ino) for p in (cap.root,cap.source.parent)}
                    link, unlink = a.os.link, a.os.unlink
                    def after(fn):
                        def call(*args, **kwargs):
                            descriptor=kwargs.get('src_dir_fd',kwargs.get('dir_fd'))
                            relevant=descriptor is not None and (lambda z:(z.st_dev,z.st_ino))(os.fstat(descriptor)) in identities
                            result = fn(*args, **kwargs)
                            if relevant:count[0] += 1
                            if relevant and count[0] == target:
                                raise OSError('lost syscall response')
                            return result
                        return call
                    with ExitStack() as stack:
                        stack.enter_context(patch.object(a.os, 'link', side_effect=after(link)))
                        stack.enter_context(patch.object(a.os, 'unlink', side_effect=after(unlink)))
                        yield
                with self.subTest(reverse=reverse, boundary=boundary):
                    self.fault_case(reverse, fault)

    def test_every_affected_directory_fsync_failure_holds(self):
        from contextlib import contextmanager
        for reverse in (False, True):
            for boundary in range(1, 2 * len(a.NFS_STEPS) + 1):
                @contextmanager
                def fault(cap, target=boundary):
                    count = [0]
                    identities = {(p.stat().st_dev, p.stat().st_ino) for p in (cap.source.parent, cap.root)}
                    original = a.os.fsync
                    def fsync(fd):
                        z = os.fstat(fd)
                        if (z.st_dev, z.st_ino) in identities:
                            count[0] += 1
                            if count[0] == target:
                                raise OSError('lost directory fsync')
                        return original(fd)
                    with patch.object(a.os, 'fsync', side_effect=fsync):
                        yield
                with self.subTest(reverse=reverse, boundary=boundary):
                    self.fault_case(reverse, fault)

    def test_post_filesystem_sql_failure_retains_both_revisions_and_native_preimage(self):
        cap = self.cap()
        original = a._set_size
        def fail(*args):
            original(*args)
            raise OSError('SQL response lost before commit')
        with patch.object(a, '_set_size', side_effect=fail), self.assertRaises(a.o.Held):
            cap.install()
        self.assertEqual(cap._phase, 'uncertain')
        self.assertNotEqual(cap.source.read_bytes(), self.source_before)
        self.assertEqual(cap.stage.read_bytes(), self.source_before)
        with closing(sqlite3.connect(self.case.c.controller.native_database)) as db:
            self.assertEqual(a.snapshot(db, cap.preparation._deadline), cap._before)
        for name, raw in self.reader_before.items():
            self.assertEqual((self.case.cfg / name).read_bytes(), raw)

    def verify_terminal(self, cap, rollback=False):
        verifier = fixture.load('publication_archive_verifier')
        baseline = cap.journal / 'baseline.json'
        real = self.case.life.vectors
        def bound():
            files,nodes,absent=real()
            files[baseline]=a.o.signature(baseline)
            return files,nodes,absent
        with patch.object(verifier,'installed'),patch.object(self.case.life,'vectors',side_effect=bound):
            return (verifier.verify_rollback_existing_with_vectors if rollback else verifier.verify_existing_with_vectors)(
                self.case.c.controller,self.case.c.writer,self.case.life,baseline,self.case.scratch)

    def test_independent_version2_terminal_verifier_closes_protocol_journal_and_common_root(self):
        cap=self.cap();cap.install();cap.complete()
        result=self.verify_terminal(cap)
        self.assertTrue(result['summary']['native_only_size_cell_transition'])
        self.assertIn(str(self.common),result['original_vectors']['files9'])
        self.assertEqual(set(cap.journal.iterdir()),{Path(path) for path in result['original_vectors']['files9'] if Path(path).parent==cap.journal})

    def test_independent_version2_rollback_verifier_proves_original_sql_and_pages(self):
        cap=self.cap();cap.install();cap.reverse();cap.complete_reversed()
        result=self.verify_terminal(cap,rollback=True)
        self.assertTrue(result['summary']['native_preimage_restored'])
        self.assertTrue(result['summary']['rollback_verified'])

    def test_independent_phase_receipt_link_count_tamper_refuses(self):
        import json
        cap=self.cap();cap.install();cap.complete()
        path=cap.journal/'install-nfs-01-retain-displaced-done.json'
        value=json.loads(path.read_bytes())
        value['locations'][str(cap.source)][8]=999
        path.write_bytes(a.o.compact(value))
        with self.assertRaisesRegex(a.o.Held,'verifier-nfs-exact-phase-inode-and-links'):
            self.verify_terminal(cap)

    def test_foreign_source_observed_after_callback_is_retained_before_unlink(self):
        cap=self.cap();original=a.direct;fired=[]
        def late(*args):
            original(*args)
            if not fired and cap.source.exists() and cap.source.stat().st_nlink==2 and (cap.root/'install-displaced.arc').exists():
                replacement=cap.source.parent/'foreign-temporary'
                replacement.write_bytes(b'foreign source')
                os.replace(replacement,cap.source)
                fired.append(True)
        with patch.object(a,'direct',side_effect=late),self.assertRaises(a.o.Held):cap.install()
        self.assertTrue(fired)
        self.assertEqual(cap.source.read_bytes(),b'foreign source')
        self.assertEqual((cap.root/'install-displaced.arc').read_bytes(),self.source_before)
        self.assertEqual(cap._phase,'uncertain')

    def mount_fixture(self, *, shadow=False, readonly=False, source='fixture:/export', nested=False):
        import io
        z=self.case.c.source.stat();device=str(os.major(z.st_dev))+':'+str(os.minor(z.st_dev))
        facts=copy.deepcopy(self.facts)
        facts.update(library=str(self.case.c.library),device=z.st_dev,
                     mount={'source':'fixture:/export','target':str(self.common.parent),'fstype':'nfs4','fsroot':'/export','options':'rw','maj:min':device})
        options='ro' if readonly else 'rw'
        rows=[f'101 1 {device} /export/{self.common.name} {self.common} {options} - nfs4 {source} rw']
        if shadow:rows.append(f'102 101 {device} /export/{self.common.name}/retention {self.case.retention} rw - nfs4 {source} rw')
        if nested:rows.append(f'103 101 {device} /elsewhere {self.case.c.library}/shadow ro - nfs4 {source} ro')
        real=open
        def opened(path,*args,**kwargs):
            if str(path)=='/proc/self/mountinfo':return io.StringIO('\n'.join(rows)+'\n')
            return real(path,*args,**kwargs)
        return facts,patch('builtins.open',side_effect=opened)

    def test_mountinfo_exact_original_export_and_same_mount_id_join(self):
        facts,transport=self.mount_fixture()
        with transport:result=ORIGINAL_NFS_GEOMETRY(facts,self.case.c.source,self.case.retention)
        self.assertEqual(result['id'],101)
        # This tests parsing/joining captured rows only; not actual NFS support.

    def searchable_geometry(self):
        common=self.common.with_name('archive-publication-'+'a'*64)
        self.common.rename(common);self.common=common
        (common/'library').rename(common/'L');(common/'retention').rename(common/'R')
        self.case.c.library=common/'L';self.case.c.source=common/'L'/'Series.001.cbz';self.case.retention=common/'R'
        common.chmod(0o711)
        self.geometry=dict(version=2,kind='searchable-common-root-nfs',**{role:dict(path=str(path),signature9=a.o.signature(path))for role,path in(('common_root',common),('library',self.case.c.library),('retention',self.case.retention))})
        self.facts['geometry']=self.geometry

    def test_searchable_disposable_geometry_uses_original_mount_join(self):
        self.searchable_geometry();facts,transport=self.mount_fixture()
        with transport:result=ORIGINAL_NFS_GEOMETRY(facts,self.case.c.source,self.case.retention)
        self.assertEqual(result['id'],101)
        self.assertFalse((self.case.c.writer.root/a.PENDING).exists())

    def test_searchable_geometry_modes_nonce_and_originals_refuse(self):
        self.searchable_geometry()
        for fault in ('root700','root755','leaf711','owner','foreignnonce','legacy711','rootdrift','shadow'):
            with self.subTest(fault=fault):
                for role,path in(('common_root',self.common),('library',self.case.c.library),('retention',self.case.retention)):self.geometry[role]['signature9']=a.o.signature(path)
                facts,transport=self.mount_fixture(shadow=fault=='shadow');g=facts['geometry']
                if fault in ('root700','root755'):
                    self.common.chmod(0o700 if fault=='root700'else 0o755);g['common_root']['signature9']=a.o.signature(self.common)
                elif fault=='leaf711':
                    self.case.c.library.chmod(0o711);g['library']['signature9']=a.o.signature(self.case.c.library)
                elif fault=='owner':g['common_root']['signature9'][6]=1001
                elif fault=='foreignnonce':g['common_root']['path']=str(self.common.with_name('archive-publication-unknown'))
                elif fault=='legacy711':g.update(version=1,kind='private-common-root-nfs')
                elif fault=='rootdrift':g['common_root']['signature9'][3]+=1
                try:
                    with transport,self.assertRaises((a.o.Held,FileNotFoundError)):ORIGINAL_NFS_GEOMETRY(facts,self.case.c.source,self.case.retention)
                finally:
                    self.common.chmod(0o711);self.case.c.library.chmod(0o700)
        self.assertFalse((self.case.c.writer.root/a.PENDING).exists())

    def test_same_device_separate_mount_ids_and_nested_shadow_refuse(self):
        for fault in ({'shadow':True},{'nested':True},{'readonly':True},{'source':'foreign:/export'}):
            facts,transport=self.mount_fixture(**fault)
            with self.subTest(fault=fault),transport,self.assertRaises(a.o.Held):
                ORIGINAL_NFS_GEOMETRY(facts,self.case.c.source,self.case.retention)
        self.assertFalse((self.case.c.writer.root/a.PENDING).exists())

    def test_actual_local_mount_cannot_satisfy_nfs_admission(self):
        facts,_=self.mount_fixture()
        with self.assertRaises(a.o.Held):
            ORIGINAL_NFS_GEOMETRY(facts,self.case.c.source,self.case.retention)
        self.assertFalse((self.case.c.writer.root/a.PENDING).exists())

    def test_noncooperating_post_cas_actor_is_outside_the_exclusion_contract(self):
        """Demonstrate the NFS primitive limit; this is not preservation proof.

        An actor that removes the admitted link, creates a foreign sole link and
        deletes it inside the syscall boundary can hide that foreign pathname.
        UID1000/0700 and fstat checks cannot exclude that actor. The owning
        contract requires it absent for the complete Writer/reader interval.
        """
        cap=self.cap();unlink=a.os.unlink;observed=[]
        library_id=(cap.source.parent.stat().st_dev,cap.source.parent.stat().st_ino)
        def actor(name,**kwargs):
            descriptor=kwargs.get('dir_fd')
            if not observed and name==cap.source.name and descriptor is not None and (lambda z:(z.st_dev,z.st_ino))(os.fstat(descriptor))==library_id:
                unlink(name,**kwargs)
                fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600,dir_fd=descriptor)
                try:os.write(fd,b'excluded external actor')
                finally:os.close(fd)
                observed.append(True)
            return unlink(name,**kwargs)
        with patch.object(a.os,'unlink',side_effect=actor):cap.install()
        self.assertTrue(observed)
        self.assertEqual(cap._phase,'installed')
        self.assertNotIn(b'excluded external actor',cap.source.read_bytes())
        self.assertEqual(cap.stage.read_bytes(),self.source_before)


if __name__ == '__main__':
    unittest.main()

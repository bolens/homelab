from contextlib import closing
import importlib.util
import os
from pathlib import Path
import sqlite3
import tempfile
import sys
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('backup', Path(__file__).with_name('comic_retained_standalone_backup.py'))
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name); self.root.chmod(0o700)
        self.native = self.root/'native'; self.reader = self.root/'reader'
        self.native.mkdir(); self.reader.mkdir()
        for root, name in ((self.native,'mylar.db'), (self.reader,'database.sqlite')):
            with closing(sqlite3.connect(root/name)) as db:
                db.execute('CREATE TABLE typed (id INTEGER PRIMARY KEY,value BLOB,n TEXT)')
                db.execute('INSERT INTO typed VALUES (1,?,NULL)', (b'\x00\xff',)); db.commit()
        self.source = self.native/'source.cbz'; self.source.write_bytes(b'source\0archive')
        self.target = self.root/'target.cbz'; self.target.write_bytes(b'target\0archive')
        self.scopes = [dict(role='native_state',root=str(self.native),databases=['mylar.db']),
                       dict(role='reader_state',root=str(self.reader),databases=['database.sqlite']),
                       dict(role='retained_source',root=str(self.source),databases=[]),
                       dict(role='existing_target',root=str(self.target),databases=[])]
        self.out = self.root/'preserved'
    def tearDown(self):
        self.tmp.cleanup()
    def run_backup(self):
        return b.copy_and_verify(self.scopes, self.out)
    def test_real_original_directory_birth_model_and_backup_restore(self):
        before=os.lstat(self.root);result=self.run_backup();answer=result.close()
        self.assertFalse(answer['ordinary_import'])
        for path in (self.out,self.out/'backup',self.out/'restore'):
            after=os.lstat(path)
            self.assertEqual(after.st_dev,before.st_dev)
            self.assertEqual(after.st_nlink==1,before.st_nlink==1)
        self.assertEqual((self.out/'restore/existing_target').read_bytes(),self.target.read_bytes())

    def test_real_fresh_original_directory_FD_census_and_drift_cleanup(self):
        directory=self.root/'fresh-census';directory.mkdir(mode=0o700)
        fd=os.open(directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW);real=b.os.listdir;fresh=[]
        try:
            self.assertEqual(b._directory_names(fd),())
            (directory/'child').mkdir(mode=0o700)
            self.assertEqual(b._directory_names(fd),('child',))
            def changed(value):
                names=real(value)
                if isinstance(value,int):fresh.append(value);os.chmod(directory,0o750)
                return names
            with patch.object(b.os,'listdir',changed),self.assertRaises(ValueError):b._directory_names(fd)
            self.assertEqual(len(fresh),1)
            with self.assertRaises(OSError):os.fstat(fresh[0])
            self.assertEqual(os.fstat(fd).st_ino,os.lstat(directory).st_ino)
        finally:os.close(fd)

    def test_real_sqlite_independent_private_copies(self):
        result = self.run_backup()
        self.assertFalse(result.close()['ordinary_import'])
        self.assertEqual((self.out/'backup/native_state/source.cbz').read_bytes(), self.source.read_bytes())
        self.assertNotEqual(os.lstat(self.out/'backup/native_state/source.cbz').st_ino,
                            os.lstat(self.out/'restore/native_state/source.cbz').st_ino)
        for phase in ('backup', 'restore'):
            self.assertEqual(os.lstat(self.out/phase/'retained_source').st_mode & 0o777, 0o600)
    def test_source_drift_after_backup_holds(self):
        result = self.run_backup(); self.source.write_bytes(b'foreign')
        with self.assertRaises(ValueError): result.close()
        self.assertFalse(result.close_copies()['cleanup'])
    def test_copy_replacement_identical_bytes_holds(self):
        result = self.run_backup(); p=self.out/'restore/existing_target'; data=p.read_bytes()
        p.unlink(); p.write_bytes(data); p.chmod(0o600)
        with self.assertRaises(ValueError): result.close_copies()
    def test_existing_output_refused(self):
        self.out.mkdir()
        with self.assertRaises(ValueError): self.run_backup()
    def test_known_root_mutated_first_enumeration_holds(self):
        real=b.os.listdir; fired=[]
        def change(path):
            values=real(path)
            if not fired:
                fired.append(True); self.source.chmod(0o640)
            return values
        with patch.object(b.os,'listdir',change), self.assertRaises(ValueError): self.run_backup()
        self.assertTrue(fired); self.assertFalse(self.out.exists())
    def test_created_file_first_fsync_security_mutation_holds(self):
        real=b.os.fsync; fired=[]
        def change(fd):
            z=os.fstat(fd)
            if z.st_mode & 0o170000 == 0o100000 and not fired:
                fired.append(True); os.fchmod(fd,0o640)
            return real(fd)
        with patch.object(b.os,'fsync',change), self.assertRaises(ValueError): self.run_backup()
        self.assertTrue(fired)
    def test_created_output_directory_replacement_holds(self):
        real=b.os.fsync; fired=[]
        def change(fd):
            if self.out.exists() and not fired:
                fired.append(True); self.out.rename(self.root/'original-out'); self.out.mkdir(mode=0o700)
            return real(fd)
        with patch.object(b.os,'fsync',change), self.assertRaises(ValueError): self.run_backup()
        self.assertTrue(fired)
    def test_explicit_source_original_precedes_first_validation_callback(self):
        real=b.need; fired=[]
        def change(value, reason):
            result=real(value,reason)
            if not fired:
                fired.append(True); self.target.chmod(0o640)
            return result
        with patch.object(b,'need',change), self.assertRaisesRegex(ValueError,'backup-root-conflict'):
            self.run_backup()
        self.assertTrue(fired); self.assertFalse(self.out.exists())
    def test_output_parent_transient_metadata_before_birth_holds(self):
        real=b.load_primitives; fired=[]
        def change(*args):
            result=real(*args); fired.append(True)
            self.root.chmod(0o750); self.root.chmod(0o700)
            return result
        with patch.object(b,'load_primitives',change), self.assertRaisesRegex(ValueError,'backup-output-parent-drift'):
            self.run_backup()
        self.assertTrue(fired); self.assertFalse(self.out.exists())
    def test_created_parent_metadata_during_first_file_fsync_holds(self):
        real=b.os.fsync; fired=[]
        def change(fd):
            z=os.fstat(fd)
            if z.st_mode & 0o170000 == 0o100000 and not fired:
                fired.append(True)
                directory=self.out/'backup/native_state'
                directory.chmod(0o750); directory.chmod(0o700)
            return real(fd)
        with patch.object(b.os,'fsync',change), self.assertRaises(ValueError): self.run_backup()
        self.assertTrue(fired)
    def test_foreign_namespace_after_close_holds(self):
        result=self.run_backup(); (self.out/'foreign').write_text('foreign')
        with self.assertRaises(ValueError): result.close()
    def test_constructor_and_forged_object_hold(self):
        with self.assertRaises(ValueError): b.BackupObservation()
        with self.assertRaises(ValueError): object.__new__(b.BackupObservation).close()
    def test_swapped_roles_hold(self):
        self.scopes.reverse()
        with self.assertRaises(ValueError): self.run_backup()
    def test_selected_hardlink_hold(self):
        os.link(self.source,self.root/'source-alias')
        with self.assertRaises(ValueError): self.run_backup()
    def test_parent_first_assertion_loss_closes_incoming_and_parent(self):
        self._copy_failure('parent_assertion')
    def test_parent_open_loss_closes_incoming(self):
        self._copy_failure('parent_open')
    def test_outgoing_open_loss_closes_incoming_and_parent(self):
        self._copy_failure('outgoing_open')
    def test_owned_insertion_assertion_loss_closes_all_FDs(self):
        self._copy_failure('insertion')
    def _copy_failure(self,kind):
        realopen=b.os.open;realneed=b.need;opened=[];fired=[]
        def opening(path,*args,**kwargs):
            caller=sys._getframe(1).f_code.co_name
            copying=caller=='copy_file' or (caller=='parent_fd' and sys._getframe(2).f_code.co_name=='copy_file')
            if copying and not fired and ((kind=='parent_open' and caller=='parent_fd') or
                    (kind=='outgoing_open' and caller=='copy_file' and args[0]&os.O_CREAT)):
                fired.append(True);raise OSError('disposable '+kind)
            fd=realopen(path,*args,**kwargs)
            if copying:opened.append(fd)
            return fd
        def assertion(value,reason):
            result=realneed(value,reason)
            copying=sys._getframe(1).f_code.co_name=='copy_file' or sys._getframe(2).f_code.co_name=='copy_file'
            if copying and not fired and ((kind=='parent_assertion' and reason=='backup-parent-namespace') or
                    (kind=='insertion' and reason=='backup-owned-directory-transition')):
                fired.append(True);raise OSError('disposable '+kind)
            return result
        with patch.object(b.os,'open',opening),patch.object(b,'need',assertion),self.assertRaisesRegex(OSError,'disposable'):
            self.run_backup()
        self.assertTrue(fired);self.assertTrue(opened)
        live=[]
        for fd in opened:
            try:os.fstat(fd);live.append(fd)
            except OSError:pass
        try:self.assertEqual(live,[])
        finally:
            for fd in live:os.close(fd)
    def test_foreign_reused_incoming_FD_remains_open(self):
        self._foreign_fd('incoming')
    def test_foreign_reused_parent_FD_remains_open(self):
        self._foreign_fd('parent')
    def test_foreign_reused_outgoing_FD_remains_open(self):
        self._foreign_fd('outgoing')
    def test_erased_incoming_FD_preserves_original_failure(self):
        self._foreign_fd('erased')
    def _foreign_fd(self, kind):
        realopen=b.os.open;realneed=b.need;owned={};foreign=[];fired=[]
        path=self.root/'unrelated-resource';path.write_bytes(b'unrelated bytes')
        def opening(path,*args,**kwargs):
            fd=realopen(path,*args,**kwargs);caller=sys._getframe(1).f_code.co_name
            if caller=='copy_file':owned['outgoing' if args[0]&os.O_CREAT else 'incoming']=fd
            elif caller=='parent_fd' and sys._getframe(2).f_code.co_name=='copy_file':owned['parent']=fd
            return fd
        def assertion(value,reason):
            result=realneed(value,reason)
            if not fired and 'incoming' in owned and reason==('backup-owned-directory-transition' if kind=='outgoing' else 'backup-parent-namespace'):
                fd=owned['incoming' if kind=='erased' else kind];os.close(fd);fired.append(True)
                if kind!='erased':
                    replacement=realopen(path,os.O_RDONLY|os.O_NOFOLLOW);foreign.append(replacement)
                    self.assertEqual(replacement,fd)
                raise OSError('disposable original FD replaced')
            return result
        try:
            with patch.object(b.os,'open',opening),patch.object(b,'need',assertion),self.assertRaisesRegex(OSError,'original FD replaced'):
                self.run_backup()
            self.assertTrue(fired)
            for fd in foreign:self.assertEqual(os.read(fd,100),b'unrelated bytes')
            for fd in owned.values():
                if fd not in foreign:
                    with self.assertRaises(OSError):os.fstat(fd)
        finally:
            for fd in foreign:
                try:os.close(fd)
                except OSError:pass
    def test_last_copy_callback_reused_outgoing_FD_holds_without_close(self):
        realopen=b.os.open;realneed=b.need;outgoing=[];foreign=[];fired=[]
        path=self.root/'last-foreign';path.write_bytes(b'unchanged foreign')
        def opening(path,*args,**kwargs):
            fd=realopen(path,*args,**kwargs)
            if sys._getframe(1).f_code.co_name=='copy_file' and args[0]&os.O_CREAT:outgoing.append(fd)
            return fd
        def assertion(value,reason):
            result=realneed(value,reason)
            if reason=='backup-created-file-drift' and not fired:
                fd=outgoing[-1];os.close(fd);replacement=realopen(path,os.O_RDONLY|os.O_NOFOLLOW)
                if replacement!=fd:
                    os.dup2(replacement,fd);os.close(replacement);replacement=fd
                foreign.append(replacement);self.assertEqual(fd,replacement);fired.append(True)
            return result
        try:
            with patch.object(b.os,'open',opening),patch.object(b,'need',assertion),self.assertRaisesRegex(ValueError,'backup-copy-FD-ownership'):
                self.run_backup()
            self.assertTrue(fired);self.assertEqual(os.read(foreign[0],100),b'unchanged foreign')
        finally:
            for fd in foreign:os.close(fd)
    def test_archive_fixed_size_bound(self):
        with self.target.open('r+b') as stream: stream.truncate(b.MAX_ARCHIVE_BYTES+1)
        with self.assertRaises(ValueError): self.run_backup()

if __name__ == '__main__': unittest.main()

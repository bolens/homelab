"""Original backup witnesses survive callbacks without adopting changed copies."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import stat
import struct
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import closing, contextmanager
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import comic_retained_pack_backup as backup


class Custody(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)
        self.scopes = []
        for role in ('native_config', 'worker_state', 'reader_config'):
            path = self.root / role
            path.mkdir()
            (path / 'payload').write_bytes(b'original')
            with closing(sqlite3.connect(path / 'state.sqlite')) as db:
                db.execute('CREATE TABLE protected(k TEXT)')
                db.execute("INSERT INTO protected VALUES ('preserve')")
                db.commit()
            self.scopes.append(dict(role=role, root=str(path), databases=['state.sqlite']))
        self.primitives = Path(backup.__file__).parent / 'comic_reader_backup_primitives.py'
        self.pin = hashlib.sha256(self.primitives.read_bytes()).hexdigest()

    def copy(self):
        return backup.copy_and_verify(self.scopes, self.root / 'copies', self.primitives, self.pin)

    def test_verified_copies_close_without_reopening_payloads_or_SQL(self):
        original=backup.os.open;calls=[]
        def observed(*args,**kwargs):
            calls.append(args[0]);return original(*args,**kwargs)
        with patch.object(backup.os,'open',side_effect=observed):
            held=self.copy();before=len(calls)
            for _ in range(3):held.close();held.close_copies()
            self.assertEqual(len(calls),before)
        target=self.root/'copies/restore/native_config/payload'
        target.write_bytes(b'changed payload')
        with self.assertRaises(ValueError):held.close_copies()

    def test_discovered_SQLite_count_comes_from_the_closed_file_census(self):
        archive=Path(self.scopes[1]['root'])/'retained-history';archive.mkdir()
        for index in range(17):
            with closing(sqlite3.connect(archive/(str(index)+'.sqlite'))) as db:
                db.execute('CREATE TABLE preserved(value TEXT)');db.commit()
        held=self.copy();row=backup._OBS[held]
        self.assertEqual(len(row['databases']),20)
        self.assertEqual(len(row['required']),3)
        self.assertEqual(row['databases']['worker_state:retained-history/16.sqlite']['tables']['preserved']['rows'],0)
        held.close();held.close_copies()

    def test_current_census_reuses_only_unchanged_original_hashes(self):
        held=self.copy();opening=os.open;reads=[]
        def observed(path,*args,**kwargs):
            reads.append(str(path));return opening(path,*args,**kwargs)
        payload=Path(self.scopes[1]['root'])/'payload'
        with patch.object(os,'open',side_effect=observed):
            original,measured=held.current_scopes()
            self.assertNotIn(str(payload),reads)
            self.assertEqual(next(r for r in measured['worker_state']if r['path']=='payload')['sha256'],hashlib.sha256(b'original').hexdigest())
            payload.write_bytes(b'changed');reads.clear()
            _,current=held.current_scopes()
            self.assertIn(str(payload),reads)
            self.assertEqual(next(r for r in current['worker_state']if r['path']=='payload')['sha256'],hashlib.sha256(b'changed').hexdigest())
        self.assertEqual(next(r for r in original['source_scopes'][1]['records']if r['path']=='payload')['sha256'],hashlib.sha256(b'original').hexdigest())
        held.close_copies()
        with self.assertRaises(ValueError):held.close()

    def test_current_hash_reuse_cannot_adopt_transient_registry_rebase(self):
        held=self.copy();row=backup._OBS[held]['source_scopes'][1]['records']
        payload=next(value for value in row if value['path']=='payload');original_hash=payload['sha256']
        snapshot=backup.snapshot;project=backup._projection;fired=[]
        def changed(*args,**kwargs):
            result=snapshot(*args,**kwargs);payload['sha256']='f'*64;fired.append(True);return result
        def restored(value):
            if type(value)is tuple and len(value)==2 and type(value[1])is dict and 'worker_state'in value[1]:payload['sha256']=original_hash
            return project(value)
        try:
            with patch.object(backup,'snapshot',changed),patch.object(backup,'_projection',restored):
                _,current=held.current_scopes()
            self.assertTrue(fired)
            self.assertEqual(next(value for value in current['worker_state']if value['path']=='payload')['sha256'],original_hash)
        finally:payload['sha256']=original_hash

    def test_current_census_detects_new_file_without_replacing_baseline(self):
        held=self.copy();new=Path(self.scopes[1]['root'])/'new';new.write_bytes(b'new')
        original,current=held.current_scopes()
        self.assertEqual(next(r for r in current['worker_state']if r['path']=='new')['sha256'],hashlib.sha256(b'new').hexdigest())
        self.assertNotIn('new',{r['path']for r in original['source_scopes'][1]['records']})
        held.close_copies()

    def test_current_census_cannot_outlive_caller_phase_or_original_copy(self):
        held=self.copy()
        with self.assertRaisesRegex(ValueError,'current-original-deadline'):held.current_scopes(deadline=0)
        target=self.root/'copies/restore/native_config/payload';target.write_bytes(b'foreign')
        with self.assertRaises(ValueError):held.current_scopes()

    def test_original_caller_deadline_refuses_before_output(self):
        with self.assertRaisesRegex(ValueError,'original-deadline'):
            backup.copy_and_verify(self.scopes,self.root/'copies',self.primitives,self.pin,deadline=0)
        self.assertFalse((self.root/'copies').exists())

    def test_restore_clone_space_keeps_logical_and_scratch_budgets(self):
        frame,total=backup.snapshot([Path(row['root']) for row in self.scopes],source_links=True)
        ordinary=backup.required_space(total,frame)
        cloned=backup.required_space(total,frame,reflink_restore=True)
        self.assertEqual(ordinary-cloned,total)
        largest=max(z[2] for _,z in frame[0] if z[5]&0o170000==0o100000)
        self.assertGreaterEqual(cloned,total+4*largest+2*1024**2)

    def test_copy_attribute_change_still_refuses_without_content_rehash(self):
        held=self.copy();target=self.root/'copies/restore/native_config/payload'
        target.chmod(0o600 if stat.S_IMODE(target.stat().st_mode)!=0o600 else 0o400)
        with self.assertRaises(ValueError):held.close_copies()

    def test_config_symlink_preserved_without_following_external_target(self):
        outside=self.root/'outside';outside.write_bytes(b'preserve outside scope')
        alias=Path(self.scopes[0]['root'])/'font-alias';alias.symlink_to(outside)
        held=self.copy();held.close()
        for stage in ('backup','restore'):
            copied=self.root/'copies'/stage/'native_config'/'font-alias'
            self.assertTrue(copied.is_symlink());self.assertEqual(os.readlink(copied),str(outside))
        self.assertEqual(outside.read_bytes(),b'preserve outside scope')
        alias.unlink();alias.symlink_to(self.root/'foreign')
        with self.assertRaises(ValueError):held.close()

    def test_closed_source_hardlinks_restore_as_independent_copies(self):
        source=Path(self.scopes[1]['root']);os.link(source/'payload',source/'preserved-payload')
        before=backup.nine((source/'payload').stat())
        held=self.copy();held.close();held.close_copies()
        self.assertEqual(backup.nine((source/'payload').stat()),before)
        for stage in ('backup','restore'):
            first=self.root/'copies'/stage/'worker_state'/'payload'
            second=first.with_name('preserved-payload')
            self.assertEqual(first.read_bytes(),second.read_bytes())
            self.assertEqual(first.stat().st_nlink,1);self.assertEqual(second.stat().st_nlink,1)
            self.assertNotEqual(first.stat().st_ino,second.stat().st_ino)

    def test_source_link_outside_backup_scope_refuses_before_output(self):
        os.link(Path(self.scopes[1]['root'])/'payload',self.root/'outside-link')
        with self.assertRaisesRegex(ValueError,'backup-source-link-group'):self.copy()
        self.assertFalse((self.root/'copies').exists())

    def test_copy_node_budget_derived_from_both_original_trees(self):
        roots=[Path(s['root'])for s in self.scopes];original,_=backup.snapshot(roots)
        with patch.object(backup,'MAX_NODES',len(original[0])):
            held=self.copy();held.close();held.close_copies()

    def test_double_byte_budget_refuses_before_output(self):
        _,size=backup.snapshot([Path(s['root'])for s in self.scopes])
        with patch.object(backup,'MAX_BYTES',size),self.assertRaisesRegex(ValueError,'backup-two-copy-byte-bound'):self.copy()
        self.assertFalse((self.root/'copies').exists())

    def test_default_snapshot_still_refuses_source_alias(self):
        source=Path(self.scopes[1]['root']);os.link(source/'payload',source/'alias')
        with self.assertRaisesRegex(ValueError,'backup-selected-alias'):backup.snapshot([source])

    def test_duplicate_root_does_not_supply_missing_link(self):
        source=Path(self.scopes[1]['root']);os.link(source/'payload',self.root/'outside')
        with self.assertRaisesRegex(ValueError,'backup-source-link-group'):
            backup.snapshot([source,source],source_links=True)

    def test_source_link_metadata_disagreement_refuses(self):
        source=Path(self.scopes[1]['root']);alias=source/'alias';os.link(source/'payload',alias);original=os.lstat
        def changed(path,*args,**kwargs):
            z=original(path,*args,**kwargs)
            if Path(path)==alias:
                fields=dict(zip(('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_uid','st_gid','st_nlink'),backup.nine(z)))
                fields['st_gid']+=1;return SimpleNamespace(**fields)
            return z
        with patch.object(backup.os,'lstat',side_effect=changed),self.assertRaisesRegex(ValueError,'backup-source-link-group'):
            backup.snapshot([source],source_links=True)

    def test_link_added_at_final_raw_callback_is_not_adopted(self):
        source=Path(self.scopes[1]['root']);os.link(source/'payload',source/'alias');original=backup.raw
        def changed(frame):
            os.link(source/'payload',self.root/'outside');return original(frame)
        with patch.object(backup,'raw',side_effect=changed),self.assertRaisesRegex(ValueError,'backup-original-file'):
            backup.snapshot([source],source_links=True)

    def test_copy_count_rejects_bool_and_incomplete_tree(self):
        roots=[Path(s['root'])for s in self.scopes[:2]]
        with self.assertRaisesRegex(ValueError,'backup-copy-source-count'):backup.snapshot(roots,source_nodes=True)
        with self.assertRaisesRegex(ValueError,'backup-copy-node-count'):backup.snapshot(roots,source_nodes=50)

    def rebase(self, held):
        row = backup._OBS[held]
        module = row['module']
        for stage in ('backup', 'restore'):
            path = self.root / 'copies' / stage / 'native_config' / 'payload'
            attributes = module.attrs(path)
            path.write_bytes(b'foreign')
            module.apply_attrs(path, attributes)
        rows, _ = module.inventory(self.root / 'copies/backup/native_config', 'tree', detached=True)
        row['logical']['native_config'] = module.logical(rows)
        row['copies'], _ = backup.snapshot([self.root / 'copies/backup', self.root / 'copies/restore'])

    def test_rebased_copies_cannot_replace_original_witness(self):
        held = self.copy()
        self.rebase(held)
        with self.assertRaisesRegex(ValueError, 'backup-original'):
            held.close_copies()

    def test_equal_registry_entry_replacement_refuses(self):
        held = self.copy()
        backup._OBS[held] = dict(backup._OBS[held])
        with self.assertRaisesRegex(ValueError, 'backup-original'):
            held.close_copies()

    def test_equal_registry_table_replacement_refuses(self):
        held = self.copy()
        with patch.object(backup, '_OBS', dict(backup._OBS)):
            with self.assertRaisesRegex(ValueError, 'backup-original'):
                held.close_copies()

    def test_callback_cannot_rebase_both_copies_before_final_closure(self):
        held = self.copy()
        original = backup.raw
        fired = []
        def late(frame):
            if not fired:
                fired.append(True)
                self.rebase(held)
            return original(frame)
        with patch.object(backup, 'raw', late):
            with self.assertRaises(ValueError):
                held.close_copies()
        self.assertTrue(fired)

    def test_factory_cannot_publish_callback_rebased_observation(self):
        original = backup.BackupObservation.close
        fired = []
        def late(held):
            fired.append(True)
            self.rebase(held)
            return original(held)
        with patch.object(backup.BackupObservation, 'close', late):
            with self.assertRaisesRegex(ValueError, 'backup-original'):
                self.copy()
        self.assertTrue(fired)

    def test_factory_serializer_cannot_rebase_unsealed_witness(self):
        encoder = backup.encode
        fired = []
        def late(value):
            if type(value) is dict and 'out' in value and 'digest' in value and not fired:
                pending = [held for held in backup._OBS if held not in backup._SEALS]
                self.assertEqual(len(pending), 1)
                fired.append(True)
                self.rebase(pending[0])
                value['copies'] = backup._OBS[pending[0]]['copies']
            return encoder(value)
        with patch.object(backup, 'encode', late):
            with self.assertRaisesRegex(ValueError, 'backup-original'):
                self.copy()
        self.assertTrue(fired)

    def test_inventory_callback_cannot_replace_database_verifier(self):
        loader = backup.source_module
        listxattr = os.listxattr
        fired = []
        foreign_calls = []
        def loaded(*args):
            module, frame = loader(*args)
            def foreign(*args):
                foreign_calls.append(True)
                return []
            def mutation(*args, **kwargs):
                if not fired:
                    fired.append(True)
                    module.database_rows = foreign
                return listxattr(*args, **kwargs)
            guard = patch.object(os, 'listxattr', mutation)
            guard.start()
            self.addCleanup(guard.stop)
            return module, frame
        with patch.object(backup, 'source_module', loaded):
            with self.assertRaisesRegex(ValueError, 'backup-original-primitive'):
                self.copy()
        self.assertTrue(fired)
        self.assertFalse(foreign_calls)

    def test_equal_but_differently_typed_keyword_default_refuses(self):
        held = self.copy()
        module = backup._OBS[held]['module']
        self.assertIs(module.inventory.__kwdefaults__['detached'], False)
        module.inventory.__kwdefaults__['detached'] = 0
        with self.assertRaisesRegex(ValueError, 'backup-original-primitive'):
            held.close_copies()

    def test_foreign_serializer_cannot_replace_returned_summary(self):
        encoder = backup.encode
        fired = []
        def foreign(value):
            if type(value) is dict and 'out' in value and 'digest' in value:
                fired.append(True)
                replacement = json.loads(encoder(value))
                replacement['digest'] = 'f'*64
                return encoder(replacement)
            return encoder(value)
        with patch.object(backup, 'encode', foreign):
            with self.assertRaisesRegex(ValueError, 'backup-original-factory-encoding'):
                self.copy()
        self.assertTrue(fired)




class OriginalDeadline(unittest.TestCase):
    def setUp(self):
        import comic_reader_backup_primitives as primitive
        self.p=primitive
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)

    def test_attribute_batch_refuses_reader_rebinding_before_next_leaf(self):
        path=self.root/'one';path.write_bytes(b'original')
        original=self.p.attrs;listing=os.listxattr;fired=[]
        def changed(*args,**kwargs):
            if not fired:self.p.attrs=lambda path: {};fired.append(True)
            return listing(*args,**kwargs)
        try:
            with patch.object(os,'listxattr',changed),self.assertRaisesRegex(self.p.Held,'attributes-original-reader'):
                self.p.attributes_many((path,path))
        finally:self.p.attrs=original
        self.assertTrue(fired)

    def test_expired_hash_refuses_before_open(self):
        path=self.root/'source';path.write_bytes(b'preserve')
        with patch.object(self.p.os,'open') as opening:
            with self.assertRaisesRegex(self.p.Held,'original-deadline'):self.p.hash_file(path,deadline=0)
        opening.assert_not_called()

    def test_copy_stream_checks_original_deadline_between_chunks(self):
        import io
        source=io.BytesIO(b'a'*(2*1024**2));target=io.BytesIO()
        with patch.object(self.p.time,'monotonic',side_effect=[1,1,3]):
            with self.assertRaisesRegex(self.p.Held,'original-deadline'):self.p.copy_stream(source,target,2)
        self.assertEqual(len(target.getvalue()),1024**2)

    def test_expired_database_refuses_before_scratch_or_hash(self):
        path=self.root/'database.sqlite';path.write_bytes(b'preserve')
        with patch.object(self.p.tempfile,'TemporaryDirectory') as scratch:
            with self.assertRaisesRegex(self.p.Held,'original-deadline'):self.p.database(path,deadline=0)
        scratch.assert_not_called();self.assertEqual(path.read_bytes(),b'preserve')

    def test_nonfinite_deadline_is_not_execution_authority(self):
        for deadline in (float('nan'),float('inf'),True):
            with self.subTest(deadline=deadline),self.assertRaisesRegex(self.p.Held,'original-deadline'):
                self.p.check_deadline(deadline)

    def test_restore_clone_failure_never_streams_fallback(self):
        import errno
        source=self.root/'source';source.write_bytes(b'original')
        rows,_=self.p.inventory(source,'file')
        with patch.object(self.p.fcntl,'ioctl',side_effect=OSError(errno.EOPNOTSUPP,'unsupported')):
            with self.assertRaises(OSError):self.p.copy_scope(source,self.root/'target',rows,reflink=True)
        self.assertEqual((self.root/'target').read_bytes(),b'')
        self.assertEqual(source.read_bytes(),b'original')

    def test_clone_probe_refuses_foreign_creation_error(self):
        import errno
        before=tuple(self.root.iterdir())
        with patch.object(self.p.fcntl,'ioctl',side_effect=OSError(errno.EIO,'failure')):
            with self.assertRaises(OSError):self.p.qualify_reflink_restore(self.root)
        self.assertEqual(tuple(self.root.iterdir()),before)


class NfsAclTransport(unittest.TestCase):
    def setUp(self):
        import comic_reader_backup_primitives as primitive
        self.p = primitive
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.root.chmod(0o700)

    def acl(self, mode, kind='file'):
        return self.p.mode_nfs4_acl(mode, kind)

    @contextmanager
    def nfs(self, root, override=None):
        listing, getting, removing = os.listxattr, os.getxattr, os.removexattr
        def selected(path):
            return Path(path).is_relative_to(root)
        def names(path, **kwargs):
            return listing(path, **kwargs) + (['system.nfs4_acl'] if selected(path) else [])
        def value(path, name, **kwargs):
            if name == 'system.nfs4_acl' and selected(path):
                z = os.lstat(path)
                return override if override is not None else self.acl(stat.S_IMODE(z.st_mode), 'directory' if stat.S_ISDIR(z.st_mode) else 'file')
            return getting(path, name, **kwargs)
        def remove(path, name, **kwargs):
            if name == 'system.nfs4_acl':raise OSError(22, 'server-derived ACL cannot be removed')
            return removing(path, name, **kwargs)
        with patch.object(os, 'listxattr', side_effect=names), patch.object(os, 'getxattr', side_effect=value), patch.object(os, 'removexattr', side_effect=remove):
            yield

    def test_actual_nfs_mode_acl_fixtures(self):
        for kind, mode, encoded in [('file', 0, '00000003000000000000000000160180000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 256, '00000003000000000000000000160181000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 384, '00000003000000000000000000160187000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 420, '00000003000000000000000000160187000000064f574e45524000000000000000000000001200810000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000'), ('file', 436, '00000003000000000000000000160187000000064f574e45524000000000000000000000001200870000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000'), ('file', 438, '00000003000000000000000000160187000000064f574e45524000000000000000000000001200870000000647524f55504000000000000000000000001200870000000945564552594f4e4540000000'), ('file', 448, '000000030000000000000000001601a7000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 488, '000000030000000000000000001601a7000000064f574e45524000000000000000000000001200a10000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 493, '000000030000000000000000001601a7000000064f574e45524000000000000000000000001200a10000000647524f55504000000000000000000000001200a10000000945564552594f4e4540000000'), ('file', 504, '000000030000000000000000001601a7000000064f574e45524000000000000000000000001200a70000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('file', 511, '000000030000000000000000001601a7000000064f574e45524000000000000000000000001200a70000000647524f55504000000000000000000000001200a70000000945564552594f4e4540000000'), ('file', 39, '00000005000000010000000000000027000000064f574e4552400000000000000000000000160180000000064f574e45524000000000000000000000001200810000000647524f55504000000000000100000000000000260000000647524f55504000000000000000000000001200a70000000945564552594f4e4540000000'), ('file', 271, '00000005000000010000000000000026000000064f574e4552400000000000000000000000160181000000064f574e45524000000000000000000000001200a00000000647524f55504000000000000100000000000000070000000647524f55504000000000000000000000001200a70000000945564552594f4e4540000000'), ('file', 452, '000000040000000000000000001601a7000000064f574e45524000000000000000000000001200800000000647524f55504000000000000100000000000000010000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000'), ('directory', 0, '00000003000000000000000000160180000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 256, '00000003000000000000000000160181000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 384, '000000030000000000000000001601c7000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 420, '000000030000000000000000001601c7000000064f574e45524000000000000000000000001200810000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000'), ('directory', 436, '000000030000000000000000001601c7000000064f574e45524000000000000000000000001200c70000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000'), ('directory', 438, '000000030000000000000000001601c7000000064f574e45524000000000000000000000001200c70000000647524f55504000000000000000000000001200c70000000945564552594f4e4540000000'), ('directory', 448, '000000030000000000000000001601e7000000064f574e45524000000000000000000000001200800000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 488, '000000030000000000000000001601e7000000064f574e45524000000000000000000000001200a10000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 493, '000000030000000000000000001601e7000000064f574e45524000000000000000000000001200a10000000647524f55504000000000000000000000001200a10000000945564552594f4e4540000000'), ('directory', 504, '000000030000000000000000001601e7000000064f574e45524000000000000000000000001200e70000000647524f55504000000000000000000000001200800000000945564552594f4e4540000000'), ('directory', 511, '000000030000000000000000001601e7000000064f574e45524000000000000000000000001200e70000000647524f55504000000000000000000000001200e70000000945564552594f4e4540000000'), ('directory', 39, '00000005000000010000000000000067000000064f574e4552400000000000000000000000160180000000064f574e45524000000000000000000000001200810000000647524f55504000000000000100000000000000660000000647524f55504000000000000000000000001200e70000000945564552594f4e4540000000'), ('directory', 271, '00000005000000010000000000000066000000064f574e4552400000000000000000000000160181000000064f574e45524000000000000000000000001200a00000000647524f55504000000000000100000000000000470000000647524f55504000000000000000000000001200e70000000945564552594f4e4540000000'), ('directory', 452, '000000040000000000000000001601e7000000064f574e45524000000000000000000000001200800000000647524f55504000000000000100000000000000010000000647524f55504000000000000000000000001200810000000945564552594f4e4540000000')]:
            with self.subTest(kind=kind, mode=mode):
                self.assertEqual(self.acl(mode, kind).hex(), encoded)

    def test_all_modes_have_exact_posix_data_permissions(self):
        for kind in ('file', 'directory'):
            for mode in range(0o1000):
                raw = self.acl(mode, kind); count = struct.unpack_from('>I', raw)[0]; offset = 4; aces = []
                for _ in range(count):
                    typ, flags, mask, size = struct.unpack_from('>IIII', raw, offset); offset += 16
                    who = raw[offset:offset+size].decode(); offset += (size+3)//4*4
                    self.assertEqual(flags, 0); aces.append((typ, mask, who))
                self.assertEqual(offset, len(raw))
                for owner, group, bits in ((True, True, mode>>6), (True, False, mode>>6), (False, True, mode>>3), (False, False, mode)):
                    for bit, requested in ((4, 1), (2, 2), (2, 4), (1, 0x20), *(([(2, 0x40)]) if kind=='directory' else [])):
                        allowed = False
                        for typ, mask, who in aces:
                            if mask & requested and (who=='EVERYONE@' or who=='OWNER@' and owner or who=='GROUP@' and group):
                                allowed = typ==0; break
                        self.assertEqual(allowed, bool(bits & bit), (kind, mode, owner, group, requested))

    def test_noncanonical_acl_never_projects(self):
        expected = dict(mode=0o600, uid=1000, gid=1000, mtime_ns=1, xattrs={})
        valid = self.acl(0o600)
        mutations = [valid[:-1], valid+b'\0', valid[:8]+struct.pack('>I', 1)+valid[12:], valid.replace(b'OWNER@', b'NAMED@'), valid[:12]+struct.pack('>I', 0xffffffff)+valid[16:]]
        for raw in mutations:
            actual = dict(expected, xattrs={'system.nfs4_acl':raw.hex()})
            self.assertFalse(self.p.copied_attributes_match(actual, expected, 'file'))

    def test_source_present_acl_and_other_attributes_stay_exact(self):
        expected = dict(mode=0o600, uid=1000, gid=1000, mtime_ns=1, xattrs={'system.nfs4_acl':'0102', 'user.fixture':'03'})
        self.assertTrue(self.p.copied_attributes_match(expected, expected, 'file'))
        for attrs in ({'system.nfs4_acl':self.acl(0o600).hex(), 'user.fixture':'03'}, {'system.nfs4_acl':'0102'}, dict(expected['xattrs'], **{'user.foreign':'00'})):
            self.assertFalse(self.p.copied_attributes_match(dict(expected, xattrs=attrs), expected, 'file'))
        self.assertFalse(self.p.copied_attributes_match(dict(expected, mode=0o644), expected, 'file'))

    def test_foreign_acl_refuses_before_ownership_or_mode_change(self):
        path = self.root/'file'; path.write_bytes(b'original'); expected = self.p.attrs(path)
        with self.nfs(path, override=b'foreign'), patch.object(os, 'chown') as chown, patch.object(os, 'chmod') as chmod:
            with self.assertRaises(self.p.Held):self.p.apply_attrs(path, expected)
        chown.assert_not_called(); chmod.assert_not_called()

    def test_late_acl_after_chmod_refuses(self):
        path = self.root/'file'; path.write_bytes(b'original'); expected = self.p.attrs(path); real = os.chmod; changed = []
        def chmod(*args, **kwargs):
            real(*args, **kwargs); changed.append(True)
        original = os.getxattr
        def value(p, name, **kwargs):
            if name=='system.nfs4_acl':return b'late-foreign' if changed else self.acl(stat.S_IMODE(os.lstat(p).st_mode))
            return original(p, name, **kwargs)
        with self.nfs(path), patch.object(os, 'getxattr', side_effect=value), patch.object(os, 'chmod', side_effect=chmod):
            with self.assertRaises(self.p.Held):self.p.apply_attrs(path, expected)
        self.assertTrue(changed)

    def test_nfs_roundtrip_preserves_source_and_strict_logical_comparison(self):
        source=self.root/'source'; source.mkdir(mode=0o700); (source/'payload').write_bytes(b'preserved')
        os.setxattr(source/'payload', 'user.fixture', b'keep')
        rows,_=self.p.inventory(source,'tree'); nfs=self.root/'nfs'; restored=self.root/'restored'
        with self.nfs(nfs):
            self.p.copy_scope(source,nfs,rows); copied,_=self.p.inventory(nfs,'tree',detached=True)
            self.assertNotEqual(self.p.logical(copied),self.p.logical(rows))
            self.assertTrue(self.p.copied_records_match(copied,rows))
            self.p.copy_scope(nfs,restored,rows)
        returned,_=self.p.inventory(restored,'tree',detached=True)
        self.assertEqual(self.p.logical(returned),self.p.logical(rows))
        self.assertEqual(self.p.inventory(source,'tree')[0],rows)


if __name__ == '__main__':
    unittest.main()

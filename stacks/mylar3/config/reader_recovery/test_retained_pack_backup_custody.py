"""Original backup witnesses survive callbacks without adopting changed copies."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import closing
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


if __name__ == '__main__':
    unittest.main()

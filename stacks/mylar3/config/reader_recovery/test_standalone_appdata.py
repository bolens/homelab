"""Original factory/terminal tests with a disposable synthetic Docker CLI.

The fixture exercises real streaming, restore, SQL and descriptor checks. It
does not establish an encrypted repository or configured runtime acceptance.
"""
import importlib.util
import os
from pathlib import Path
import sys
import tarfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from appdata_cli_fixture import synthetic_cli
import test_standalone_directory_joins as fixture


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ResticDirectoryTests(unittest.TestCase):
    def setUp(self):
        host = Path(__file__).parent.parent / 'standalone_launch_host'
        self.backup_module = load('appdata_original_backup', host / 'comic_retained_standalone_backup.py')
        self.modules = patch.dict(sys.modules, {'comic_retained_standalone_backup': self.backup_module})
        self.modules.start()
        self.addCleanup(self.modules.stop)
        self.parent = load('appdata_original_parent', host / 'comic_retained_standalone_parent.py')
        self.case = fixture.DirectoryTests('test_actual_backup_noop_sole_record_and_three_insertions')
        self.case.existing_journal = True
        self.case.restic_prior_fixture = True
        changes = patch.multiple(fixture, p=self.parent,
                                 b=SimpleNamespace(copy_and_verify=self.make_backup))
        changes.start()
        self.addCleanup(changes.stop)
        self.addCleanup(self.cleanup_case)
        self.case.setUp()
        # Reader app data has no Native mount or writable alias.
        self.case.mounts=[dict(Type='bind',Source=str(path),Destination=str(path),RW=True)
                          for path in (self.case.data,self.case.cache,self.case.library)]

    def cleanup_case(self):
        observation = getattr(self.case, 'backup', None)
        if observation is not None:
            witness = self.backup_module._OBSERVATIONS[observation]['restic']
            records = [(witness['snapshot_fd'], tuple(witness['snapshot_signature9']))]
            records.extend((fd, tuple(frame)) for _, fd, frame, _ in witness['restore_custody'])
            for fd, original in records:
                try:
                    if self.backup_module.nine(os.fstat(fd)) == original:
                        os.close(fd)
                except OSError:
                    pass
            for _, fd, original in (*witness['output_ancestors'], *witness['mount_custody']):
                try:
                    if self.backup_module.five(os.fstat(fd)) == tuple(original):
                        os.close(fd)
                except OSError:
                    pass
        if hasattr(self.case, 'tmp'):
            self.case.tmp.cleanup()

    def make_backup(self, scopes, output):
        with synthetic_cli(self.case.root) as artifact:
            self.artifact = artifact
            return self.backup_module.copy_and_verify(scopes, output, restic_appdata=True)

    def witness(self):
        return self.backup_module._OBSERVATIONS[self.case.backup]['restic']

    def call(self):
        return self.case.call()

    def test_real_stream_restore_SQL_and_original_terminal_join_without_media_copies(self):
        result = self.call()
        witness = self.witness()
        self.assertFalse(result['ordinary_import'])
        self.assertFalse((self.case.root / 'copies/backup').exists())
        self.assertEqual(len(self.backup_module._OBSERVATIONS[self.case.backup]['databases']), 4)
        with tarfile.open(self.artifact) as archive:
            self.assertFalse(any(name.endswith('.cbz') for name in archive.getnames()))
        self.assertIn(witness['snapshot_path'], dict(result['original_vectors'][0]))

    def test_prior_preservation_and_extra_database_survive_app_only_restore(self):
        self.call()
        restored = self.case.root / 'copies/restore'
        prior = Path('retained-standalone-v1') / ('b'*64)
        self.assertEqual((restored/'native_config'/prior/'accepted.json').read_bytes(),
                         (self.case.data/prior/'accepted.json').read_bytes())
        for stem in ('target-preserved','target-restored'):
            for suffix in ('.cbz','.cbr','.zip'):
                self.assertTrue((self.case.data/prior/(stem+suffix)).is_file())
                self.assertFalse((restored/'native_config'/prior/(stem+suffix)).exists())
        state=self.backup_module._OBSERVATIONS[self.case.backup]
        original=dict(state['source_databases'])[str(self.case.reader/'tasks.sqlite')]
        self.assertEqual(original['tables']['additional']['rows'],1)
        self.assertEqual(dict(state['databases'])[str(restored/'reader_config/tasks.sqlite')],original)

    def late_change(self, change):
        original = self.parent.raw
        fired = []
        def callback(frame):
            original(frame)
            if not fired:
                fired.append(True)
                change()
        with patch.object(self.parent, 'raw', callback), self.assertRaises((ValueError, OSError)):
            self.call()
        self.assertEqual(fired, [True])

    def test_snapshot_descriptor_loss_after_copy_close_holds(self):
        self.late_change(lambda: os.close(self.witness()['snapshot_fd']))

    def test_output_ancestor_descriptor_loss_after_copy_close_holds(self):
        self.late_change(lambda: os.close(self.witness()['output_ancestors'][-1][1]))

    def test_snapshot_binding_change_after_copy_close_holds(self):
        self.late_change(lambda: self.witness().__setitem__('snapshot_id', 'f'*64))

    def test_foreign_restore_namespace_holds(self):
        (self.case.root / 'copies/restore/foreign').write_bytes(b'foreign')
        with self.assertRaises(ValueError):
            self.call()


if __name__ == '__main__':
    unittest.main()

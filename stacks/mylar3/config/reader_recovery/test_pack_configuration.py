"""Genuine pack observation with an exact external app-configuration file."""
from contextlib import closing
import hashlib
import importlib.util
import os
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parent))
from appdata_cli_fixture import synthetic_cli
import test_appdata_transport as fixtures


class PackConfiguration(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.AppDataTransport('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.base
        self.scopes = []
        for role in ('native_config', 'worker_state', 'reader_config'):
            root = self.root / role
            with closing(sqlite3.connect(root / 'state.sqlite')) as db:
                db.execute('CREATE TABLE protected(value TEXT)')
                db.execute("INSERT INTO protected VALUES ('keep original')")
                db.commit()
            self.scopes.append(dict(role=role, root=str(root), databases=['state.sqlite']))
        directory = self.root / 'external'
        directory.mkdir()
        self.config = directory / 'settings.zip'
        self.config.write_bytes(b'{"placeholder":true,"state":"/state"}')
        self.config.chmod(0o600)
        (directory / 'unrelated.cbz').write_bytes(b'PK\x03\x04NOT APPLICATION DATA')
        path = Path(__file__).with_name('comic_retained_pack_backup.py')
        spec = importlib.util.spec_from_file_location('original_pack_configuration', path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.primitive = Path(__file__).parent.parent / 'standalone_launch_host/comic_appdata_restic_primitives.py'
        self.reference = dict(path=str(self.config), sha256=hashlib.sha256(self.config.read_bytes()).hexdigest(),
                              signature9=list(self.module.nine(self.config.lstat())))

    def backup(self, **options):
        with synthetic_cli(self.root):
            observation = self.module.copy_and_verify(self.scopes, self.root / 'recovery', self.primitive,
                hashlib.sha256(self.primitive.read_bytes()).hexdigest(), restic_appdata=True,
                external_configuration=self.reference, **options)
        self.addCleanup(self.release, observation)
        return observation

    def release(self, observation):
        witness = self.module._OBS[observation]['restic']
        for _, fd, frame, _ in witness['restore_custody']:
            try:
                if self.module.nine(os.fstat(fd)) == tuple(frame):
                    os.close(fd)
            except OSError:
                pass
        for _, fd, frame in (*witness['output_ancestors'], *witness['mount_custody']):
            try:
                if self.module.five(os.fstat(fd)) == tuple(frame):
                    os.close(fd)
            except OSError:
                pass
        try:
            if self.module.nine(os.fstat(witness['snapshot_fd'])) == tuple(witness['snapshot_signature9']):
                os.close(witness['snapshot_fd'])
        except OSError:
            pass

    def test_genuine_observation_restores_configuration_and_all_SQL_without_media(self):
        observation = self.backup()
        summary = observation.close()
        self.assertEqual(summary['storage'], 'restic-appdata-v2')
        self.assertEqual(summary['scopes'], 4)
        restored = self.root / 'recovery/restore/worker_configuration/configuration.json'
        self.assertEqual(restored.read_bytes(), self.config.read_bytes())
        self.assertFalse(list((self.root / 'recovery').rglob('*.cbz')))
        original, current = observation.current_scopes()
        self.assertEqual(set(current), {'native_config', 'worker_state', 'reader_config', 'worker_configuration'})
        self.assertEqual(current['worker_configuration'][0]['sha256'], self.reference['sha256'])
        self.assertEqual(len(original['databases']), 3)
        observation.close_copies()

    def test_external_file_is_forbidden_in_legacy_copy_mode(self):
        with self.assertRaisesRegex(ValueError, 'external-configuration-mode'):
            self.module.copy_and_verify(self.scopes, self.root / 'recovery', self.primitive,
                hashlib.sha256(self.primitive.read_bytes()).hexdigest(), external_configuration=self.reference)
        self.assertFalse((self.root / 'recovery').exists())

    def test_reference_content_or_incarnation_mismatch_holds(self):
        self.reference['sha256'] = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'original-configuration-ref'):
            self.backup()
        self.assertFalse((self.root / 'recovery').exists())

    def test_source_configuration_mutation_holds_original_source_close(self):
        observation = self.backup()
        self.config.write_bytes(b'{"changed":true}')
        with self.assertRaises(ValueError):
            observation.close()

    def test_late_restored_configuration_FD_loss_holds(self):
        observation = self.backup()
        witness = self.module._OBS[observation]['restic']
        restored = str(self.root / 'recovery/restore/worker_configuration/configuration.json')
        descriptor = next(fd for path, fd, _, _ in witness['restore_custody'] if path == restored)
        os.close(descriptor)
        with self.assertRaises((OSError, ValueError)):
            observation.close_copies()


if __name__ == '__main__':
    unittest.main()

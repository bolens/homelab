"""Explicit external configuration scope; no parent-directory or media copy."""
import copy
import io
import os
from pathlib import Path
import sys
import tarfile
import time
import unittest

sys.path.insert(0, str(Path(__file__).parent))
import test_appdata_transport as fixtures
primitives = fixtures.primitives
transport = fixtures.transport


class ConfigurationScope(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.AppDataTransport('runTest')
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.parent = self.case.base / 'separate-configuration'
        self.parent.mkdir()
        self.config = self.parent / 'settings.zip'
        self.config.write_bytes(b'{"placeholder":true,"state":"/state"}')
        self.config.chmod(0o600)
        self.sibling = self.parent / 'unrelated.cbz'
        self.sibling.write_bytes(b'PK\x03\x04NEVER READ OR BACK UP')

    def scopes(self):
        scopes = copy.deepcopy(self.case.scopes)
        for scope in scopes:
            scope['kind'] = 'tree'
        records, _ = primitives.inventory(self.config, 'file')
        records[0]['path'] = 'configuration.json'
        scopes.append(dict(role='worker_configuration', root=str(self.config), kind='file', records=records))
        return scopes

    def index(self):
        return transport.appdata_make_index(self.scopes(), deadline=time.monotonic() + 10)

    def archive(self, index):
        output = io.BytesIO()
        transport.appdata_write_archive(output, index, deadline=time.monotonic() + 10)
        return output.getvalue()

    def restore(self, index, raw=None):
        destination = self.case.base / 'external-restore'
        result = transport.appdata_restore_archive(io.BytesIO(self.archive(index) if raw is None else raw),
            destination, index, deadline=time.monotonic() + 10)
        self.addCleanup(transport.appdata_release_restore, result['custody'])
        transport.appdata_verify_restored(destination, index, deadline=time.monotonic() + 10,
                                         custody=result['custody'])
        return destination, result['custody']

    def test_exact_external_configuration_restored_without_parent_siblings(self):
        index = self.index()
        self.assertEqual(transport.appdata_policy_value(index)['version'], 2)
        with tarfile.open(fileobj=io.BytesIO(self.archive(index))) as archive:
            self.assertEqual([name for name in archive.getnames() if name.startswith('worker_configuration/')],
                             ['worker_configuration/configuration.json'])
            self.assertFalse(any(name.endswith('.cbz') or 'unrelated' in name for name in archive.getnames()))
        destination, _ = self.restore(index)
        restored = destination / 'worker_configuration/configuration.json'
        self.assertEqual(restored.read_bytes(), self.config.read_bytes())
        self.assertNotEqual(restored.stat().st_ino, self.config.stat().st_ino)
        self.assertEqual(restored.stat().st_mode & 0o7777, 0o600)
        self.assertEqual(list((destination / 'worker_configuration').iterdir()), [restored])

    def test_non_configuration_bytes_and_duplicate_JSON_keys_hold(self):
        for raw in (b'PK\x03\x04PAYLOAD', b'[]', b'{"key":1,"key":2}', b'{"key":NaN}'):
            self.config.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(transport.Held):
                self.index()

    def test_external_symlink_or_hardlink_holds(self):
        os.link(self.config, self.parent / 'alias')
        with self.assertRaises(transport.Held):
            self.index()
        (self.parent / 'alias').unlink()
        self.config.unlink()
        self.config.symlink_to('unrelated.cbz')
        with self.assertRaises((transport.Held, primitives.Held)):
            self.index()

    def test_source_change_after_selection_holds_stream(self):
        index = self.index()
        self.config.write_bytes(b'{"different":true}')
        with self.assertRaises(transport.Held):
            self.archive(index)

    def test_extra_or_directory_records_refused(self):
        for mutation in ('extra', 'directory'):
            scopes = self.scopes()
            if mutation == 'extra':
                row = copy.deepcopy(scopes[-1]['records'][0])
                row['path'] = 'another.json'
                scopes[-1]['records'].append(row)
            else:
                scopes[-1]['records'][0]['kind'] = 'directory'
            with self.subTest(mutation=mutation), self.assertRaises(transport.Held):
                transport.appdata_make_index(scopes, deadline=time.monotonic() + 10)

    def test_missing_member_refuses_independent_restore(self):
        index = self.index()
        output = io.BytesIO()
        with tarfile.open(fileobj=io.BytesIO(self.archive(index))) as source:
            with tarfile.open(fileobj=output, mode='w') as destination:
                for member in source:
                    if member.name == 'worker_configuration/configuration.json':
                        continue
                    destination.addfile(member, source.extractfile(member))
        with self.assertRaises(transport.Held):
            self.restore(index, output.getvalue())

    def test_capacity_counts_external_configuration_once(self):
        scopes = self.scopes()
        index = transport.appdata_make_index(scopes, deadline=time.monotonic() + 10)
        files = tuple((str(transport.appdata_source(scope, row)), tuple(row['stamp']))
                      for scope in scopes for row in scope['records'])
        estimate = transport.appdata_estimate(scopes, files, deadline=time.monotonic() + 10)
        selected = transport.appdata_selected(transport.appdata_policy_value(index))
        self.assertEqual(estimate['app_bytes'], sum(row['stamp'][2] for _, row in selected))
        self.assertEqual(sum(scope['role'] == 'worker_configuration' for scope, _ in selected), 1)

    def test_file_scope_inside_an_existing_tree_is_rejected(self):
        scopes = self.scopes()
        self.config = self.case.base / 'worker_state/settings.json'
        records, _ = primitives.inventory(self.config, 'file')
        records[0]['path'] = 'configuration.json'
        scopes[-1].update(root=str(self.config), records=records)
        with self.assertRaisesRegex(transport.Held, 'configuration-scope-overlap'):
            transport.appdata_make_index(scopes, deadline=time.monotonic() + 10)


if __name__ == '__main__':
    unittest.main()

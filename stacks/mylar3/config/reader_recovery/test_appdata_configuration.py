"""Explicit external configuration scope; no parent-directory or media copy."""
import copy
import io
import os
from pathlib import Path
import sys
import tarfile
import tempfile
from unittest.mock import patch
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


class LiveCapacitySample(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.scopes = []
        for role in ('native_config', 'worker_state', 'reader_config'):
            path = self.root / role
            path.mkdir()
            (path / 'settings.json').write_bytes(b'{"placeholder":true}')
            self.scopes.append(dict(role=role, root=str(path), kind='tree'))
        self.database = self.root / 'native_config/workflow.sqlite'
        self.database.write_bytes(b'SQLite format 3\x00fixture')
        self.external = self.root / 'external/settings.zip'
        self.external.parent.mkdir()
        self.external.write_bytes(b'{"placeholder":true}')

    def sample(self, scopes=None):
        return transport.appdata_capacity_sample(self.scopes if scopes is None else scopes,
                                                deadline=time.monotonic() + 10)

    def test_only_aggregate_preliminary_facts_with_no_preservation_authority(self):
        result = self.sample()
        self.assertEqual(set(result), {'app_bytes', 'media_bytes', 'largest_app_file', 'nodes_sampled',
                                       'preliminary', 'source_preservation', 'backup_authority'})
        self.assertTrue(result['preliminary'])
        self.assertIs(result['source_preservation'], False)
        self.assertIs(result['backup_authority'], False)
        self.assertEqual(result['media_bytes'], 0)
        self.assertEqual(result['app_bytes'], sum(path.stat().st_size for path in self.root.rglob('*')
                                               if path.is_file() and path != self.external))

    def test_completed_native_samples_may_change_during_later_scope_sampling(self):
        original = transport.appdata_payload
        def churn(role, relative, head, **kwargs):
            if role == 'worker_state':
                self.database.write_bytes(b'SQLite format 3\x00new current epoch')
                directory = self.database.parent / 'new-app-state'
                directory.mkdir()
                (directory / 'new.json').write_bytes(b'{}')
            return original(role, relative, head, **kwargs)
        with patch.object(transport, 'appdata_payload', churn):
            self.assertTrue(self.sample()['preliminary'])

    def test_change_during_individual_file_read_refuses(self):
        original = transport.appdata_payload
        def churn(role, relative, head, **kwargs):
            if Path(kwargs['path']) == self.database:
                self.database.write_bytes(b'changed during original file read')
            return original(role, relative, head, **kwargs)
        with patch.object(transport, 'appdata_payload', churn):
            with self.assertRaisesRegex(transport.Held, 'capacity-original-file-close'):
                self.sample()

    def test_root_replacement_refuses_and_releases_owned_descriptors(self):
        original = transport.appdata_payload
        reader = self.root / 'reader_config'
        before = set(os.listdir('/proc/self/fd'))
        def replace(role, relative, head, **kwargs):
            if role == 'worker_state':
                reader.rename(reader.with_name('displaced-reader'))
                reader.mkdir()
            return original(role, relative, head, **kwargs)
        with patch.object(transport, 'appdata_payload', replace):
            with self.assertRaisesRegex(transport.Held, 'original-ancestor'):
                self.sample()
        self.assertEqual(set(os.listdir('/proc/self/fd')), before)

    def test_external_configuration_drift_before_its_turn_refuses(self):
        scopes = self.scopes + [dict(role='worker_configuration', root=str(self.external), kind='file')]
        original = transport.appdata_payload
        def replace(role, relative, head, **kwargs):
            if role == 'native_config':
                self.external.write_bytes(b'{"changed":true}')
            return original(role, relative, head, **kwargs)
        with patch.object(transport, 'appdata_payload', replace):
            with self.assertRaisesRegex(transport.Held, 'original-configuration-root'):
                self.sample(scopes)

    def test_exact_external_file_does_not_enumerate_its_parent(self):
        scopes = self.scopes + [dict(role='worker_configuration', root=str(self.external), kind='file')]
        (self.external.parent / 'unselected.cbz').write_bytes(b'PK\x03\x04original')
        original = transport.os.scandir
        def forbid_parent(path):
            if isinstance(path, int):
                self.assertNotEqual(transport.appdata_node5(os.fstat(path)),
                                    transport.appdata_node5(self.external.parent.stat()))
            return original(path)
        with patch.object(transport.os, 'scandir', forbid_parent):
            self.assertEqual(self.sample(scopes)['app_bytes'],
                             self.sample()['app_bytes'] + self.external.stat().st_size)

    def test_same_classifier_excludes_worker_media_and_refuses_unknown_native_archive(self):
        (self.root / 'worker_state/original.cbz').write_bytes(b'PK\x03\x04original')
        self.assertGreater(self.sample()['media_bytes'], 0)
        (self.root / 'native_config/unknown.zip').write_bytes(b'PK\x03\x04unknown')
        with self.assertRaisesRegex(transport.Held, 'native-unclassified-archive'):
            self.sample()

    def test_supported_local_app_link_is_not_followed_or_counted_twice(self):
        worker = self.root / 'worker_state'
        (worker / 'alias').symlink_to('settings.json')
        self.assertEqual(self.sample()['app_bytes'], sum(path.stat().st_size for path in self.root.rglob('*')
                                                       if path.is_file() and not path.is_symlink() and path != self.external))
        (worker / 'alias').unlink()
        (worker / 'alias').symlink_to('../reader_config/settings.json')
        with self.assertRaisesRegex(transport.Held, 'capacity-link-local-file'):
            self.sample()

    def test_source_hardlink_group_must_be_complete(self):
        source = self.root / 'worker_state/settings.json'
        os.link(source, self.root / 'outside-link')
        with self.assertRaisesRegex(transport.Held, 'complete-hardlink-group'):
            self.sample()
        (self.root / 'outside-link').unlink()
        os.link(source, source.with_name('inside-link'))
        self.assertGreater(self.sample()['app_bytes'], 0)

    def test_role_and_scope_alias_policies_are_frozen_before_callbacks(self):
        original = transport.appdata_payload
        caller = copy.deepcopy(self.scopes)
        def mutate(*args, **kwargs):
            caller[2]['root'] = str(self.external.parent)
            return original(*args, **kwargs)
        with patch.object(transport, 'appdata_payload', mutate):
            self.assertTrue(self.sample(caller)['preliminary'])
        for scopes in (self.scopes[:2], list(reversed(self.scopes)),
                       self.scopes + [dict(role='worker_configuration', root=str(self.database), kind='file')]):
            with self.subTest(scopes=scopes), self.assertRaises(transport.Held):
                self.sample(scopes)

    def test_original_deadline_is_required(self):
        for deadline in (None, time.monotonic() - 1):
            with self.subTest(deadline=deadline), self.assertRaises(transport.Held):
                transport.appdata_capacity_sample(self.scopes, deadline=deadline)

    def test_bounded_growth_refuses_without_leaking_directory_descriptors(self):
        deep = self.root / 'worker_state'
        for _ in range(66):
            deep = deep / 'nested'
            deep.mkdir()
        before = set(os.listdir('/proc/self/fd'))
        with self.assertRaisesRegex(transport.Held, 'node-depth-bound'):
            self.sample()
        self.assertEqual(set(os.listdir('/proc/self/fd')), before)


    def test_aggregate_byte_bound_includes_all_encountered_app_and_media(self):
        directory = self.root / 'worker_state'
        for index in range(129):
            with (directory / ('sparse-' + str(index) + '.bin')).open('wb') as output:
                output.truncate(4 * 1024**3)
        with self.assertRaisesRegex(transport.Held, 'capacity-byte-bound'):
            self.sample()

    def test_unsupported_fifo_refuses_without_opening_it(self):
        os.mkfifo(self.root / 'worker_state/unsupported')
        with self.assertRaisesRegex(transport.Held, 'capacity-unsupported-node'):
            self.sample()


    def test_large_media_uses_prefix_only_and_keeps_app_file_limit(self):
        path = self.root / 'worker_state/large-original.cbz'
        with path.open('wb') as output:
            output.write(b'PK\x03\x04')
            output.truncate(5 * 1024**3)
        before = transport.appdata_signature(path.lstat())
        self.assertEqual(self.sample()['media_bytes'], 5 * 1024**3)
        self.assertEqual(transport.appdata_signature(path.lstat()), before)
        path.unlink()
        with (self.root / 'worker_state/oversize-app.bin').open('wb') as output:
            output.truncate(5 * 1024**3)
        with self.assertRaisesRegex(transport.Held, 'capacity-app-file-bound'):
            self.sample()


if __name__ == '__main__':
    unittest.main()

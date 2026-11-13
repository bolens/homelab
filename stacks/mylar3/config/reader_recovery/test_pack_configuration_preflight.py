"""Root preflight and genuine backup, with explicit Docker/Root ownership doubles.

This does not authenticate a launch, stop a service or establish live acceptance.
"""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from contextlib import closing
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import test_pack_configuration as fixture
from appdata_cli_fixture import synthetic_cli


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RootPreflight(unittest.TestCase):
    release = fixture.PackConfiguration.release

    def setUp(self):
        fixture.PackConfiguration.setUp(self)
        host = Path(__file__).parent.parent / 'standalone_launch_host'
        self.parent = load('configuration_preflight_parent', Path(__file__).with_name('comic_retained_pack_parent.py'))
        self.broker = load('configuration_preflight_broker', host / 'comic_retained_standalone_broker.py')
        self.primitive_module = load('configuration_preflight_primitives', self.primitive)
        native = self.root / 'native_config'
        data = native / 'mylar'
        data.mkdir()
        reader = self.root / 'reader_config'
        state = self.root / 'worker_state'
        for path in (data / 'mylar.db', data / 'workflow.sqlite', reader / 'database.sqlite', reader / 'tasks.sqlite'):
            with closing(sqlite3.connect(path)) as db:
                db.execute('CREATE TABLE protected(value TEXT)')
                db.commit()
        self.native_ini = data / 'config.ini'
        self.native_ini.write_bytes(b'[General]\nplaceholder=true\n')
        self.native_ini.chmod(0o600)
        self.library = self.root / 'library'
        self.library.mkdir()
        downloads = self.root / 'downloads'
        downloads.mkdir()
        (downloads / 'capture').mkdir()
        self.source = downloads / 'original.cbz'
        self.source.write_bytes(b'PK\x03\x04SOURCE')
        self.target = self.library / 'target.cbz'
        self.target.write_bytes(b'PK\x03\x04TARGET')
        cfg = dict(state='/state', mylar=dict(config_dir='/mylar'), writer_state='/mylar/media-writer',
                   roots=['/library'], maintenance=dict(ddl_cache='/ddl'))
        self.config.write_text(json.dumps(cfg))
        source_map = self.config.with_name('sources.json')
        source_map.write_text(json.dumps({'placeholder.py': 'a' * 64}))
        request = dict(version=1, kind='retained-ddl-existing-target-v1', ddl_id='56', pack_id='b' * 64,
            member_id='c' * 64, source_generation='d' * 64,
            source_sha256=hashlib.sha256(self.source.read_bytes()).hexdigest(),
            target_sha256=hashlib.sha256(self.target.read_bytes()).hexdigest(),
            owner=dict(table='issues', issueid='12', parentcomicid='34', releasecomicid='34'), review_sha256='f' * 64)
        review = self.config.with_name('review.json')
        review.write_text(json.dumps(dict(version=1, kind='retained-pack-reviewed-native-cohort', request=request,
            native_api_sha256='a' * 64, native_image='e' * 64,
            native_sources={name: 'a' * 64 for name in ('native_writers.py', 'publication_retained_api.py',
                                                       'publication_retained_delivery.py', 'publication_retained_finalize.py')},
            existing_target=dict(path='/library/target.cbz', sha256=request['target_sha256']))))
        for path in (source_map, review):
            path.chmod(0o600)
        receipt = state / 'maintenance/packs' / request['pack_id'] / 'receipt.json'
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps(dict(id=request['pack_id'], source_generation=request['source_generation'],
            inventory_complete=True, capture_source='/ddl/capture',
            members=[dict(id=request['member_id'], phase='review', source='/ddl/original.cbz')])) )
        receipt.chmod(0o600)
        def ref(path, child):
            return dict(path=child, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                        signature9=list(self.module.nine(path.lstat())))
        self.boot = dict(version=1, kind='pack-retained-bootstrap-v1', nonce='1' * 64, challenge='2' * 64,
            parent_sha256='3' * 64, request=request, data_root='/config/mylar',
            config_ref=ref(self.config, '/settings.zip'), source_map_ref=ref(source_map, '/sources.json'),
            review_ref=ref(review, '/review.json'))
        mount = lambda path, child: dict(Type='bind', Source=str(path), Destination=child, RW=True)
        mounts = dict(native=[mount(native, '/config')], reader=[mount(reader, '/config')], worker=[
            mount(state, '/state'), mount(data, '/mylar'), mount(self.library, '/library'), mount(downloads, '/ddl'),
            mount(self.config, '/settings.zip'), mount(source_map, '/sources.json'), mount(review, '/review.json')])
        self.ids = dict(native='4' * 64, reader='5' * 64, worker='6' * 64)
        running = dict(Running=True, Paused=False, Pid=os.getpid(), StartedAt='fixture-original',
                       Restarting=False, Dead=False, OOMKilled=False, Status='running', ExitCode=0)
        self.rows = {role: dict(Id=cid, Image='sha256:' + 'e' * 64, Config={}, HostConfig={}, Mounts=mounts[role],
            NetworkSettings=dict(Networks={}), State=dict(running)) for role, cid in self.ids.items()}
        self.rows['worker']['State'].update(Running=False, Pid=0, Status='created')
        def command(runtime, args):
            if args[0] == 'inspect':
                return self.parent.encode([copy.deepcopy(next(row for row in self.rows.values() if row['Id'] == args[1]))])
            raise AssertionError('Unexpected lifecycle/network command')
        commands = patch.object(self.parent.ConfiguredRuntime, 'command', command)
        commands.start()
        self.addCleanup(commands.stop)
        with patch.object(self.parent.os, 'geteuid', return_value=0):
            self.runtime = self.parent.ConfiguredRuntime.observe(self.ids)
        row = dict(document=dict(kind='pack-root-deployment-v1',
            native_config_ref=ref(self.native_ini, '/config/mylar/config.ini'),
            daemon_sources={'/app/mylar3/mylar/native_writers.py': 'a' * 64}),
            modules={'comic_retained_pack_parent.py': self.parent, 'comic_retained_pack_backup.py': self.module,
                     'comic_appdata_restic_primitives.py': self.primitive_module})
        self.installation = SimpleNamespace(close=lambda: row)
        self.backup_parent = self.root / 'root-backups'
        self.backup_parent.mkdir(mode=0o700)
        owner = self.backup_parent.stat()
        original_nine = self.broker.nine
        def root_ownership(stat):
            result = original_nine(stat)
            return result[:6] + (0, 0) + result[8:] if (stat.st_dev, stat.st_ino) == (owner.st_dev, owner.st_ino) else result
        for setting in (patch.object(self.broker, 'BACKUP_PARENT', self.backup_parent),
                        patch.object(self.broker, 'nine', root_ownership)):
            setting.start()
            self.addCleanup(setting.stop)

    def preflight(self):
        return self.broker._pack_preflight(self.installation, self.runtime, self.boot, '7' * 64)

    def operation(self):
        with synthetic_cli(self.root):
            plan = self.preflight()
            observation = self.module.copy_and_verify(plan['scopes'], Path(plan['output']), self.primitive,
                hashlib.sha256(self.primitive.read_bytes()).hexdigest(), restic_appdata=True,
                external_configuration=plan['external_configuration'])
        self.addCleanup(self.release, observation)
        return plan, observation

    def test_preflight_derives_original_external_ref_and_genuine_factory_restores_it(self):
        plan, observation = self.operation()
        self.assertEqual(plan['external_configuration']['path'], str(self.config))
        self.assertEqual(plan['external_configuration']['sha256'], hashlib.sha256(self.config.read_bytes()).hexdigest())
        self.assertEqual(observation.close()['storage'], 'restic-appdata-v2')
        self.assertEqual((Path(plan['output']) / 'restore/worker_configuration/configuration.json').read_bytes(),
                         self.config.read_bytes())
        self.assertFalse(self.runtime.quiescent)
        self.assertTrue(self.rows['native']['State']['Running'])

    def test_terminal_unchanged_configuration_rule_refuses_actual_postbackup_change(self):
        _, observation = self.operation()
        original, measured = observation.current_scopes()
        old = next(scope['records'] for scope in original['source_scopes'] if scope['name'] == 'worker_configuration')
        self.broker._pack_scope_successor(old, measured['worker_configuration'], changed={}, new_files=set(), new_directories=set())
        self.config.write_bytes(b'{"changed":true}')
        _, measured = observation.current_scopes()
        with self.assertRaises(self.broker.Held):
            self.broker._pack_scope_successor(old, measured['worker_configuration'], changed={}, new_files=set(), new_directories=set())


    def test_preflight_samples_changing_native_database_without_claiming_its_epoch(self):
        original = self.primitive_module.appdata_payload
        database = self.native_ini.parent / 'workflow.sqlite'
        def change_completed_scope(role, *args, **kwargs):
            if role == 'worker_state':
                with closing(sqlite3.connect(database)) as db:
                    db.execute("INSERT INTO protected VALUES ('new current epoch')")
                    db.commit()
            return original(role, *args, **kwargs)
        with synthetic_cli(self.root), patch.object(self.primitive_module, 'appdata_payload', change_completed_scope):
            plan = self.preflight()
        controls = dict(plan['config_frame'][0])
        self.assertIn(str(self.native_ini), controls)
        self.assertIn(str(self.config), controls)
        self.assertNotIn(str(database), controls)
        self.assertEqual(plan['config_frame'][2], ())
        self.assertFalse(Path(plan['output']).exists())

    def test_native_configuration_change_during_sample_still_refuses(self):
        original = self.primitive_module.appdata_payload
        def change(role, *args, **kwargs):
            if role == 'worker_state':
                self.native_ini.write_bytes(b'[General]\nchanged=true\n')
            return original(role, *args, **kwargs)
        with synthetic_cli(self.root), patch.object(self.primitive_module, 'appdata_payload', change):
            with self.assertRaises((ValueError, self.broker.Held)):
                self.preflight()

    def test_worker_configuration_change_during_sample_still_refuses(self):
        original = self.primitive_module.appdata_payload
        def change(role, *args, **kwargs):
            if role == 'native_config':
                self.config.write_bytes(b'{"changed":true}')
            return original(role, *args, **kwargs)
        with synthetic_cli(self.root), patch.object(self.primitive_module, 'appdata_payload', change):
            with self.assertRaises((ValueError, self.primitive_module.Held, self.broker.Held)):
                self.preflight()

    def test_genuine_factory_rejects_underestimate_using_fresh_capacity_before_snapshot(self):
        estimate = dict(app_bytes=0, media_bytes=0, largest_app_file=0, nodes_sampled=3,
                        preliminary=True, source_preservation=False, backup_authority=False)
        with synthetic_cli(self.root):
            with patch.object(self.primitive_module, 'appdata_capacity_sample', return_value=estimate):
                plan = self.preflight()
            source = self.native_ini.parent / 'new-current-app-data.bin'
            with source.open('wb') as output:
                output.truncate(200 * 1024**2)
            low = SimpleNamespace(free=1024**3 + 64 * 1024**2)
            with patch.object(self.primitive_module.shutil, 'disk_usage', return_value=low):
                with self.assertRaisesRegex(Exception, 'restic-appdata-capacity'):
                    self.module.copy_and_verify(plan['scopes'], Path(plan['output']), self.primitive,
                        hashlib.sha256(self.primitive.read_bytes()).hexdigest(), restic_appdata=True,
                        external_configuration=plan['external_configuration'])
        self.assertFalse(Path(plan['output']).exists())
        self.assertEqual(list((self.root / 'synthetic-repository/snapshots').iterdir()), [])
        self.assertEqual(source.stat().st_size, 200 * 1024**2)


if __name__ == '__main__':
    unittest.main()

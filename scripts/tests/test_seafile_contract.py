"""Portable Seafile 14 migration and non-mutating preparation contracts."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
STACK = ROOT / 'stacks/seafile'


class SeafileContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.compose = yaml.safe_load((STACK / 'docker-compose.yml').read_text())
        cls.services = cls.compose['services']

    def test_redis_is_ephemeral_authenticated_and_not_published(self):
        redis = self.services['redis']
        self.assertEqual(redis['image'], 'redis:8-alpine@sha256:3811787313eba226a2ef38658c6ccb91cd5e110edc89c37767de373120a0e5a0')
        self.assertEqual(redis['networks'], ['default'])
        self.assertNotIn('ports', redis)
        self.assertNotIn('volumes', redis)
        self.assertEqual(redis['user'], '1000:1000')
        self.assertEqual(redis['tmpfs'], ['/data:rw,nosuid,nodev,noexec,size=16m,mode=0700,uid=1000,gid=1000'])
        self.assertEqual(redis['command'], ['/bin/sh', '-ec', 'exec redis-server --requirepass "$$REDIS_PASSWORD" --save "" --appendonly no'])
        self.assertIn('REDIS_PASSWORD=${REDIS_PASSWORD:?Set REDIS_PASSWORD in stack.env}', redis['environment'])
        self.assertIn('REDISCLI_AUTH="$$REDIS_PASSWORD"', redis['healthcheck']['test'][1])
        self.assertIn('grep -qx PONG', redis['healthcheck']['test'][1])
        self.assertNotIn('memcached', self.services)
        app = self.services['seafile']
        self.assertEqual(app['depends_on']['redis'], {'condition': 'service_healthy'})
        self.assertIn('CACHE_PROVIDER=redis', app['environment'])
        self.assertIn('REDIS_HOST=redis', app['environment'])
        self.assertIn('REDIS_PORT=6379', app['environment'])
        self.assertIn('REDIS_PASSWORD=${REDIS_PASSWORD:?Set REDIS_PASSWORD in stack.env}', app['environment'])
        self.assertFalse(any(key.startswith('MEMCACHED_') for key in app['environment']))

    def test_database_volume_and_ingress_boundaries_are_retained(self):
        self.assertEqual(self.services['db']['image'], 'mariadb:13.0')
        self.assertEqual(self.services['db']['volumes'], ['seafile_db12:/var/lib/mysql'])
        self.assertEqual(self.services['seafile']['volumes'], ['seafile_data:/shared'])
        self.assertEqual(set(self.compose['volumes']), {'seafile_db12', 'seafile_data'})
        self.assertEqual(self.services['db']['networks'], ['default'])
        self.assertEqual(self.services['seafile']['networks'], ['default', 'ingress-public'])
        self.assertEqual(self.compose['networks'], {'ingress-public': {'name': 'ingress-public', 'external': True}})
        for service in self.services.values():
            for key in ('ports', 'privileged', 'network_mode', 'devices'):
                self.assertNotIn(key, service)
        self.assertEqual(self.services['seafile']['healthcheck']['test'], ['CMD', 'curl', '-f', 'http://127.0.0.1:80/'])
        self.assertIn('reverse_proxy seafile:80', (STACK / 'caddy_snippet.conf.example').read_text())

    def test_versioned_settings_do_not_enable_unprovisioned_features(self):
        app = self.services['seafile']
        self.assertEqual(app['image'], 'seafileltd/seafile-mc:14.0-latest')
        env = app['environment']
        for key in ('ENABLE_SEADOC=false', 'ENABLE_NOTIFICATION_SERVER=false', 'ENABLE_SEAFILE_AI=false',
                    'ENABLE_SEAFDAV=${ENABLE_SEAFDAV:-false}', 'SEAFDAV_WORKERS=${SEAFDAV_WORKERS:-5}',
                    'ENABLE_METADATA_MANAGEMENT=${ENABLE_METADATA_MANAGEMENT:-False}',
                    'SEAFILE_SERVER_PROTOCOL=${SEAFILE_SERVER_PROTOCOL:-https}'):
            self.assertIn(key, env)
        for role, default in [('CCNET', 'ccnet_db'), ('SEAFILE', 'seafile_db'), ('SEAHUB', 'seahub_db')]:
            self.assertIn(f'SEAFILE_MYSQL_DB_{role}_DB_NAME=${{SEAFILE_MYSQL_DB_{role}_DB_NAME:-{default}}}', env)

    def test_metadata_and_migration_cover_persistence_and_removed_settings(self):
        meta = yaml.safe_load((STACK / 'stack.yaml').read_text())
        self.assertEqual(meta['databases'], ['mysql', 'redis'])
        self.assertEqual({row['name'] for row in meta['volumes']}, {'seafile_db12', 'seafile_data'})
        self.assertTrue(all(row['critical'] for row in meta['volumes']))
        readme = (STACK / 'README.md').read_text()
        for required in ('isolated', 'rollback', 'seafile_db12', 'seafile_data', 'MariaDB 12',
                         'ENABLE_SEAFDAV', 'INNER_METADATA_SERVER_URL', 'DISABLE_SSO_USER_LOCAL_PWD_LOGIN',
                         'monthly_download_traffic_limit', 'monthly_download_traffic_limit_per_user',
                         'monthly_upload_traffic_limit', 'verified backup', '14.0/upgrade/upgrade_docker_14.0/'):
            self.assertIn(required, readme)

    def fixture(self, root):
        stack = root / 'stacks/seafile'
        stack.mkdir(parents=True)
        for name in ('prepare-stack.sh', 'stack.env.example', 'caddy_snippet.conf.example', 'docker-compose.yml'):
            shutil.copy2(STACK / name, stack / name)
        (root / 'scripts').mkdir()
        shutil.copy2(ROOT / 'scripts/prepare-stack-lib.sh', root / 'scripts/prepare-stack-lib.sh')
        return stack

    def test_preparation_is_idempotent_preserves_settings_and_never_starts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stack = self.fixture(root)
            stub = root / 'bin'
            stub.mkdir()
            calls = root / 'docker-calls'
            docker = stub / 'docker'
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\ncase "$*" in\n"info"|"network inspect ingress-public") exit 0;;\n*) exit 97;;\nesac\n')
            docker.chmod(0o755)
            env = {'PATH': str(stub) + ':/usr/bin:/bin', 'HOME': str(root), 'CALLS': str(calls)}
            result = subprocess.run(['bash', str(stack / 'prepare-stack.sh')], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((stack / 'stack.env').read_bytes(), (stack / 'stack.env.example').read_bytes())
            private = b'REDIS_PASSWORD=private_fixture_value\nJWT_PRIVATE_KEY=fixture_key\nUNRELATED_SETTING=keep\n'
            (stack / 'stack.env').write_bytes(private)
            (stack / 'caddy_snippet.conf').write_text('private-fixture-ingress\n')
            (stack / 'application-settings').write_text('keep existing setting\n')
            for _ in range(2):
                result = subprocess.run(['bash', str(stack / 'prepare-stack.sh')], env=env, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn('private_fixture_value', result.stdout + result.stderr)
                self.assertNotIn('fixture_key', result.stdout + result.stderr)
                self.assertEqual((stack / 'stack.env').read_bytes(), private)
                self.assertEqual((stack / '.env').read_bytes(), private)
                self.assertEqual((stack / 'caddy_snippet.conf').read_text(), 'private-fixture-ingress\n')
                self.assertEqual((stack / 'application-settings').read_text(), 'keep existing setting\n')
            self.assertEqual(calls.read_text().splitlines(), ['info', 'network inspect ingress-public'] * 3)

    def test_original_compose_renders_and_missing_redis_secret_refuses(self):
        docker = shutil.which('docker')
        if docker is None:
            self.skipTest('Docker Compose CLI unavailable; no daemon operation required')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stack = self.fixture(root)
            shutil.copy2(stack / 'stack.env.example', stack / 'stack.env')
            env = {'PATH': os.environ['PATH'], 'HOME': str(root), 'DOCKER_CONFIG': str(root / 'docker-config')}
            command = [docker, 'compose', '--project-directory', str(stack), '--env-file', str(stack / 'stack.env'),
                       '-f', str(stack / 'docker-compose.yml'), 'config', '--quiet']
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stderr)
            original = (stack / 'stack.env').read_text()
            (stack / 'stack.env').write_text('\n'.join(line for line in original.splitlines() if not line.startswith('REDIS_PASSWORD=')) + '\n')
            result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('REDIS_PASSWORD', result.stderr)


if __name__ == '__main__':
    unittest.main()

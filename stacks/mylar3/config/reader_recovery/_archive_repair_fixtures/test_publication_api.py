"""Authentication, bounded protocol and genuine native registration controls."""
import ast
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import sys
import types
import unittest
from unittest.mock import patch

import publication_api as api
import publication_guard as guard
import patch_publication_guard as adapter
import test_publication_guard as fixtures

TOOL_ROOT = fixtures.TOOL_ROOT


class ProtocolTests(unittest.TestCase):
    def test_malformed_requests_never_construct_state(self):
        bad = ['{"version":1,"version":1,"action":"status"}',
               '{"version":1.0,"action":"status"}',
               '{"version":true,"action":"status"}',
               '{"version":1,"action":"status","path":"/private"}',
               '{"version":1,"action":"status","extra":NaN}',
               '{"version":1,"action":"status","extra":' + '1'*21 + '}',
               '['*17 + '0' + ']'*17,
               '{"version":1,"action":"unknown"}',
               '{"version":1,"action":"register","token":"bad"}',
               '{"version":1,"action":"recover-registration","token":"'+'a'*64+'","mode":true}',
               ' '* (api.MAX_REQUEST+1),
               json.dumps({'version':1,'action':'status','extra':[0]*65536})]
        with patch.object(api, 'Controller') as controller:
            for raw in bad:
                with self.subTest(raw=raw[:100]), self.assertRaises(guard.Unavailable):
                    api.execute(raw, data_dir='/absent', library_roots=[])
            controller.assert_not_called()

    def test_request_preserves_exact_values_and_quoted_brackets(self):
        self.assertEqual(api.request('{"version":1,"action":"status"}'), dict(version=1, action='status'))
        backup = dict(manifest_sha256='a'*64, restore_sha256='b'*64, description='["reviewed"]')
        value = dict(version=1, action='prepare-bootstrap', epoch='c'*64, backup=backup)
        self.assertEqual(api.request(json.dumps(value)), value)

    def test_no_caller_filesystem_or_native_observation_fields(self):
        for field in ('data_dir', 'writer_root', 'library_roots', 'source', 'observed'):
            with self.subTest(field=field), self.assertRaises(guard.Unavailable):
                api.request(json.dumps(dict(version=1, action='status', **{field:'/private'})))


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.module = types.SimpleNamespace(execute=lambda *args, **kwargs: {'called': True})
        self.mylar = types.ModuleType('mylar')
        self.mylar.CONFIG = types.SimpleNamespace(API_ENABLED=True, API_KEY='p'*32, DESTINATION_DIR='/library')
        self.mylar.DATA_DIR = '/state';self.mylar.publication_api = self.module
        self.cherrypy = types.SimpleNamespace(request=types.SimpleNamespace(method='POST'))
        namespace = {'mylar':self.mylar, 'cherrypy':self.cherrypy}
        exec('class Handler:\n' + adapter.METHOD, namespace)
        self.handler = namespace['Handler']()
        self.handler.apikey = 'p'*32;self.handler.apitype = 'normal'
        self.handler._failureResponse = lambda message: {'error':message}
        self.handler._successResponse = lambda value: {'result':value}

    def test_primary_post_authenticated_before_protocol_import(self):
        cases = [('s'*32, 'sse', True, 'POST', {'request':'invalid'}),
                 ('p'*32, 'normal', False, 'POST', {'request':'invalid'}),
                 ('p'*32, 'normal', True, 'GET', {'request':'invalid'}),
                 ('p'*32, 'normal', True, 'POST', {'request':'invalid','callback':'jsonp'}),
                 ('p'*32, 'sse', True, 'POST', {'request':'invalid'})]
        with patch.object(self.module, 'execute') as execute, patch.dict(sys.modules, {'mylar':self.mylar}):
            for key, kind, enabled, method, kwargs in cases:
                self.handler.apikey=key;self.handler.apitype=kind
                self.mylar.CONFIG.API_ENABLED=enabled;self.cherrypy.request.method=method
                self.handler._publicationControl(**kwargs)
                self.assertIn('error', self.handler.data)
            execute.assert_not_called()

    def test_primary_request_uses_only_native_configuration_and_sanitizes_errors(self):
        with patch.dict(sys.modules, {'mylar':self.mylar}), patch.object(self.module, 'execute') as execute:
            execute.return_value = {'version':1}
            self.handler._publicationControl(request='reviewed')
            execute.assert_called_once_with('reviewed', data_dir='/state', library_roots=['/library'])
            self.assertEqual(self.handler.data, {'result':{'version':1}})
            execute.side_effect = ValueError('/private/secret')
            self.handler._publicationControl(request='invalid')
            self.assertNotIn('secret', str(self.handler.data))

    def test_checked_idempotent_source_patch_and_tampering_refusal(self):
        source = "commands = ['getVersion', 'checkGithub']\nclass Api:\n    def _getVersion(self, **kwargs):\n        pass\n"
        result = adapter.patched_source(source)
        self.assertEqual(adapter.patched_source(result), result);ast.parse(result)
        for changed in (result.replace("len(key) != 32", "False"), source.replace('checkGithub','changed')):
            with self.assertRaises(ValueError):adapter.patched_source(changed)

    @unittest.skipUnless(os.environ.get('MYLAR_WORKFLOW_SOURCE'), 'actual native source supplied by image gate')
    def test_actual_pinned_api_patch_twice(self):
        source = (Path(os.environ['MYLAR_WORKFLOW_SOURCE']) / 'api.py').read_text()
        result = adapter.patched_source(source)
        self.assertEqual(adapter.patched_source(result), result)
        self.assertEqual(result.count('def _publicationControl('), 1);ast.parse(result)
        if Path('/app/mylar3/lib').is_dir():
            import subprocess
            subprocess.run([sys.executable, '-c',
                'from mylar import publication_api, api; assert callable(publication_api.execute); assert callable(api.Api._publicationControl)'],
                check=True, env=dict(os.environ, PYTHONPATH=str(Path(os.environ['MYLAR_WORKFLOW_SOURCE']).parent)+':/app/mylar3:/app/mylar3/lib'))


@unittest.skipUnless((Path(TOOL_ROOT) / 'lib/archive_backend.py').is_file(), 'custom image offline archive verifier required')
class NativeProtocolTests(unittest.TestCase):
    def setUp(self):
        fixtures.NativeObservationTests.setUp(self)
        from workflow_store import Store
        self.store = Store(self.root)
        self.controller = api.Controller(self.root, [self.library], tool_root=TOOL_ROOT)
        self.backup = dict(manifest_sha256='a'*64, restore_sha256='b'*64, description='private backup description')

    def call(self, action, **kwargs):
        value = api.request(json.dumps(dict(version=1, action=action, **kwargs)))
        return self.controller.dispatch(value)

    def bootstrap(self):
        prepared = self.call('prepare-bootstrap', epoch='c'*64, backup=self.backup)
        self.assertNotIn('description', prepared['backup'])
        return self.call('initialize-bootstrap', token=prepared['token'])['census']

    def prepare(self, census=None):
        with self.writer.hold():
            inventory = guard.observe_owners(self.database, self.writer, [self.owner], [self.library], tool_root=TOOL_ROOT)['inventory']
        rejected = dict(table='issues', issueid='999', parentcomicid='888', releasecomicid='888')
        return self.call('prepare-registration', census=census or self.bootstrap(), inventory=inventory,
                         allowed=[self.owner], rejected=[rejected], created=1,
                         evidence=dict(sha256='d'*64, description='private reviewed evidence'))

    def test_prepare_native_commit_replay_and_advisory(self):
        prepared = self.prepare()
        self.assertNotIn('description', json.dumps(prepared))
        self.assertNotIn(str(self.source), json.dumps(prepared))
        self.assertEqual(prepared['outcome'], 'prepared')
        self.assertEqual(self.call('status')['census']['revision'], 0)
        committed = self.call('register', token=prepared['token'])
        self.assertEqual(committed['census']['revision'], 1)
        self.assertEqual(self.call('register', token=prepared['token']), committed)
        check = self.call('check', owner=self.owner, payload=prepared['payload'])
        self.assertTrue(check['advisory']);self.assertEqual(check['decision'], 'allowed')
        check = self.call('check', owner=prepared['rejected'][0], payload=prepared['payload'])
        self.assertEqual(check['decision'], 'held')
        with patch.object(self.controller, 'observe') as observe:
            self.assertEqual(self.call('check', owner=self.owner, payload='e'*64)['decision'], 'unknown')
            observe.assert_not_called()

    def test_stale_catalog_commit_refused_without_authority_changes(self):
        prepared = self.prepare();before = self.controller.database.read_bytes()
        with closing(sqlite3.connect(self.database)) as db:
            db.execute("UPDATE issues SET Status='Wanted'");db.commit()
        with self.assertRaises(guard.Unavailable):self.call('register', token=prepared['token'])
        self.assertEqual(self.controller.database.read_bytes(), before)
        self.assertEqual(self.call('status')['census']['revision'], 0)
        with self.assertRaises(guard.Unavailable):
            self.call('recover-registration', token=prepared['token'], mode='abort')
        self.assertEqual(self.controller.database.read_bytes(), before)

    def test_accepted_abort_and_repeat_finish_report_durable_outcome(self):
        prepared = self.prepare()
        state = guard.RegistrationState(self.controller.database, self.writer)
        def interrupted(stage):
            if stage == 'intent-accepted':
                raise RuntimeError('isolated interruption')
        with self.assertRaises(RuntimeError):
            state.register(prepared['token'], accepted_token=prepared['token'],
                           observe=lambda body:self.controller.observe(self.writer, body), boundary=interrupted)
        self.assertEqual(self.call('status', token=prepared['token'])['intent']['outcome'], 'accepted')
        result = self.call('recover-registration', token=prepared['token'], mode='abort')
        self.assertEqual(result['outcome'], 'aborted');self.assertEqual(result['census']['revision'], 0)
        for mode in ('abort', 'finish'):
            self.assertEqual(self.call('recover-registration', token=prepared['token'], mode=mode)['outcome'], 'aborted')
        self.assertEqual(self.call('status', token=prepared['token'])['intent']['outcome'], 'aborted')

    def test_status_receipt_is_read_only_and_hot_sidecar_refused_before_sql(self):
        prepared = self.prepare()
        before = self.controller.database.read_bytes()
        calls=[];original=sqlite3.connect
        def readonly(path, **kwargs):
            self.assertIn('mode=ro&immutable=1', str(path))
            db=original(path, **kwargs);db.set_trace_callback(calls.append);return db
        with patch('sqlite3.connect', side_effect=readonly):
            result=self.call('status', token=prepared['token'])
        self.assertEqual(result['intent']['outcome'], 'prepared')
        self.assertFalse(any('IMMEDIATE' in sql or sql.startswith(('UPDATE','INSERT','CREATE')) for sql in calls))
        self.assertEqual(self.controller.database.read_bytes(), before)
        journal=Path(str(self.controller.database)+'-journal');journal.write_bytes(b'unsupported sidecar')
        with patch('sqlite3.connect') as connect:
            result=self.call('status', token=prepared['token'])
            self.assertEqual(result['intent']['outcome'], 'unavailable');connect.assert_not_called()
        self.assertEqual(journal.read_bytes(), b'unsupported sidecar')

    def test_bootstrap_protocol_validation_rejects_oversize_before_state(self):
        value=dict(version=1,action='prepare-bootstrap',epoch='c'*64,
                   backup=dict(self.backup, description='x'*1025))
        with patch.object(api, 'Controller') as controller, self.assertRaises(guard.Unavailable):
            api.execute(json.dumps(value),data_dir=self.root,library_roots=[])
        controller.assert_not_called()

    def test_stale_census_and_wrong_payload_refused(self):
        census = self.bootstrap();prepared = self.prepare(census)
        self.call('register', token=prepared['token'])
        with self.assertRaises(guard.Unavailable):self.prepare(census)
        current = self.call('status')['census']
        with self.writer.hold():
            inventory = guard.observe_owners(self.database,self.writer,[self.owner],[self.library],tool_root=TOOL_ROOT)['inventory']
        inventory = dict(inventory, payload='e'*64)
        with self.assertRaises(guard.Unavailable):
            self.call('prepare-registration', census=current, inventory=inventory, allowed=[self.owner],
                      rejected=prepared['rejected'], created=1, evidence=dict(sha256='d'*64, description='review'))

    def test_passive_status_missing_authority_never_creates_state(self):
        other = api.Controller(self.root / 'absent', [], tool_root=TOOL_ROOT)
        with patch('sqlite3.connect') as connect:
            result = other.dispatch(dict(version=1, action='status'))
            self.assertEqual(result['state'], 'held');connect.assert_not_called()
        self.assertFalse(other.root.exists())

    def test_corrupt_valid_header_receipt_status_is_sanitized(self):
        prepared=self.prepare()
        raw=bytearray(self.controller.database.read_bytes());raw[100]=255
        self.controller.database.write_bytes(raw)
        result=self.call('status',token=prepared['token'])
        self.assertEqual(result['intent']['outcome'],'unavailable')
        self.assertEqual(result['state'],'held')
        self.assertNotIn(str(self.root),json.dumps(result))
        self.assertFalse(Path(str(self.controller.database)+'-journal').exists())

    def test_typed_journal_recovery_restores_old_without_registration(self):
        fixture=fixtures.RegistrationJournalTests();self.addCleanup(fixture.doCleanups);fixture.setUp()
        controller=api.Controller(fixture.root,[],tool_root=TOOL_ROOT)
        def call(action, **kwargs):
            return controller.dispatch(api.request(json.dumps(dict(version=1,action=action,**kwargs))))
        original=fixture.pair()
        prepared=call('prepare-journal',kind='registration',token=fixture.token)
        self.assertEqual(fixture.pair(),original)
        with self.assertRaises(guard.Unavailable):
            call('recover-journal',kind='bootstrap',token=prepared['token'])
        self.assertEqual(fixture.pair(),original)
        self.assertEqual(call('recover-journal',kind='registration',token=prepared['token'])['outcome'],'restored-old')
        self.assertEqual(call('status')['state'],'held')
        result=call('recover-registration',token=fixture.token,mode='abort')
        self.assertEqual(result['outcome'],'aborted');self.assertEqual(result['census']['revision'],1)

    def test_pending_media_check_holds_without_observing_or_clearing(self):
        prepared=self.prepare();self.call('register', token=prepared['token'])
        self.writer.create_file(self.writer.pending)
        before=self.writer.pending.read_bytes()
        with patch.object(self.controller, 'observe') as observe:
            result=self.call('check', owner=self.owner, payload=prepared['payload'])
            self.assertEqual(result['reason'], 'media-pending');observe.assert_not_called()
        self.assertEqual(self.writer.pending.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()

"""Durable conversion handoff fixtures, without live media or network access."""
from contextlib import nullcontext
import json
import ast
import sys
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from workflow_store import Store
import converted_tagging as tagging


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.now = 1000
        self.store = Store(self.temp.name, clock=lambda: self.now)
        self.payload = dict(version=1, path='/library/Series/Issue.cbz', sha256='a'*64)
        self.catalog = Mock(return_value=dict(issueid='12', comicid='34', agerating=None, readingorder=[]))
        self.inspect = Mock(return_value=('a'*64, False))
        self.tag = Mock(return_value='added')
        self.recover = Mock(return_value=None)
        self.settings = Mock(return_value=True)
        self.queue = tagging.Queue(self.store, self.catalog, nullcontext, self.inspect,
                                   self.tag, self.recover, self.settings, clock=lambda: self.now)

    def add(self):
        return tagging.admit(json.dumps(self.payload), self.store)['key']

    def record(self, key):
        return self.store.get('converted_tag', key)

    def test_duplicate_notification_and_completion_are_idempotent(self):
        key = self.add(); self.assertEqual(self.add(), key)
        self.queue.tick(); self.queue.tick(); self.add(); self.queue.tick()
        self.assertEqual(self.tag.call_count, 1)
        self.assertEqual(self.record(key)['phase'], 'completed')

    def test_delayed_rescan_waits_then_tags(self):
        key = self.add(); self.catalog.return_value = None
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'waiting-library')
        self.tag.assert_not_called()
        self.catalog.return_value = dict(issueid='12', comicid='34')
        self.now += 61; self.queue.tick()
        self.assertEqual(self.record(key)['phase'], 'completed')

    def test_ambiguous_catalog_and_replaced_file_require_review(self):
        key = self.add(); self.catalog.side_effect = ValueError('private details')
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'review')
        self.assertNotIn('private details', json.dumps(tagging.snapshot(self.store)))
        self.tag.assert_not_called()
        self.payload['path'] = '/library/Series/Other.cbz'; key = self.add()
        self.catalog.side_effect = None; self.inspect.return_value = ('b'*64, False)
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'review')
        self.tag.assert_not_called()

    def test_existing_metadata_and_unsupported_settings_do_not_tag(self):
        key = self.add(); self.settings.return_value = False
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'waiting-settings')
        self.assertEqual(self.record(key)['attempts'], 0)
        self.settings.return_value = True; self.now += 61
        self.inspect.return_value = ('b'*64, True)
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'completed')
        self.assertIn('preserved', self.record(key)['reason'])
        self.tag.assert_not_called()

    def test_restart_after_publication_uses_saved_token(self):
        key = self.add()
        self.tag.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.queue.tick()
        record = self.record(key)
        self.assertEqual(record['phase'], 'tagging')
        self.assertEqual(len(record['token']), 32)
        self.recover.return_value = 'added'
        self.queue.tick()
        self.assertEqual(self.record(key)['phase'], 'completed')
        self.assertEqual(self.tag.call_count, 1)
        self.assertEqual(self.recover.call_args.args[0]['token'], record['token'])

    def test_retry_is_bounded_and_does_not_block_later_job(self):
        key = self.add(); self.tag.return_value = 'failed'
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'retry')
        self.payload['path'] = '/library/Series/Second.cbz'; other = self.add()
        self.tag.return_value = 'added'; self.queue.tick()
        self.assertEqual(self.record(other)['phase'], 'completed')
        self.tag.return_value = 'failed'
        for _ in range(5):
            self.now += 4000; self.queue.tick()
        self.assertEqual(self.record(key)['phase'], 'review')
        self.assertEqual(self.record(key)['attempts'], 6)

    def test_changed_catalog_identity_does_not_reuse_publication(self):
        key = self.add(); self.tag.return_value = 'failed'; self.queue.tick()
        self.now += 4000; self.catalog.return_value = dict(issueid='99', comicid='34')
        self.queue.tick(); self.assertEqual(self.record(key)['phase'], 'review')
        self.assertEqual(self.tag.call_count, 1)

    def test_input_bounds_and_canonical_paths(self):
        for changes in ({'version':True}, {'path':'/library/../secret.cbz'}, {'path':'relative.cbz'},
                        {'path':'/library//comic.cbz'}, {'path':'/library/a\nb.cbz'},
                        {'sha256':'A'*64}, {'path':'/library/file.cbr'}, {'extra':True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                tagging.admit(json.dumps(dict(self.payload, **changes)), self.store)
        with self.assertRaises(ValueError): tagging.admit(' '*8193, self.store)

    def test_snapshot_never_exposes_paths_tokens_or_hashes(self):
        key = self.add(); self.queue.tick()
        value = json.dumps(tagging.snapshot(self.store))
        self.assertNotIn('/library', value); self.assertNotIn('a'*64, value)
        self.assertNotIn(self.record(key)['token'], value)


class IntegrationTest(unittest.TestCase):
    def test_primary_key_is_required_and_failure_is_sanitized(self):
        from patch_converted_tagging import api
        source = "class Api:\n    allowed = ['getVersion', 'checkGithub']\n    def _getVersion(self, **kwargs): pass\n"
        patched = api(source); self.assertEqual(api(patched), patched)
        namespace = {'mylar': SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True, API_KEY='primary'))}
        exec(compile(patched, '<fixture>', 'exec'), namespace)
        endpoint = namespace['Api']()
        endpoint._failureResponse = lambda value: dict(success=False, error=value)
        endpoint._successResponse = lambda value: dict(success=True, data=value)
        fake = SimpleNamespace(converted_tagging=SimpleNamespace(admit=Mock(return_value={'version':1})))
        with patch.dict(sys.modules, {'mylar': fake}):
            endpoint.apikey = 'read-only'; endpoint._queueConvertedTag(conversion='{}')
            fake.converted_tagging.admit.assert_not_called()
            self.assertFalse(endpoint.data['success'])
            endpoint.apikey = 'primary'; endpoint._queueConvertedTag(conversion='{}')
            self.assertTrue(endpoint.data['success'])
            fake.converted_tagging.admit.side_effect = RuntimeError('/private/path api-key')
            endpoint._queueConvertedTag(conversion='{}')
            self.assertNotIn('/private', str(endpoint.data))

    def test_native_idle_loop_anchor_is_checked_and_idempotent(self):
        from patch_converted_tagging import worker
        source = 'def work():\n    while True:\n        if False:\n            pass\n        else:\n            time.sleep(5)\n'
        result = worker(source); ast.parse(result)
        self.assertEqual(worker(result), result)
        self.assertIn('converted_tagging.poll()', result)
        with self.assertRaises(ValueError): worker('pass')


if __name__ == '__main__': unittest.main()

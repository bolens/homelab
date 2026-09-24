"""Worker liveness, progress, idle, and image patch contract regression tests."""
import ast
from pathlib import Path
import sys
import unittest

from health import assess
from patch_health import patched_source

SOURCE = Path(sys.argv.pop(1)) if len(sys.argv) > 1 else None


class HealthTest(unittest.TestCase):
    def setUp(self):
        self.value = {'enabled': ['POST-PROCESS-QUEUE', 'DDL-QUEUE'],
                      'queues': {name: {'alive': True, 'size': 0} for name in ('POST-PROCESS-QUEUE', 'DDL-QUEUE')},
                      'downloaded': 12, 'completed': 0, 'processing': False, 'ddl_active': []}

    def test_idle_is_healthy_indefinitely(self):
        initial = assess(self.value, {}, 0)
        self.assertFalse(assess(self.value, initial['observations'], 10000)['errors'])

    def test_dead_worker_is_immediate_error(self):
        self.value['queues']['DDL-QUEUE']['alive'] = False
        self.assertIn('DDL-QUEUE is down', assess(self.value, {}, 0)['errors'])

    def test_new_arrivals_cannot_hide_stall(self):
        self.value['processing'] = True
        initial = assess(self.value, {}, 0)
        self.value['completed'] = 2
        self.value['queues']['POST-PROCESS-QUEUE']['size'] = 4
        self.assertFalse(assess(self.value, initial['observations'], 899)['errors'])
        self.assertIn('POST-PROCESS-QUEUE has made no progress for 15 minutes',
                      assess(self.value, initial['observations'], 900)['errors'])

    def test_download_progress_resets_stall_and_idle_recovers(self):
        self.value['ddl_active'] = [['id', 1, 'date']]
        initial = assess(self.value, {}, 0)
        self.assertTrue(assess(self.value, initial['observations'], 900)['errors'])
        self.value['ddl_active'][0][1] = 2
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])
        self.value['ddl_active'] = []
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])

    def test_completed_import_resets_timer(self):
        self.value['completed'] = 3
        initial = assess(self.value, {}, 0)
        self.value['downloaded'] += 1
        self.assertFalse(assess(self.value, initial['observations'], 900)['errors'])

    def test_unknown_api_source_fails_closed(self):
        with self.assertRaises(ValueError):
            patched_source('def changed(): pass')

    @unittest.skipUnless(SOURCE, 'Provide candidate source directory')
    def test_candidate_patch_idempotent_and_primary_key_required(self):
        source = patched_source((SOURCE / 'api.py').read_text())
        self.assertEqual(patched_source(source), source)
        tree = ast.parse(source)
        for name in ('_getHealth', '_reportFailedDownload'):
            node = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == name)
            from types import SimpleNamespace
            from unittest.mock import Mock
            obj = SimpleNamespace(apikey='download-key', _failureResponse=Mock(return_value='denied'))
            namespace = {'mylar': SimpleNamespace(CONFIG=SimpleNamespace(API_ENABLED=True, API_KEY='primary-key'))}
            exec(compile(ast.Module(body=[node], type_ignores=[]), '<api>', 'exec'), namespace)
            namespace[name](obj)
            self.assertEqual(obj.data, 'denied')


if __name__ == '__main__':
    unittest.main()
